// Compatibility shim. Jalebi used bundled Twemoji SVGs for section markers and
// dimension glyphs; it now uses the stroke-based icon set in ./icons.tsx.
//
// Why the change: coloured emoji read as decoration. This is a tool editors use
// to decide whether something is fit to publish, and the interface should look
// like an editing desk rather than a chat app. Monochrome line icons also
// inherit currentColor, so they adapt to light/dark and to the accent colour of
// whatever section they sit in — which emoji bitmaps cannot.
//
// `Emoji` and `DIM_EMOJI` are kept as aliases so call sites did not all have to
// change in one commit; new code should import `Icon` from './icons' directly.

import { Icon, type IconName } from './icons';

export type EmojiName = IconName;

export function Emoji({
  name,
  size = 16,
  className,
}: {
  name: EmojiName;
  size?: number;
  className?: string;
}) {
  return <Icon name={name} size={size} className={className} />;
}

/** Dimension key → icon. Covers both the live scoring dimensions and the
 *  legacy rubric vocabulary, so older stored evaluations still render. */
export const DIM_EMOJI: Record<string, IconName> = {
  // Live scoring dimensions (app/scoring/constitution.py).
  accuracy: 'target',
  insight: 'sparkle',
  narrative: 'book',
  depth: 'search',
  sourcing: 'link',
  writing: 'pencil',
  headline: 'heading',
  // Legacy rubric keys, retained for historical evaluations.
  research: 'chart',
  evidence: 'chart',
  neutrality: 'scale',
  context: 'globe',
  structure: 'grid',
  readability: 'eye',
  grammar: 'write',
  citations: 'link',
  formatting: 'ruler',
  seo: 'search',
  engagement: 'sparkle',
};
