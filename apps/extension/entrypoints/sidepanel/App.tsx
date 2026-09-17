import { useEffect, useState } from 'react';
import { Header } from '@/components/Header';
import { Settings } from '@/components/Settings';
import { Scorecard } from '@/components/Scorecard';
import { Spinner } from '@/components/ui';
import {
  Eyebrow,
  Headline,
  CircleButton,
  MetricPill,
  SourceCard,
  SegmentedToggle,
} from '@/components/controls';
import { ReviewCanvas } from '@/components/ReviewCanvas';
import { Emoji } from '@/components/emoji';
import { useTheme } from '@/lib/useTheme';
import {
  fetchContentTypes,
  fetchProviders,
  classifyContentType,
  evaluate,
} from '@/lib/api';
import { isGoogleDocUrl } from '@/lib/doc';
import { markIssuesInDoc, clearDocMarks } from '@/lib/docs';
import type { Issue } from '@/lib/types';
import { FALLBACK_CONTENT_TYPES } from '@/lib/contentTypes';
import type {
  ContentTypeOption,
  ContentTypeValue,
  EvaluationResult,
  ProviderOption,
} from '@/lib/types';
import type { DocPayload } from '@/lib/messaging';

type Phase = 'loading-doc' | 'ready' | 'evaluating' | 'done' | 'error';

