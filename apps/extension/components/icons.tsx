// Device-independent inline SVG icons (no emoji fonts, no external images, no
// copyright). Monochrome line glyphs tinted per card — matching the reference UI.

export type IconName =
  | 'summary' | 'priority' | 'strengths' | 'steps' | 'breakdown' | 'detail'
  | 'chart' | 'target' | 'pencil' | 'grid' | 'book' | 'scale' | 'link'
  | 'globe' | 'eye' | 'heading' | 'search' | 'sparkle'
  | 'words' | 'model' | 'provider' | 'kb' | 'up' | 'down'
  | 'ruler' | 'write' | 'check' | 'cross' | 'warn' | 'clock' | 'user' | 'shield';

// 24×24, stroke-based, currentColor.
const PATHS: Record<IconName, JSX.Element> = {
  summary: <><path d="M4 6h16M4 12h16M4 18h11" /></>,
  priority: <><path d="M12 3 2 20h20L12 3Z" /><path d="M12 10v4M12 17h.01" /></>,
  strengths: <><path d="M20 6 9 17l-5-5" /></>,
  steps: <><path d="M5 12h14M13 5l7 7-7 7" /></>,
  breakdown: <><path d="M5 21V10M12 21V4M19 21v-7" /></>,
  detail: <><path d="M6 3h8l4 4v14H6zM14 3v4h4" /></>,
  chart: <><path d="M4 20h16M7 16v-4M12 16V8M17 16v-6" /></>,
  target: <><circle cx="12" cy="12" r="8" /><circle cx="12" cy="12" r="4" /><circle cx="12" cy="12" r="1" fill="currentColor" stroke="none" /></>,
  pencil: <><path d="M5 19l1-4L16 5l3 3L9 18l-4 1Z" /></>,
  grid: <><path d="M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z" /></>,
  book: <><path d="M5 4h11a2 2 0 0 1 2 2v14H7a2 2 0 0 1-2-2V4ZM18 6H8" /></>,
  scale: <><path d="M12 3v18M5 7h14M5 7l-2.5 6a2.5 2.5 0 0 0 5 0L5 7ZM19 7l-2.5 6a2.5 2.5 0 0 0 5 0L19 7Z" /></>,
  link: <><path d="M9 15l6-6M8.5 12 7 13.5a3 3 0 0 0 4 4l1.5-1.5M15.5 12 17 10.5a3 3 0 0 0-4-4L11.5 8" /></>,
  globe: <><circle cx="12" cy="12" r="8" /><path d="M4 12h16M12 4a12 12 0 0 1 0 16 12 12 0 0 1 0-16Z" /></>,
  eye: <><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7-10-7-10-7Z" /><circle cx="12" cy="12" r="2.5" /></>,
  heading: <><path d="M6 4v16M18 4v16M6 12h12" /></>,
  search: <><circle cx="11" cy="11" r="6" /><path d="M20 20l-4-4" /></>,
  sparkle: <><path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3Z" /></>,
  words: <><path d="M4 7h16M4 12h16M4 17h9" /></>,
  model: <><rect x="6" y="6" width="12" height="12" rx="2" /><path d="M9 3v3M15 3v3M9 18v3M15 18v3M3 9h3M3 15h3M18 9h3M18 15h3" /></>,
  provider: <><circle cx="12" cy="12" r="8" /><path d="M12 4v16M4 12h16" /></>,
  kb: <><path d="M6 4h11a1 1 0 0 1 1 1v15H7a1 1 0 0 1-1-1V4ZM6 16h12" /></>,
  up: <><path d="M12 19V5M6 11l6-6 6 6" /></>,
  down: <><path d="M12 5v14M6 13l6 6 6-6" /></>,
  ruler: <><path d="M3 15 15 3l6 6L9 21Z" /><path d="M7 11l2 2M10 8l2 2M13 5l2 2" /></>,
  write: <><path d="M4 20h16" /><path d="M6 16l1-3.5L15 4l3 3-8.5 8.5L6 16Z" /></>,
  check: <><path d="M20 6 9 17l-5-5" /></>,
  cross: <><path d="M18 6 6 18M6 6l12 12" /></>,
  warn: <><path d="M12 3 2 20h20L12 3Z" /><path d="M12 10v4M12 17h.01" /></>,
  clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  user: <><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></>,
  shield: <><path d="M12 3l8 3v6c0 4.5-3.2 8.3-8 9-4.8-.7-8-4.5-8-9V6l8-3Z" /></>,
};

export function Icon({
  name,
  size = 16,
  color,
  className,
  strokeWidth = 2,
}: {
  name: IconName;
  size?: number;
  color?: string;
  className?: string;
  strokeWidth?: number;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke={color || 'currentColor'}
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden
    >
      {PATHS[name]}
    </svg>
  );
}

// Dimension key → icon.
export const DIM_ICON: Record<string, IconName> = {
  research: 'chart', evidence: 'chart', accuracy: 'target', narrative: 'book',
  neutrality: 'scale', context: 'globe', structure: 'grid', writing: 'pencil',
  readability: 'eye', grammar: 'pencil', headline: 'heading', citations: 'link',
  formatting: 'grid', seo: 'search', engagement: 'sparkle',
};
