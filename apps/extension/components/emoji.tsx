// Colorful, device-independent emoji rendered from bundled Twemoji SVGs
// (github.com/jdecked/twemoji, CC-BY 4.0 — see public/emoji/LICENSE). Because the
// art is packaged, every OS (Mac / Windows / Android / Linux) shows identical
// glyphs — unlike raw unicode, which renders per-platform. Apple's own emoji art
// is proprietary and cannot be redistributed, so Twemoji is the licensed stand-in.

// Semantic name → Twemoji codepoint filename.
const CP = {
  summary: '1f4cb', // 📋
  priority: '1f6a8', // 🚨
  strengths: '2705', // ✅
  steps: '1f680', // 🚀
  breakdown: '1f4ca', // 📊
  detail: '1f4c4', // 📄
  words: '270d', // ✍️
  provider: '1f916', // 🤖
  model: '2699', // ⚙️
  kb: '1f4da', // 📚
  chart: '1f4ca', // 📊
  target: '1f3af', // 🎯
  book: '1f4d6', // 📖
  scale: '2696', // ⚖️
  globe: '1f310', // 🌐
  grid: '1f9f1', // 🧱
  pencil: '1f58b', // 🖋️
  eye: '1f453', // 👓
  write: '270d', // ✍️
  heading: '1f4f0', // 📰
  link: '1f517', // 🔗
  ruler: '1f4d0', // 📐
  search: '1f50d', // 🔍
  sparkle: '2728', // ✨
} as const;

export type EmojiName = keyof typeof CP;

export function Emoji({
  name,
  size = 16,
  className,
}: {
  name: EmojiName;
  size?: number;
  className?: string;
}) {
  return (
    <img
      src={`/emoji/${CP[name]}.svg`}
      width={size}
      height={size}
      alt=""
      draggable={false}
      className={className}
      style={{ display: 'inline-block', verticalAlign: 'middle' }}
    />
  );
}

// Dimension key → emoji.
export const DIM_EMOJI: Record<string, EmojiName> = {
  research: 'chart', evidence: 'chart', accuracy: 'target', narrative: 'book',
  neutrality: 'scale', context: 'globe', structure: 'grid', writing: 'pencil',
  readability: 'eye', grammar: 'write', headline: 'heading', citations: 'link',
  formatting: 'ruler', seo: 'search', engagement: 'sparkle',
};