export default function App() {
  const [theme, setTheme] = useTheme();
  const [showSettings, setShowSettings] = useState(false);

  const [phase, setPhase] = useState<Phase>('loading-doc');
  const [doc, setDoc] = useState<DocPayload | null>(null);
  const [error, setError] = useState<string>('');

  const [types, setTypes] = useState<ContentTypeOption[]>(FALLBACK_CONTENT_TYPES);
  const [contentType, setContentType] = useState<ContentTypeValue>('news_article');
  const [result, setResult] = useState<EvaluationResult | null>(null);

  const [providers, setProviders] = useState<ProviderOption[]>([]);
  const [provider, setProvider] = useState<string>('');
  const [detecting, setDetecting] = useState(false);
  const [marking, setMarking] = useState(false);
  const [markMsg, setMarkMsg] = useState('');
  const [resultView, setResultView] = useState<'report' | 'review'>('report');

  // Load content types + available AI providers from the backend.
  useEffect(() => {
    fetchContentTypes()
      .then((t) => t.length && setTypes(t))
      .catch(() => setTypes(FALLBACK_CONTENT_TYPES));
    fetchProviders()
      .then((p) => {
        const avail = p.providers.filter((x) => x.available);
        setProviders(avail);
        setProvider(p.active);
      })
      .catch(() => setProviders([]));
  }, []);

  const loadDoc = async () => {
    setPhase('loading-doc');
    setError('');
    try {
      const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
      if (!tab?.id || !isGoogleDocUrl(tab.url)) {
        setPhase('error');
        setError('Open a Google Doc, then reopen Jalebi.');
        return;
      }
      const payload = (await chrome.tabs.sendMessage(tab.id, {
        type: 'JALEBI_EXTRACT_DOC',
      })) as DocPayload;
      if (!payload?.ok) {
        setPhase('error');
        setError(payload?.error || 'Could not read the document. Try reloading the doc.');
        return;
      }
      setDoc(payload);
      setPhase('ready');
    } catch {
      setPhase('error');
      setError('Could not reach the document. Reload the Google Doc and try again.');
    }
  };

  useEffect(() => {
    loadDoc();
  }, []);

  const detectType = async () => {
    if (!doc?.text) return;
    setDetecting(true);
    try {
      const res = await classifyContentType(doc.text, doc.title);
      setContentType(res.content_type);
    } catch {
      /* leave the current selection */
    }
    setDetecting(false);
  };

  const issuesWithQuotes = (r: EvaluationResult): Issue[] => {
    const all = [...r.critical_issues, ...r.categories.flatMap((c) => c.issues)];
    const seen = new Set<string>();
    const out: Issue[] = [];
    for (const i of all) {
      if (i.quote && !seen.has(i.quote)) {
        seen.add(i.quote);
        out.push(i);
      }
    }
    return out;
  };

  const markInDoc = async () => {
    if (!doc?.docId || !result) return;
    setMarking(true);
    setMarkMsg('');
    try {
      const res = await markIssuesInDoc(doc.docId, issuesWithQuotes(result));
      setMarkMsg(
        `Highlighted ${res.marked} line(s) · ${res.commented} comment(s)` +
          (res.missed ? ` · ${res.missed} not located` : ''),
      );
    } catch (e) {
      setMarkMsg(e instanceof Error ? e.message : 'Failed to mark the doc.');
    }
    setMarking(false);
  };

  const clearMarks = async () => {
    if (!doc?.docId) return;
    setMarking(true);
    try {
      const res = await clearDocMarks(doc.docId);
      setMarkMsg(`Cleared ${res.cleared} highlight(s).`);
    } catch (e) {
      setMarkMsg(e instanceof Error ? e.message : 'Failed to clear.');
    }
    setMarking(false);
  };

  const runEvaluation = async () => {
    if (!doc?.text) return;
    setPhase('evaluating');
    setError('');
    try {
      const res = await evaluate({
        text: doc.text,
        content_type: contentType,
        title: doc.title,
        doc_id: doc.docId,
        doc_url: doc.url || null,
        provider: provider || null,
      });
      setResult(res);
      setPhase('done');
    } catch (e) {
      setPhase('error');
      setError(e instanceof Error ? e.message : 'Evaluation failed.');
    }
  };

  return (
    <div className="mx-auto flex h-full max-w-md flex-col">
      <Header
        theme={theme}
        onThemeChange={setTheme}
        onToggleSettings={() => setShowSettings((s) => !s)}
      />

      <main className="flex-1 space-y-4 overflow-y-auto p-4">
        {showSettings && <Settings onClose={() => setShowSettings(false)} />}

        {/* Greeting — eyebrow + mixed-weight headline */}
        {phase !== 'error' && (
          <div className="px-1 pt-1">
            <Eyebrow>Jalebi · Editorial QA</Eyebrow>
            <div className="mt-1.5">
              <Headline>
                {phase === 'done' ? (
                  <>
                    Here's how <b>{doc?.title || 'this doc'}</b> measures up{' '}
                    <Emoji name="target" size={20} />
                  </>
                ) : (
                  <>
                    Let's get this doc <b>publication-ready</b>{' '}
                    <Emoji name="sparkle" size={20} />
                  </>
                )}
              </Headline>
            </div>
            {phase === 'done' && result && (
              <div className="mt-3 flex flex-wrap gap-1.5">
                <MetricPill emoji="target" label="Score" value={`${result.overall_score}/100`} />
                <MetricPill
                  emoji={result.publication_ready ? 'strengths' : 'priority'}
                  label="Readiness"
                  value={result.publication_readiness}
                />
                {result.critical_issues.length > 0 && (
                  <MetricPill
                    emoji="priority"
                    label="Priority"
                    value={result.critical_issues.length}
                  />
                )}
              </div>
            )}
          </div>
        )}

        {/* Document + controls card */}
        {phase !== 'error' && (
          <div className="card p-4">
            <SourceCard
              title={doc?.title || (phase === 'loading-doc' ? 'Reading document…' : 'Untitled')}
              host={doc?.url ? new URL(doc.url).host : 'docs.google.com'}
              wordCount={doc?.text ? doc.text.split(/\s+/).filter(Boolean).length : undefined}
            />

            <div className="mb-1 mt-4 flex items-center justify-between">
              <label className="ink-soft text-[11px] font-semibold uppercase tracking-wide">
                Content type
              </label>
              <button
                onClick={detectType}
                disabled={!doc?.text || detecting || phase === 'evaluating'}
                className="text-[11px] font-semibold text-jalebi-600 transition hover:text-jalebi-500 disabled:opacity-40"
              >
                {detecting ? 'Detecting…' : '✨ Auto-detect'}
              </button>
            </div>
            <select
              value={contentType}
              onChange={(e) => setContentType(e.target.value as ContentTypeValue)}
              disabled={phase === 'evaluating'}
              className="mb-3 w-full rounded-lg border border-black/10 bg-white/50 px-3 py-2 text-sm outline-none focus:border-jalebi-500 dark:border-white/10 dark:bg-white/5"
            >
              {types.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>

            {providers.length > 1 && (
              <>
                <label className="ink-soft mb-1 block text-[11px] font-semibold uppercase tracking-wide">
                  AI model
                </label>
                <select
                  value={provider}
                  onChange={(e) => setProvider(e.target.value)}
                  disabled={phase === 'evaluating'}
                  className="mb-3 w-full rounded-lg border border-black/10 bg-white/50 px-3 py-2 text-sm outline-none focus:border-jalebi-500 dark:border-white/10 dark:bg-white/5"
                >
                  {providers.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.label}
                      {p.open_source ? ' · open source' : ''}
                    </option>
                  ))}
                </select>
              </>
            )}

            <button
              onClick={runEvaluation}
              disabled={phase === 'loading-doc' || phase === 'evaluating' || !doc?.text}
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-br from-jalebi-500 to-jalebi-600 px-4 py-2.5 text-sm font-bold text-white shadow-lg shadow-jalebi-600/30 transition hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {phase === 'evaluating' ? (
                <>
                  <Spinner className="h-4 w-4 border-white border-t-transparent" />
                  Evaluating…
                </>
              ) : phase === 'done' ? (
                'Re-evaluate'
              ) : (
                'Evaluate with Jalebi'
              )}
            </button>
          </div>
        )}

        {/* States */}
        {phase === 'loading-doc' && <LoadingDoc />}
        {phase === 'evaluating' && <Evaluating />}
        {phase === 'error' && <ErrorState message={error} onRetry={loadDoc} />}
        {phase === 'done' && result && (
          <>
            <div className="flex justify-center">
              <SegmentedToggle
                value={resultView}
                onChange={setResultView}
                options={[
                  { value: 'report', label: 'Report' },
                  { value: 'review', label: 'Review' },
                ]}
              />
            </div>

            {resultView === 'review' && doc?.text && (
              <ReviewCanvas text={doc.text} issues={issuesWithQuotes(result)} />
            )}

            {resultView === 'report' && (
              <>
                <div className="card p-3">
                  <div className="flex items-center gap-2">
                    <button
                      onClick={markInDoc}
                      disabled={marking}
                      className="flex flex-1 items-center justify-center gap-2 rounded-full bg-gradient-to-br from-jalebi-500 to-jalebi-600 px-4 py-2.5 text-xs font-bold text-white shadow-lg shadow-jalebi-600/30 transition hover:brightness-105 active:scale-[.99] disabled:opacity-50"
                    >
                      {marking ? (
                        <Spinner className="h-3.5 w-3.5 border-white border-t-transparent" />
                      ) : (
                        <Emoji name="pencil" size={14} />
                      )}
                      {marking ? 'Working…' : 'Highlight & comment in doc'}
                    </button>
                    <CircleButton
                      onClick={clearMarks}
                      disabled={marking}
                      variant="light"
                      title="Clear all highlights & comments"
                    >
                      ↺
                    </CircleButton>
                  </div>
                  {markMsg && <p className="ink-soft mt-2 px-1 text-[11px]">{markMsg}</p>}
                </div>
                <Scorecard result={result} />
              </>
            )}
          </>
        )}
      </main>
    </div>
  );
}

