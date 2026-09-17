import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { priorityStyle } from '@/lib/score';
import { checkText } from '@/lib/api';
import { StatusPill, type PillTone } from './controls';
import { Emoji, type EmojiName } from './emoji';
import type { Issue, Priority } from '@/lib/types';
import type { GrammarIssue } from '@/lib/inline/types';

// Review Workspace — the primary editing surface. The Google Docs canvas won't let
// us draw on it, so we mirror the document onto our own canvas: flagged spans are
// highlighted, and hovering one pops a betterment card RIGHT NEXT TO the text (no
// scrolling to a list). Fixes apply to this local copy; "Copy corrected text"
// writes the result to the clipboard to paste back (no OAuth needed).

interface Mark {
  id: string;
  quote: string;
  title: string;
  detail: string;
  expected: string | null;
  bg: string;
  fg: string;
  tone: PillTone;
  pillLabel: string;
  icon: EmojiName;
  kind: 'editorial' | 'grammar';
}

const PRIORITY_TONE: Record<Priority, PillTone> = {
  critical: 'red',
  high: 'red',
  medium: 'amber',
  low: 'blue',
};

const SEVERITY: Record<string, { tone: PillTone; label: string; bg: string; fg: string }> = {
  spelling: { tone: 'red', label: 'Spelling', bg: '#FEE4E2', fg: '#D92D20' },
  grammar: { tone: 'red', label: 'Grammar', bg: '#FEE4E2', fg: '#D92D20' },
  punctuation: { tone: 'blue', label: 'Punctuation', bg: '#E0F2FE', fg: '#026AA2' },
  style: { tone: 'purple', label: 'Style', bg: '#ECE9FF', fg: '#6941C6' },
};

function findQuote(text: string, quote: string): number {
  if (!quote) return -1;
  const i = text.indexOf(quote);
  if (i >= 0) return i;
  return text.toLowerCase().indexOf(quote.toLowerCase());
}

function editorialMark(issue: Issue, i: number): Mark | null {
  if (!issue.quote) return null;
  const p = priorityStyle[issue.priority];
  return {
    id: `ed-${i}`,
    quote: issue.quote.trim(),
    title: issue.problem,
    detail: issue.explanation || issue.suggestion,
    expected: issue.options && issue.options.length ? issue.options[0] : null,
    bg: p.bg,
    fg: p.fg,
    tone: PRIORITY_TONE[issue.priority],
    pillLabel: p.label,
    icon: 'priority',
    kind: 'editorial',
  };
}

function grammarMark(text: string, g: GrammarIssue, i: number): Mark | null {
  const quote = text.slice(g.offset, g.offset + g.length).trim();
  if (!quote) return null;
  const s = SEVERITY[g.severity] ?? SEVERITY.style;
  return {
    id: `gr-${i}`,
    quote,
    title: g.short || g.message,
    detail: g.message,
    expected: g.replacements[0] ?? null,
    bg: s.bg,
    fg: s.fg,
    tone: s.tone,
    pillLabel: s.label,
    icon: 'pencil',
    kind: 'grammar',
  };
}

interface Seg {
  text: string;
  mark?: Mark;
  key: number;
}

function buildSegments(text: string, marks: Mark[]): Seg[] {
  const located = marks
    .map((m) => ({ m, start: findQuote(text, m.quote) }))
    .filter((x) => x.start >= 0)
    .map((x) => ({ ...x, end: x.start + x.m.quote.length }))
    .sort((a, b) => a.start - b.start);

  const segs: Seg[] = [];
  let cursor = 0;
  let key = 0;
  for (const { m, start, end } of located) {
    if (start < cursor) continue;
    if (start > cursor) segs.push({ text: text.slice(cursor, start), key: key++ });
    segs.push({ text: text.slice(start, end), mark: m, key: key++ });
    cursor = end;
  }
  if (cursor < text.length) segs.push({ text: text.slice(cursor), key: key++ });
  return segs;
}

