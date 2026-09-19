// Editorial "vitals" UI — iOS-style card system matching the reference:
// pastel pill labels, metric chips, ring gauges, gradient dimension bars, and a
// radial overall-score hero. Icons are device-independent inline SVG (see icons.tsx).
import type { ReactNode } from 'react';
import { Emoji, DIM_EMOJI, type EmojiName } from './emoji';
import type { CategoryScore, EvaluationResult } from '@/lib/types';

// Saturated → light vertical gradients for the dimension bars.
const BAR_PALETTE = [
  { from: '#FDB022', to: '#FEF0C7', text: '#B54708' },
  { from: '#F79009', to: '#FFEAD5', text: '#B54708' },
  { from: '#36BFFA', to: '#E0F2FE', text: '#0B7DB4' },
  { from: '#9E77ED', to: '#ECE9FF', text: '#6941C6' },
  { from: '#47CD89', to: '#DCFAE6', text: '#17864A' },
  { from: '#FD6F8E', to: '#FFE4E8', text: '#C11548' },
  { from: '#2ED3B7', to: '#CCFBEF', text: '#107569' },
  { from: '#EE46BC', to: '#FCE7F6', text: '#C11574' },
];

// Reference pastel shades: soft tint background + saturated text, per section.
export const PILL: Record<
  string,
  { bg: string; fg: string; emoji: EmojiName }
> = {
  summary: { bg: '#ECE9FF', fg: '#7A5AF8', emoji: 'summary' },
  priority: { bg: '#FFE7E5', fg: '#F04438', emoji: 'priority' },
  strengths: { bg: '#DCFAE6', fg: '#17B26A', emoji: 'strengths' },
  steps: { bg: '#E0F2FE', fg: '#2E90FA', emoji: 'steps' },
  breakdown: { bg: '#FFF0E1', fg: '#E8820C', emoji: 'breakdown' },
  detail: { bg: '#EFEFF2', fg: '#5D5D68', emoji: 'detail' },
};

// ── primitives ──────────────────────────────────────────────────────────────
export function SectionPill({
  label,
  tone,
}: {
  label: string;
  tone: { bg: string; fg: string; emoji: EmojiName };
}) {
  return (
    <span
      style={{ background: tone.bg, color: tone.fg }}
      className="inline-flex items-center gap-1.5 rounded-full py-1 pl-1.5 pr-2.5 text-[11px] font-bold"
    >
      <Emoji name={tone.emoji} size={14} />
      {label}
    </span>
  );
}

export function Chip({ icon, children }: { icon: EmojiName; children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-black/[0.05] px-1.5 py-0.5 align-middle dark:bg-white/10">
      <Emoji name={icon} size={12} />
      <span className="text-[12px] font-semibold">{children}</span>
    </span>
  );
}

export function RingGauge({
  value,
  size = 56,
  stroke = 5,
  color,
  label,
}: {
  value: number;
  size?: number;
  stroke?: number;
  color: string;
  label?: string;
}) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(100, value)) / 100;
  return (
    <div className="flex flex-col items-center gap-1">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90">
          <circle cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={stroke}
            stroke="currentColor" className="text-black/[0.08] dark:text-white/10" />
          <circle cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={stroke}
            stroke={color} strokeLinecap="round" strokeDasharray={c}
            strokeDashoffset={c * (1 - pct)}
            style={{ transition: 'stroke-dashoffset .9s cubic-bezier(.22,1,.36,1)' }} />
        </svg>
        <div className="absolute inset-0 grid place-items-center text-[13px] font-bold tabular-nums">
          {value}
        </div>
      </div>
      {label && (
        <span className="text-[8px] font-semibold uppercase tracking-wide ink-soft">
          {label}
        </span>
      )}
    </div>
  );
}

/** Score → colour, on the Constitution's own bands: >=85 ready, >=75 minor
 *  revision, >=60 major revision, below that not ready. One scale everywhere,
 *  so a colour always means the same thing. */
export function scoreColour(score: number): string {
  if (score >= 85) return '#17B26A';
  if (score >= 75) return '#2E90FA';
  if (score >= 60) return '#E8820C';
  return '#F04438';
}

// ── radial overall-score hero ────────────────────────────────────────────────
export function ScoreHero({ result }: { result: EvaluationResult }) {
  const top = [...result.categories].sort((a, b) => b.weight - a.weight).slice(0, 4);
  // Ring colour reflects each dimension's own score, so the reader sees where
  // the piece is weak at a glance rather than decoding an arbitrary palette.
  const ringColor = top.map((c) => scoreColour(c.score));
  const heroTint = scoreColour(result.overall_score);
  const pos = [
    'left-1/2 top-0 -translate-x-1/2',
    'right-0 top-1/2 -translate-y-1/2',
    'left-1/2 bottom-0 -translate-x-1/2',
    'left-0 top-1/2 -translate-y-1/2',
  ];
  return (
    <div className="relative mx-auto h-[240px] w-[240px]">
      {/* A single wash keyed to the score, not a rainbow: the colour should
          carry the verdict, not decorate the panel. */}
      <div
        className="absolute inset-[26%] rounded-full opacity-25"
        style={{ filter: 'blur(28px)', background: heroTint }}
      />
      <div className="absolute inset-0 grid place-items-center">
        <div className="text-center">
          <div className="display tnum text-[56px] leading-none">
            {result.overall_score}
          </div>
          <div className="ink-soft mt-1 text-[11px] uppercase tracking-[0.14em]">
            out of 100
          </div>
        </div>
      </div>
      {top.map((c, i) => (
        <div key={c.key} className={`absolute ${pos[i]}`}>
          <RingGauge value={c.score} color={ringColor[i]} label={c.name} />
        </div>
      ))}
    </div>
  );
}

// ── gradient dimension bars ──────────────────────────────────────────────────
export function GradientBars({ categories }: { categories: CategoryScore[] }) {
  const H = 168;
  return (
    <div className="flex items-end gap-1.5" style={{ height: H + 22 }}>
      {categories.map((c, i) => {
        const p = BAR_PALETTE[i % BAR_PALETTE.length];
        const barH = Math.max(38, Math.round((c.score / 100) * H));
        return (
          <div key={c.key} className="flex min-w-0 flex-1 flex-col items-center">
            <div className="relative flex w-full justify-center" style={{ height: H }}>
              <div className="absolute bottom-0" style={{
                width: '78%', maxWidth: 34, height: barH,
                borderRadius: '15px 15px 7px 7px',
                background: `linear-gradient(180deg, ${p.from} 0%, ${p.to} 100%)`,
              }}>
                <div className="absolute left-1/2 -translate-x-1/2 rounded-full bg-white px-1.5 py-px text-[9px] font-bold tabular-nums shadow-sm"
                  style={{ top: 6, color: p.text }}>
                  {c.score}
                </div>
                <div className="absolute left-1/2 grid h-[22px] w-[22px] -translate-x-1/2 place-items-center rounded-full bg-white shadow-sm"
                  style={{ bottom: 6 }}>
                  <Emoji name={DIM_EMOJI[c.key] ?? 'chart'} size={14} />
                </div>
              </div>
            </div>
            <span className="ink-soft mt-1 w-full truncate text-center text-[8.5px] font-medium leading-tight">
              {c.name}
            </span>
          </div>
        );
      })}
    </div>
  );
}
