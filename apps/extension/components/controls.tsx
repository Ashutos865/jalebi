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

// ── status pill (image 1: "Speeding" / "Exited the geofence") ────────────────
export type PillTone = 'red' | 'amber' | 'green' | 'blue' | 'gray' | 'purple';
const PILL_TONE: Record<PillTone, { bg: string; fg: string }> = {
  red: { bg: '#FEE4E2', fg: '#D92D20' },
  amber: { bg: '#FEF0C7', fg: '#B54708' },
  green: { bg: '#DCFAE6', fg: '#067647' },
  blue: { bg: '#E0F2FE', fg: '#026AA2' },
  gray: { bg: '#F2F4F7', fg: '#475467' },
  purple: { bg: '#ECE9FF', fg: '#6941C6' },
};

export function StatusPill({
  tone,
  dot,
  children,
}: {
  tone: PillTone;
  dot?: boolean;
  children: ReactNode;
}) {
  const t = PILL_TONE[tone];
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold"
      style={{ background: t.bg, color: t.fg }}
    >
      {dot && <span className="h-1.5 w-1.5 rounded-full" style={{ background: t.fg }} />}
      {children}
    </span>
  );
}

// ── legend (image 1: the km/h colour ranges) ─────────────────────────────────
export function Legend({ items }: { items: { color: string; label: string }[] }) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
      {items.map((it) => (
        <span key={it.label} className="inline-flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full" style={{ background: it.color }} />
          <span className="ink-soft text-[11px]">{it.label}</span>
        </span>
      ))}
    </div>
  );
}

// ── impact meter (image 2: the "Impact 46" slider) ───────────────────────────
export function ImpactMeter({
  label,
  value,
  max = 100,
  color = '#7A5AF8',
  suffix = '',
}: {
  label: string;
  value: number;
  max?: number;
  color?: string;
  suffix?: string;
}) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div className="flex items-center gap-2.5">
      <span className="w-24 shrink-0 truncate text-[12px] font-medium">{label}</span>
      <div className="relative h-1.5 flex-1 rounded-full bg-black/[0.06] dark:bg-white/10">
        <div
          className="absolute inset-y-0 left-0 rounded-full"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
      <span
        className="w-9 shrink-0 text-right text-[12px] font-bold tabular-nums"
        style={{ color }}
      >
        {value}
        {suffix}
      </span>
    </div>
  );
}

// ── iOS toggle switch ────────────────────────────────────────────────────────
export function ToggleSwitch({
  checked,
  onChange,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className="relative h-5 w-9 shrink-0 rounded-full transition-colors"
      style={{ background: checked ? '#7A5AF8' : 'rgba(0,0,0,0.16)' }}
    >
      <span
        className="absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-all"
        style={{ left: checked ? '18px' : '2px' }}
      />
    </button>
  );
}

// ── labelled control row for settings panels ─────────────────────────────────
export function SettingRow({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-3 py-2">
      <div className="min-w-0">
        <div className="text-[13px] font-semibold">{label}</div>
        {hint && <div className="ink-soft text-[11px] leading-snug">{hint}</div>}
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  );
}