export function ReviewCanvas({ text, issues }: { text: string; issues: Issue[] }) {
  const [work, setWork] = useState(text);
  const [grammar, setGrammar] = useState<GrammarIssue[]>([]);
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());
  const [copied, setCopied] = useState(false);
  const [hover, setHover] = useState<{ mark: Mark; rect: DOMRect } | null>(null);
  const closeTimer = useRef<number | undefined>(undefined);

  useEffect(() => {
    let alive = true;
    checkText(text)
      .then((r) => alive && setGrammar(r.issues))
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [text]);

  const allMarks = useMemo(() => {
    const ed = issues.map(editorialMark).filter(Boolean) as Mark[];
    const gr = grammar.map((g, i) => grammarMark(text, g, i)).filter(Boolean) as Mark[];
    return [...ed, ...gr];
  }, [issues, grammar, text]);

  const marks = useMemo(
    () => allMarks.filter((m) => !dismissed.has(m.id) && findQuote(work, m.quote) >= 0),
    [allMarks, dismissed, work],
  );
  const segs = useMemo(() => buildSegments(work, marks), [work, marks]);
  const edCount = marks.filter((m) => m.kind === 'editorial').length;
  const grCount = marks.filter((m) => m.kind === 'grammar').length;

  const openCard = (mark: Mark, el: HTMLElement) => {
    window.clearTimeout(closeTimer.current);
    setHover({ mark, rect: el.getBoundingClientRect() });
  };
  const scheduleClose = () => {
    window.clearTimeout(closeTimer.current);
    closeTimer.current = window.setTimeout(() => setHover(null), 160);
  };
  const keepOpen = () => window.clearTimeout(closeTimer.current);

  const apply = (m: Mark) => {
    if (m.expected) setWork((w) => w.replace(m.quote, m.expected!));
    setHover(null);
  };
  const dismiss = (id: string) => {
    setDismissed((s) => new Set(s).add(id));
    setHover(null);
  };
  const applyAll = () =>
    setWork((w) => {
      let out = w;
      for (const m of marks) if (m.expected && out.includes(m.quote)) out = out.replace(m.quote, m.expected);
      return out;
    });
  const dismissAll = () => setDismissed((s) => new Set([...s, ...marks.map((m) => m.id)]));
  const copyAll = () => {
    navigator.clipboard?.writeText(work).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <section className="card p-4">
      <div className="mb-2 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-bold">Review workspace</h3>
          <p className="ink-soft text-[11px]">
            {edCount + grCount > 0
              ? `${edCount} editorial · ${grCount} grammar — hover a highlight`
              : 'No outstanding highlights'}
          </p>
        </div>
        <button
          onClick={copyAll}
          className="rounded-full bg-gradient-to-br from-jalebi-500 to-jalebi-600 px-3 py-1.5 text-xs font-bold text-white shadow transition hover:brightness-105"
        >
          {copied ? '✓ Copied' : 'Copy corrected text'}
        </button>
      </div>

      {marks.length > 0 && (
        <div className="mb-2 flex gap-2">
          <button
            onClick={applyAll}
            className="rounded-full bg-black/[0.05] px-2.5 py-1 text-[11px] font-semibold transition hover:bg-black/10 dark:bg-white/10 dark:hover:bg-white/20"
          >
            Apply all fixes
          </button>
          <button
            onClick={dismissAll}
            className="rounded-full bg-black/[0.05] px-2.5 py-1 text-[11px] font-semibold transition hover:bg-black/10 dark:bg-white/10 dark:hover:bg-white/20"
          >
            Dismiss all
          </button>
        </div>
      )}

      <div className="max-h-[440px] overflow-y-auto whitespace-pre-wrap rounded-xl bg-black/[0.02] p-3 text-[13px] leading-relaxed dark:bg-white/[0.03]">
        {segs.map((s) =>
          s.mark ? (
            <mark
              key={s.key}
              onMouseEnter={(e) => openCard(s.mark!, e.currentTarget)}
              onMouseLeave={scheduleClose}
              className="cursor-help rounded px-0.5"
              style={{ background: s.mark.bg, color: 'inherit', boxShadow: `inset 0 -2px 0 ${s.mark.fg}` }}
            >
              {s.text}
            </mark>
          ) : (
            <span key={s.key}>{s.text}</span>
          ),
        )}
      </div>

      <p className="ink-soft mt-2 text-[10px] leading-relaxed">
        Edits apply to this copy only. When you're done, copy the corrected text and
        paste it back into your Google Doc.
      </p>

      {hover && (
        <BettermentPopover
          mark={hover.mark}
          rect={hover.rect}
          onEnter={keepOpen}
          onLeave={scheduleClose}
          onApply={() => apply(hover.mark)}
          onDismiss={() => dismiss(hover.mark.id)}
        />
      )}
    </section>
  );
}

