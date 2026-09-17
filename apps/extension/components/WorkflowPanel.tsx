// TIES production loop (SOP §3) in the sidebar — where the writer already works.
//
// Shows the current stage, the SLA against the SOP's 12/18h and 10/12h windows,
// and only the actions this person can actually take. Editor-only transitions
// are enforced on the server; hiding them here is courtesy, not security.

import { useCallback, useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { Spinner } from './ui';
import type { AuthUser } from '@/lib/api';
import { fetchWorkflow, transitionDocument } from '@/lib/api';
import type { WorkflowState, WorkflowStatus } from '@/lib/types';

// Stage labels a writer recognises, plus the SOP's own vocabulary.
const STAGE: Record<WorkflowStatus, { label: string; hint: string }> = {
  assigned: { label: 'Assigned', hint: 'Brief issued — drafting clock running.' },
  drafting: { label: 'Drafting', hint: 'Write the draft, then hand off to your editor.' },
  submitted: { label: 'Submitted', hint: 'With the editor — 10–12h review window.' },
  under_review: { label: 'Under review', hint: 'Editor is reviewing in Suggesting Mode.' },
  revising: { label: 'Revising', hint: 'Address the comments, then resubmit.' },
  approved: { label: 'Approved (GTG)', hint: 'Signed off and ready to publish.' },
  published: { label: 'Published', hint: 'Live.' },
  reassigned: { label: 'Reassigned', hint: 'Passed to another author.' },
  scrapped: { label: 'Scrapped', hint: 'Dropped by the editor.' },
  draft: { label: 'Draft', hint: 'Not yet in the production loop.' },
  finalized: { label: 'Finalized', hint: 'Legacy status.' },
};

// Which transitions each role may offer, and how the button should read.
const ACTION: Partial<
  Record<WorkflowStatus, { label: string; editorOnly: boolean; tone: 'primary' | 'plain' | 'danger' }>
> = {
  drafting: { label: 'Start drafting', editorOnly: false, tone: 'plain' },
  submitted: { label: 'Submit for review', editorOnly: false, tone: 'primary' },
  under_review: { label: 'Start review', editorOnly: true, tone: 'primary' },
  revising: { label: 'Send back for revision', editorOnly: true, tone: 'plain' },
  approved: { label: 'GTG — Approve', editorOnly: true, tone: 'primary' },
  published: { label: 'Mark published', editorOnly: true, tone: 'plain' },
  reassigned: { label: 'Reassign', editorOnly: true, tone: 'danger' },
  scrapped: { label: 'Scrap', editorOnly: true, tone: 'danger' },
};

const REASON_REQUIRED: WorkflowStatus[] = ['reassigned', 'scrapped'];

function isEditor(me: AuthUser | null): boolean {
  return me?.role === 'editor' || me?.role === 'admin';
}

function SlaBadge({ sla }: { sla: WorkflowState['sla'] }) {
  if (!sla.phase) return null;
  const hours = sla.hours_remaining ?? 0;
  const tone = sla.overdue
    ? { bg: '#FFE7E5', fg: '#F04438' }
    : sla.at_risk
      ? { bg: '#FFF0E1', fg: '#E8820C' }
      : { bg: '#DCFAE6', fg: '#17B26A' };
  const text = sla.overdue
    ? `${Math.abs(Math.round(hours))}h overdue`
    : `${Math.round(hours)}h left`;

  return (
    <span
      style={{ background: tone.bg, color: tone.fg }}
      className="rounded-full px-2 py-0.5 text-[11px] font-bold"
      title={sla.due_at ? `Due ${new Date(sla.due_at).toLocaleString()}` : undefined}
    >
      {text} · {sla.phase}
    </span>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex gap-2 py-0.5 text-[12px]">
      <span className="w-20 shrink-0 opacity-55">{label}</span>
      <span className="min-w-0 break-words">{children}</span>
    </div>
  );
}

export function WorkflowPanel({
  docId,
  me,
  onChanged,
}: {
  docId: string | null;
  me: AuthUser | null;
  onChanged?: () => void;
}) {
  const [state, setState] = useState<WorkflowState | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState<WorkflowStatus | null>(null);
  const [error, setError] = useState('');
  const [notTracked, setNotTracked] = useState(false);
  // Confirmation step for transitions that need a written reason or an override.
  const [pending, setPending] = useState<WorkflowStatus | null>(null);
  const [reason, setReason] = useState('');

  // Generation guard: the panel is torn down aggressively when the tab changes,
  // and a slow response must not write into a newer document's state.
  const seq = useRef(0);

  const load = useCallback(async () => {
    if (!docId) return;
    const mine = ++seq.current;
    setLoading(true);
    setError('');
    try {
      const next = await fetchWorkflow(docId);
      if (mine !== seq.current) return;
      setState(next);
      setNotTracked(false);
    } catch (e) {
      if (mine !== seq.current) return;
      const msg = e instanceof Error ? e.message : 'Could not load workflow.';
      // A doc Jalebi has never evaluated has no row yet — not an error.
      if (/not tracked/i.test(msg)) {
        setNotTracked(true);
        setState(null);
      } else {
        setError(msg);
      }
    } finally {
      if (mine === seq.current) setLoading(false);
    }
  }, [docId]);

  useEffect(() => {
    void load();
  }, [load]);

  const run = async (status: WorkflowStatus, extra: { reason?: string; override_reason?: string } = {}) => {
    if (!docId) return;
    const mine = ++seq.current;
    setBusy(status);
    setError('');
    try {
      const next = await transitionDocument(docId, status, extra);
      if (mine !== seq.current) return;
      setState(next);
      setPending(null);
      setReason('');
      onChanged?.();
    } catch (e) {
      if (mine !== seq.current) return;
      setError(e instanceof Error ? e.message : 'Could not update the status.');
    } finally {
      if (mine === seq.current) setBusy(null);
    }
  };

  const onAction = (status: WorkflowStatus) => {
    const needsReason = REASON_REQUIRED.includes(status);
    const needsOverride =
      status === 'approved' && (state?.blocking_reasons.length ?? 0) > 0;
    if (needsReason || needsOverride) {
      setPending(status);
      setReason('');
      return;
    }
    void run(status);
  };

  const confirm = () => {
    if (!pending) return;
    if (REASON_REQUIRED.includes(pending)) {
      void run(pending, { reason });
    } else {
      void run(pending, { override_reason: reason });
    }
  };

  if (!docId) return null;

  if (notTracked) {
    return (
      <section className="card p-4">
        <Header />
        <p className="mt-2 text-[12px] opacity-60">
          Not in the production loop yet. Run an evaluation to start tracking this
          document, then an editor can assign it.
        </p>
      </section>
    );
  }

  if (loading && !state) {
    return (
      <section className="card p-4">
        <Header />
        <div className="mt-3 flex items-center gap-2 text-[12px] opacity-60">
          <Spinner /> Loading workflow…
        </div>
      </section>
    );
  }

  if (!state) {
    return error ? (
      <section className="card p-4">
        <Header />
        <p className="mt-2 text-[12px] text-[#F04438]">{error}</p>
      </section>
    ) : null;
  }

  const stage = STAGE[state.status] ?? { label: state.status, hint: '' };
  const editor = isEditor(me);
  const actions = state.next_states.filter((s) => {
    const spec = ACTION[s];
    return spec && (!spec.editorOnly || editor);
  });
  const blocking = state.blocking_reasons;

  return (
    <section className="card p-4">
      <div className="flex items-center justify-between gap-2">
        <Header />
        <SlaBadge sla={state.sla} />
      </div>

      <div className="mt-2.5">
        <div className="text-[15px] font-bold">{stage.label}</div>
        {stage.hint && (
          <div className="text-[12px] opacity-60">{stage.hint}</div>
        )}
      </div>

      <div className="mt-2.5">
        {state.assigned_to && <Row label="Author">{state.assigned_to}</Row>}
        {state.editor && <Row label="Editor">{state.editor}</Row>}
        {(state.word_min != null || state.word_max != null) && (
          <Row label="Words">
            {state.word_min ?? 0}–{state.word_max ?? '∞'}
          </Row>
        )}
        {state.approved_by && (
          <Row label="Approved">
            {state.approved_by}
            {state.approved_at
              ? ` · ${new Date(state.approved_at).toLocaleDateString()}`
              : ''}
          </Row>
        )}
        {state.escalation_reason && (
          <Row label="Reason">{state.escalation_reason}</Row>
        )}
        {state.override_reason && (
          <Row label="Override">
            <span className="text-[#E8820C]">{state.override_reason}</span>
          </Row>
        )}
      </div>

      {/* Advisory, not blocking: SOP §4 gives the editor final say. */}
      {blocking.length > 0 && editor && (
        <div className="mt-3 rounded-lg bg-black/[0.04] p-2.5 dark:bg-white/[0.06]">
          <div className="text-[11px] font-bold opacity-70">
            Before signing off
          </div>
          <ul className="mt-1 space-y-0.5">
            {blocking.map((b) => (
              <li key={b} className="text-[12px] leading-snug opacity-70">
                • {b}
              </li>
            ))}
          </ul>
        </div>
      )}

      {error && <p className="mt-2 text-[12px] text-[#F04438]">{error}</p>}

      {/* Reason / override capture */}
      {pending ? (
        <div className="mt-3">
          <label className="text-[12px] font-semibold">
            {REASON_REQUIRED.includes(pending)
              ? `Why are you ${pending === 'scrapped' ? 'scrapping' : 'reassigning'} this?`
              : 'Reason for approving despite the items above'}
          </label>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={3}
            autoFocus
            placeholder="Recorded in the audit log and sent to the team lead."
            className="mt-1 w-full rounded-lg border border-black/10 bg-transparent p-2 text-[12px] dark:border-white/15"
          />
          <div className="mt-2 flex gap-2">
            <button
              onClick={confirm}
              disabled={!reason.trim() || busy !== null}
              className="rounded-lg bg-[#F04438] px-3 py-1.5 text-[12px] font-bold text-white disabled:opacity-40"
            >
              {busy ? 'Saving…' : 'Confirm'}
            </button>
            <button
              onClick={() => {
                setPending(null);
                setReason('');
              }}
              className="rounded-lg px-3 py-1.5 text-[12px] font-semibold opacity-70"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        actions.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {actions.map((s) => {
              const spec = ACTION[s]!;
              const cls =
                spec.tone === 'primary'
                  ? 'bg-[#7A5AF8] text-white'
                  : spec.tone === 'danger'
                    ? 'border border-[#F04438]/40 text-[#F04438]'
                    : 'border border-black/10 dark:border-white/15';
              return (
                <button
                  key={s}
                  onClick={() => onAction(s)}
                  disabled={busy !== null}
                  className={`rounded-lg px-2.5 py-1.5 text-[12px] font-semibold disabled:opacity-40 ${cls}`}
                >
                  {busy === s ? 'Saving…' : spec.label}
                </button>
              );
            })}
          </div>
        )
      )}

      {!editor && state.next_states.some((s) => ACTION[s]?.editorOnly) && (
        <p className="mt-2 text-[11px] opacity-50">
          Further steps are the editor's to take.
        </p>
      )}
    </section>
  );
}

function Header() {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-[#ECE9FF] py-1 pl-2 pr-2.5 text-[11px] font-bold text-[#7A5AF8]">
      Production loop
    </span>
  );
}
