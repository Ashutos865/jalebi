import { scoreBand, readinessStyle, priorityStyle } from '@/lib/score';
import type { Priority, PublicationReadiness } from '@/lib/types';

export function ScoreRing({ score, size = 128 }: { score: number; size?: number }) {
  const stroke = 10;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(100, score)) / 100;
  const { hex, label } = scoreBand(score);
  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="currentColor"
          strokeWidth={stroke}
          className="text-black/10 dark:text-white/10"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={hex}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - pct)}
          style={{ transition: 'stroke-dashoffset 0.9s cubic-bezier(0.22,1,0.36,1)' }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-3xl font-bold tabular-nums" style={{ color: hex }}>
          {score}
        </span>
        <span className="ink-soft text-[10px] font-medium uppercase tracking-wider">
          {label}
        </span>
      </div>
    </div>
  );
}

export function ReadinessBadge({ readiness }: { readiness: PublicationReadiness }) {
  const s = readinessStyle[readiness];
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold"
      style={{ background: s.bg, color: s.fg }}
    >
      <span className="h-2 w-2 rounded-full" style={{ background: s.dot }} />
      {readiness}
    </span>
  );
}

export function PriorityChip({ priority }: { priority: Priority }) {
  const s = priorityStyle[priority];
  return (
    <span
      className="rounded-md px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide"
      style={{ background: s.bg, color: s.fg }}
    >
      {s.label}
    </span>
  );
}

export function CategoryBar({ name, score }: { name: string; score: number }) {
  const { hex } = scoreBand(score);
  return (
    <div className="flex items-center gap-3">
      <span className="w-28 shrink-0 truncate text-xs font-medium">{name}</span>
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-black/10 dark:bg-white/10">
        <div
          className="h-full rounded-full"
          style={{
            width: `${score}%`,
            background: hex,
            transition: 'width 0.9s cubic-bezier(0.22,1,0.36,1)',
          }}
        />
      </div>
      <span className="w-8 shrink-0 text-right text-xs font-semibold tabular-nums">
        {score}
      </span>
    </div>
  );
}

export function Spinner({ className = '' }: { className?: string }) {
  return (
    <span
      className={`jalebi-spin inline-block rounded-full border-2 border-jalebi-500 border-t-transparent ${className}`}
    />
  );
}
