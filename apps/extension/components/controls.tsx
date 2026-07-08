// UI primitives extracted from the "habit-stats" reference mock:
// eyebrow labels, mixed-weight headlines, dark circular icon buttons, metric
// pills, a segmented pill toggle, and an embedded source card. Reused across the
// sidebar where each pattern fits.
import type { ReactNode } from 'react';
import { Emoji, type EmojiName } from './emoji';

// Tiny uppercase label that sits above a headline ("Statistics").
export function Eyebrow({ children }: { children: ReactNode }) {
  return (
    <span className="ink-soft text-[10px] font-bold uppercase tracking-[0.14em]">
      {children}
    </span>
  );
}

// Mixed-weight headline: light body text with bold emphasis spans + inline emoji,
// exactly like "Hello 👋 Taylor! your overall score exceeds the average."
export function Headline({ children }: { children: ReactNode }) {
  return (
    <h2 className="text-[22px] font-light leading-tight tracking-tight [&_b]:font-bold">
      {children}
    </h2>
  );
}

type CircleVariant = 'dark' | 'light' | 'brand';
const CIRCLE: Record<CircleVariant, string> = {
  dark: 'bg-zinc-900 text-white dark:bg-white dark:text-zinc-900',
  light:
    'bg-white text-zinc-700 border border-black/10 dark:bg-white/10 dark:text-zinc-200 dark:border-white/10',
  brand: 'text-white bg-gradient-to-br from-jalebi-500 to-jalebi-600 shadow-lg shadow-jalebi-600/30',
};

// Consistent 40px circular icon button (↗ ↻ = + in the mock).
export function CircleButton({
  children,
  onClick,
  disabled,
  variant = 'dark',
  size = 40,
  title,
}: {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  variant?: CircleVariant;
  size?: number;
  title?: string;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      title={title}
      aria-label={title}
      style={{ width: size, height: size }}
      className={`grid shrink-0 place-items-center rounded-full text-[15px] font-semibold transition active:scale-95 disabled:opacity-40 ${CIRCLE[variant]}`}
    >
      {children}
    </button>
  );
}

// White rounded pill: "🏆 Best result: 7/8".
export function MetricPill({
  emoji,
  label,
  value,
}: {
  emoji: EmojiName;
  label: string;
  value?: ReactNode;
}) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-black/[0.06] bg-white px-2.5 py-1 text-[11px] font-medium shadow-sm dark:border-white/10 dark:bg-white/[0.06]">
      <Emoji name={emoji} size={13} />
      <span className="ink-soft">{label}</span>
      {value != null && <b className="font-bold" style={{ color: 'rgb(var(--ink))' }}>{value}</b>}
    </span>
  );
}

// Segmented pill toggle — track with an active white pill (Weekly / Monthly).
export function SegmentedToggle<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { value: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div className="inline-flex items-center rounded-full bg-black/[0.06] p-0.5 dark:bg-white/10">
      {options.map((o) => {
        const active = o.value === value;
        return (
          <button
            key={o.value}
            onClick={() => onChange(o.value)}
            className={`rounded-full px-3 py-1 text-[11px] font-bold transition ${
              active
                ? 'bg-white text-zinc-900 shadow-sm dark:bg-zinc-100'
                : 'ink-soft hover:text-zinc-800 dark:hover:text-zinc-100'
            }`}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

// Embedded source card — favicon chip + title + host + meta pills. Maps the mock's
// "habiesjournal.com · 👁 2.8k" link card onto the Google Doc being reviewed.
export function SourceCard({
  title,
  host,
  wordCount,
  right,
}: {
  title: string;
  host?: string;
  wordCount?: number;
  right?: ReactNode;
}) {
  return (
    <div className="flex items-center gap-3">
      <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-sky-400 to-blue-500 text-white shadow-sm">
        <Emoji name="detail" size={17} />
      </span>
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-bold leading-tight">{title}</div>
        <div className="ink-soft mt-0.5 flex items-center gap-1.5 text-[11px]">
          {host && <span className="truncate">{host}</span>}
          {host && wordCount != null && <span>·</span>}
          {wordCount != null && <span className="shrink-0">{wordCount} words</span>}
        </div>
      </div>
      {right}
    </div>
  );
}
