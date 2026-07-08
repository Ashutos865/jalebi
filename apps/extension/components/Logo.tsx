import { SPIRAL_PATH, BRAND } from '@/lib/logo';

/** The Jalebi spiral mark as a React component (sidebar/dashboard headers). */
export function Logo({
  size = 28,
  color = BRAND,
  stroke = 8,
  spin = false,
}: {
  size?: number;
  color?: string;
  stroke?: number;
  spin?: boolean;
}) {
  return (
    <svg
      viewBox="0 0 100 100"
      width={size}
      height={size}
      fill="none"
      aria-label="Jalebi"
      style={
        spin
          ? { animation: 'jalebi-spin 6s linear infinite', transformOrigin: 'center' }
          : undefined
      }
    >
      <path
        d={SPIRAL_PATH}
        stroke={color}
        strokeWidth={stroke}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
