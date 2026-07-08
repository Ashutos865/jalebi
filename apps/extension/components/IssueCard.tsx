import { useState } from 'react';
import { PriorityChip } from './ui';
import type { Issue } from '@/lib/types';

/** An editorial issue with concrete, grounded rewrite options. */
export function IssueCard({ issue, defaultOpen = false }: { issue: Issue; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  const [copied, setCopied] = useState<number | null>(null);
  const options = issue.options && issue.options.length ? issue.options : [];

  const copy = (text: string, i: number) => {
    navigator.clipboard?.writeText(text).catch(() => {});
    setCopied(i);
    setTimeout(() => setCopied(null), 1200);
  };

  return (
    <div className="rounded-2xl bg-black/[0.03] p-3 dark:bg-white/[0.04]">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-start gap-2 text-left"
      >
        <PriorityChip priority={issue.priority} />
        <span className="flex-1 text-sm font-semibold leading-snug">{issue.problem}</span>
        <span className="ink-soft mt-0.5 text-xs">{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <div className="mt-3 space-y-2.5 text-xs leading-relaxed">
          {issue.quote && (
            <blockquote className="border-l-2 border-jalebi-500 pl-2 italic ink-soft">
              “{issue.quote}”
            </blockquote>
          )}
          <Field label="Why" value={issue.explanation} />
          <Field label="Impact" value={issue.impact} />
          <Field label="Fix" value={issue.suggestion} accent />

          {options.length > 0 && (
            <div>
              <div className="mb-1 text-[10px] font-bold uppercase tracking-wide text-jalebi-600">
                Rewrite options
              </div>
              <div className="space-y-1.5">
                {options.map((opt, i) => (
                  <button
                    key={i}
                    onClick={() => copy(opt, i)}
                    title="Click to copy"
                    className="flex w-full items-start gap-2 rounded-lg border border-black/10 bg-white/40 px-2.5 py-1.5 text-left transition hover:border-jalebi-500 dark:border-white/10 dark:bg-white/5"
                  >
                    <span className="mt-px shrink-0 text-jalebi-500">
                      {String.fromCharCode(65 + i)}
                    </span>
                    <span className="flex-1">{opt}</span>
                    <span className="ink-soft shrink-0 text-[10px]">
                      {copied === i ? 'copied' : 'copy'}
                    </span>
                  </button>
                ))}
              </div>
              <p className="ink-soft mt-1 text-[10px]">
                Grounded in your text — bracketed placeholders like [figure] mean “add
                the real value”; Jalebi never invents facts.
              </p>
            </div>
          )}

          {options.length === 0 && issue.example && (
            <Field label="Example" value={issue.example} mono />
          )}
        </div>
      )}
    </div>
  );
}

function Field({
  label,
  value,
  accent,
  mono,
}: {
  label: string;
  value: string;
  accent?: boolean;
  mono?: boolean;
}) {
  return (
    <div>
      <span
        className={`mr-1.5 text-[10px] font-bold uppercase tracking-wide ${
          accent ? 'text-jalebi-600' : 'ink-soft'
        }`}
      >
        {label}
      </span>
      <span className={mono ? 'font-mono text-[11px]' : ''}>{value}</span>
    </div>
  );
}
