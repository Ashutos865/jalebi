import { useEffect, useState } from 'react';

export type ThemePref = 'system' | 'light' | 'dark';
const KEY = 'jalebi.theme';
const mql = () => window.matchMedia('(prefers-color-scheme: dark)');

/**
 * Theme with a persisted override that falls back to the OS setting.
 *
 * We always resolve to a concrete `data-theme` on <html> so that the CSS variables
 * *and* Tailwind's `dark:` variant (see @custom-variant in style.css) stay in sync,
 * even when the user overrides the OS preference.
 */
export function useTheme(): [ThemePref, (t: ThemePref) => void] {
  const [pref, setPref] = useState<ThemePref>('system');

  useEffect(() => {
    chrome.storage.local.get(KEY).then((v) => {
      const stored = (v[KEY] as ThemePref) || 'system';
      setPref(stored);
      apply(stored);
    });
    // Track OS changes while in "system" mode.
    const listener = () => setPref((p) => (apply(p), p));
    mql().addEventListener('change', listener);
    return () => mql().removeEventListener('change', listener);
  }, []);

  const update = (t: ThemePref) => {
    setPref(t);
    apply(t);
    chrome.storage.local.set({ [KEY]: t });
  };

  return [pref, update];
}

function apply(pref: ThemePref) {
  const resolved = pref === 'system' ? (mql().matches ? 'dark' : 'light') : pref;
  document.documentElement.setAttribute('data-theme', resolved);
}
