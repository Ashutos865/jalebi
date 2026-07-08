import type { ReactNode } from 'react';
import { Logo } from './Logo';
import type { ThemePref } from '@/lib/useTheme';

export function Header({
  theme,
  onThemeChange,
  onToggleSettings,
}: {
  theme: ThemePref;
  onThemeChange: (t: ThemePref) => void;
  onToggleSettings: () => void;
}) {
  const cycle = () => {
    const order: ThemePref[] = ['system', 'light', 'dark'];
    onThemeChange(order[(order.indexOf(theme) + 1) % order.length]);
  };
  const icon = theme === 'dark' ? '☾' : theme === 'light' ? '☀' : '◐';

  return (
    <header className="glass sticky top-0 z-10 flex items-center justify-between px-4 py-3">
      <div className="flex items-center gap-2.5">
        <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-white shadow-sm">
          <Logo size={26} spin />
        </div>
        <div className="leading-tight">
          <div className="text-sm font-bold">Jalebi</div>
          <div className="ink-soft text-[10px]">Editorial QA · TIES</div>
        </div>
      </div>
      <div className="flex items-center gap-1">
        <IconBtn label={`Theme: ${theme}`} onClick={cycle}>
          {icon}
        </IconBtn>
        <IconBtn label="Settings" onClick={onToggleSettings}>
          ⚙
        </IconBtn>
      </div>
    </header>
  );
}

function IconBtn({
  children,
  label,
  onClick,
}: {
  children: ReactNode;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      title={label}
      aria-label={label}
      className="flex h-8 w-8 items-center justify-center rounded-lg text-base transition hover:bg-black/5 dark:hover:bg-white/10"
    >
      {children}
    </button>
  );
}