function LoadingDoc() {
  return (
    <div className="ink-soft flex flex-col items-center gap-3 py-12 text-sm">
      <Spinner className="h-6 w-6" />
      Reading your document…
    </div>
  );
}

function Evaluating() {
  const steps = ['Classifying content', 'Reviewing dimensions', 'Judging readiness'];
  return (
    <div className="card p-6">
      <div className="mb-4 flex items-center justify-center gap-2 text-sm font-semibold">
        <Spinner className="h-5 w-5" />
        Running the editorial pipeline
      </div>
      <ul className="space-y-2">
        {steps.map((s, i) => (
          <li
            key={s}
            className="jalebi-pulse flex items-center gap-2 text-xs"
            style={{ animationDelay: `${i * 0.2}s` }}
          >
            <span className="h-1.5 w-1.5 rounded-full bg-jalebi-500" />
            {s}
          </li>
        ))}
      </ul>
    </div>
  );
}

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="card flex flex-col items-center gap-3 p-8 text-center">
      <span className="text-2xl">⚠️</span>
      <p className="text-sm ink-soft">{message}</p>
      <button
        onClick={onRetry}
        className="rounded-lg bg-jalebi-500 px-4 py-1.5 text-sm font-semibold text-white transition hover:bg-jalebi-600"
      >
        Try again
      </button>
    </div>
  );
}