// Floating card anchored to the hovered span. Self-measures and either sits below
// or flips above the span, and caps its own height with internal scroll — so it can
// never crop against the panel edge, however tall the content.
function BettermentPopover({
  mark,
  rect,
  onEnter,
  onLeave,
  onApply,
  onDismiss,
}: {
  mark: Mark;
  rect: DOMRect;
  onEnter: () => void;
  onLeave: () => void;
  onApply: () => void;
  onDismiss: () => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<{ top: number; left: number; maxH: number; ready: boolean }>({
    top: 0,
    left: 0,
    maxH: 9999,
    ready: false,
  });

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const M = 10; // viewport margin
    const vh = window.innerHeight;
    const vw = window.innerWidth;
    const w = el.offsetWidth;
    const h = el.offsetHeight;
    const below = vh - rect.bottom - M;
    const above = rect.top - M;

    let top: number;
    let maxH = vh - 2 * M;
    if (h <= below) {
      top = rect.bottom + 8; // fits below
    } else if (h <= above) {
      top = rect.top - h - 8; // flip above
    } else if (below >= above) {
      top = rect.bottom + 8; // more room below; scroll internally
      maxH = below - 6;
    } else {
      top = M; // more room above; pin to top, scroll internally
      maxH = above - 6;
    }
    const left = Math.max(M, Math.min(vw - w - M, rect.left));
    setPos({ top, left, maxH, ready: true });
  }, [rect, open, mark.id]);

  return (
    <div
      ref={ref}
      onMouseEnter={onEnter}
      onMouseLeave={onLeave}
      className="jalebi-pop fixed z-50 flex flex-col overflow-hidden rounded-2xl border border-black/10 bg-white shadow-2xl dark:border-white/10 dark:bg-zinc-900"
      style={{
        top: pos.top,
        left: pos.left,
        width: 'min(300px, calc(100vw - 20px))',
        maxHeight: pos.maxH,
        visibility: pos.ready ? 'visible' : 'hidden',
      }}
    >
      {/* Header (fixed) */}
      <div className="flex items-start gap-2.5 p-3 pb-2">
        <span
          className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-lg"
          style={{ background: mark.bg }}
        >
          <Emoji name={mark.icon} size={14} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="text-[13px] font-semibold leading-tight">{mark.title}</div>
          <div className="mt-1">
            <StatusPill tone={mark.tone} dot>
              {mark.pillLabel}
            </StatusPill>
          </div>
        </div>
        <button
          onClick={onDismiss}
          title="Dismiss"
          aria-label="Dismiss"
          className="grid h-6 w-6 shrink-0 place-items-center rounded-full text-zinc-400 transition hover:bg-black/[0.05] hover:text-zinc-700 dark:hover:bg-white/10"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" aria-hidden>
            <path d="M6 6l12 12M18 6L6 18" />
          </svg>
        </button>
      </div>

      {/* Body (scrolls if tall) */}
      <div className="min-h-0 flex-1 overflow-y-auto px-3">
        {mark.expected ? (
          <>
            <div className="ink-soft mb-1 text-[10px] font-bold uppercase tracking-wide">Expected</div>
            <p className="rounded-lg bg-black/[0.03] px-2.5 py-1.5 text-[12px] leading-relaxed dark:bg-white/[0.05]">
              {mark.expected}
            </p>
            <div
              style={{
                maxHeight: open ? 240 : 0,
                opacity: open ? 1 : 0,
                overflow: 'hidden',
                transition: 'max-height .22s ease, opacity .22s ease',
              }}
            >
              <div className="ink-soft mb-1 mt-2.5 text-[10px] font-bold uppercase tracking-wide">Why</div>
              <p className="ink-soft text-[12px] leading-relaxed">{mark.detail}</p>
            </div>
          </>
        ) : (
          // No auto-fix (e.g. needs a source) — show the guidance directly.
          <p className="text-[12px] leading-relaxed">{mark.detail}</p>
        )}
      </div>

      {/* Actions (fixed) */}
      <div className="flex items-center gap-2 p-3 pt-2">
        {mark.expected && (
          <button
            onClick={onApply}
            className="rounded-lg px-3 py-1.5 text-[12px] font-bold text-white"
            style={{ background: mark.fg }}
          >
            Apply
          </button>
        )}
        {mark.expected && (
          <button
            onClick={() => setOpen((o) => !o)}
            className="ink-soft rounded-lg px-2 py-1.5 text-[12px] font-semibold transition hover:bg-black/[0.05] dark:hover:bg-white/10"
          >
            {open ? 'Hide why' : 'Why?'}
          </button>
        )}
      </div>
    </div>
  );
}
