import { useState } from 'react';
import type { ReactNode } from 'react';
import { IssueCard } from './IssueCard';
import { ScoreHero, GradientBars, SectionPill, Chip, PILL } from './vitals';
import { SegmentedToggle } from './controls';
import { Emoji, DIM_EMOJI } from './emoji';
import { scoreBand, readinessStyle } from '@/lib/score';
import type { CategoryScore, EvaluationResult } from '@/lib/types';

export function Scorecard({ result }: { result: EvaluationResult }) {
  return (
    <div className="space-y-4">
      {/* Hero — radial overall score + verdict */}
      <section className="card p-5">
        <ScoreHero result={result} />
        <Verdict result={result} />
      </section>

      {/* Summary with metric chips */}
      <section className="card p-4">
        <SectionPill label="Summary" tone={PILL.summary} />
        <p className="mt-3 text-sm leading-relaxed">{result.summary}</p>
        <div className="mt-3 flex flex-wrap gap-1.5">
          <Chip icon="words">{result.meta.word_count} words</Chip>
          <Chip icon="provider">{result.meta.evaluator}</Chip>
          {result.meta.model && <Chip icon="model">{result.meta.model}</Chip>}
          {result.meta.knowledge_used > 0 && (
            <Chip icon="kb">{result.meta.knowledge_used} SOP ref</Chip>
          )}
        </div>
      </section>

      {/* Priority issues */}
      {result.critical_issues.length > 0 && (
        <Card>
          <SectionPill
            label={`Priority · ${result.critical_issues.length}`}
            tone={PILL.priority}
          />
          <div className="mt-3 space-y-2">
            {result.critical_issues.map((issue, i) => (
              <IssueCard key={i} issue={issue} defaultOpen={i === 0} />
            ))}
          </div>
        </Card>
      )}

      {/* Strengths */}
      {result.strengths.length > 0 && (
        <Card>
          <SectionPill label="Strengths" tone={PILL.strengths} />
          <ul className="mt-3 space-y-1.5">
            {result.strengths.map((s, i) => (
              <li key={i} className="flex gap-2 text-sm">
                <span className="text-emerald-500">✓</span>
                <span>{s}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {/* Next steps */}
      {result.next_steps.length > 0 && (
        <Card>
          <SectionPill label="Next steps" tone={PILL.steps} />
          <ol className="mt-3 space-y-1.5">
            {result.next_steps.map((s, i) => (
              <li key={i} className="flex gap-2 text-sm">
                <span className="font-bold text-saffron-600">{i + 1}.</span>
                <span>{s}</span>
              </li>
            ))}
          </ol>
        </Card>
      )}

      {/* Dimension breakdown — gradient bars or compact list */}
      <BreakdownCard categories={result.categories} />

      {/* Detailed feedback */}
      {result.categories.some((c) => c.issues.length || c.recommendations.length) && (
        <Collapsible label="Detailed feedback" tone={PILL.detail}>
          <div className="space-y-3">
            {result.categories
              .filter((c) => c.issues.length || c.recommendations.length)
              .map((c) => (
                <CategoryDetail key={c.key} category={c} />
              ))}
          </div>
        </Collapsible>
      )}

      <p className="ink-soft pb-2 text-center text-[10px]">
        {result.meta.evaluator}
        {result.meta.model ? ` · ${result.meta.model}` : ''} · schema v
        {result.meta.schema_version}
      </p>
    </div>
  );
}

function Verdict({ result }: { result: EvaluationResult }) {
  const band = scoreBand(result.overall_score);
  const rs = readinessStyle[result.publication_readiness];
  const up = result.overall_score >= 80;
  const sub = result.publication_ready
    ? 'Meets TIES standards'
    : `${result.critical_issues.length} priority issue(s) to fix`;
  return (
    <div className="mt-3 flex items-center gap-3 rounded-2xl bg-black/[0.03] p-3 dark:bg-white/[0.04]">
      <div
        className="grid h-9 w-9 shrink-0 place-items-center rounded-full text-lg font-bold"
        style={{ background: up ? 'rgba(18,183,106,.14)' : 'rgba(240,68,56,.14)', color: up ? '#079455' : '#D92D20' }}
      >
        {up ? '↑' : '↓'}
      </div>
      <span
        className="shrink-0 rounded-full px-2 py-0.5 text-[11px] font-bold"
        style={{ background: band.hex + '22', color: band.hex }}
      >
        {band.label}
      </span>
      <div className="min-w-0">
        <div className="truncate text-sm font-bold" style={{ color: rs.fg }}>
          {result.publication_readiness}
        </div>
        <div className="ink-soft truncate text-[11px]">{sub}</div>
      </div>
    </div>
  );
}

function Card({ children }: { children: ReactNode }) {
  return <section className="card p-4">{children}</section>;
}

function BreakdownCard({ categories }: { categories: CategoryScore[] }) {
  const [view, setView] = useState<'bars' | 'list'>('bars');
  return (
    <Card>
      <div className="mb-3 flex items-center justify-between">
        <SectionPill label="Breakdown" tone={PILL.breakdown} />
        <SegmentedToggle
          value={view}
          onChange={setView}
          options={[
            { value: 'bars', label: 'Bars' },
            { value: 'list', label: 'List' },
          ]}
        />
      </div>
      {view === 'bars' ? (
        <GradientBars categories={categories} />
      ) : (
        <DimensionList categories={categories} />
      )}
    </Card>
  );
}

function DimensionList({ categories }: { categories: CategoryScore[] }) {
  const sorted = [...categories].sort((a, b) => a.score - b.score);
  return (
    <ul className="space-y-2.5">
      {sorted.map((c) => {
        const band = scoreBand(c.score);
        return (
          <li key={c.key} className="flex items-center gap-2.5">
            <Emoji name={DIM_EMOJI[c.key] ?? 'chart'} size={16} />
            <span className="w-24 shrink-0 truncate text-[12px] font-medium">{c.name}</span>
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-black/[0.06] dark:bg-white/10">
              <div
                className="h-full rounded-full"
                style={{ width: `${c.score}%`, background: band.hex }}
              />
            </div>
            <span className="w-7 shrink-0 text-right text-[12px] font-bold tabular-nums">
              {c.score}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

function CategoryDetail({ category }: { category: CategoryScore }) {
  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between">
        <span className="text-sm font-semibold">{category.name}</span>
        <span className="ink-soft text-xs tabular-nums">{category.score}/100</span>
      </div>
      <div className="space-y-2">
        {category.issues.map((issue, i) => (
          <IssueCard key={i} issue={issue} />
        ))}
        {category.recommendations.map((r, i) => (
          <p key={i} className="ink-soft flex gap-2 pl-1 text-xs">
            <span className="text-saffron-500">→</span>
            {r}
          </p>
        ))}
      </div>
    </div>
  );
}

function Collapsible({
  label,
  tone,
  children,
}: {
  label: string;
  tone: (typeof PILL)[keyof typeof PILL];
  children: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  return (
    <section className="card p-4">
      <button onClick={() => setOpen((o) => !o)} className="flex w-full items-center justify-between">
        <SectionPill label={label} tone={tone} />
        <span className="ink-soft text-xs">{open ? '▲' : '▼'}</span>
      </button>
      {open && <div className="mt-3">{children}</div>}
    </section>
  );
}
