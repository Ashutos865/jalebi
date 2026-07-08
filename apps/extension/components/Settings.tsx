import { useEffect, useState } from 'react';
import {
  getBackendUrl,
  setBackendUrl,
  checkHealth,
  login,
  logout,
  fetchMe,
  type AuthUser,
} from '@/lib/api';

export function Settings({ onClose }: { onClose: () => void }) {
  const [url, setUrl] = useState('');
  const [status, setStatus] = useState<'idle' | 'ok' | 'fail' | 'checking'>('idle');

  const [me, setMe] = useState<AuthUser | null>(null);
  const [email, setEmail] = useState('');
  const [secret, setSecret] = useState('');
  const [authErr, setAuthErr] = useState('');
  const [inlineOn, setInlineOn] = useState(true);

  useEffect(() => {
    getBackendUrl().then(setUrl);
    fetchMe().then(setMe).catch(() => setMe(null));
    chrome.storage.local
      .get('jalebi.inline')
      .then((v) => setInlineOn(v['jalebi.inline'] !== false));
  }, []);

  const toggleInline = async (on: boolean) => {
    setInlineOn(on);
    await chrome.storage.local.set({ 'jalebi.inline': on });
  };

  const save = async () => {
    await setBackendUrl(url);
    try {
      const origin = new URL(url).origin;
      if (!/^https?:\/\/(localhost|127\.0\.0\.1)/.test(origin)) {
        await chrome.permissions.request({ origins: [`${origin}/*`] });
      }
    } catch {
      /* invalid URL or user declined — checkHealth will report */
    }
    setStatus('checking');
    setStatus((await checkHealth()) ? 'ok' : 'fail');
  };

  const signIn = async () => {
    setAuthErr('');
    try {
      setMe(await login(email, secret));
      setSecret('');
    } catch (e) {
      setAuthErr(e instanceof Error ? e.message : 'Sign-in failed');
    }
  };

  const signOut = async () => {
    await logout();
    setMe(null);
  };

  const input =
    'w-full rounded-lg border border-black/10 bg-white/50 px-3 py-2 text-sm outline-none focus:border-jalebi-500 dark:border-white/10 dark:bg-white/5';

  return (
    <div className="card p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-xs font-bold uppercase tracking-wider ink-soft">Settings</h2>
        <button onClick={onClose} className="ink-soft text-xs" aria-label="Close settings">
          ✕
        </button>
      </div>

      {/* Account */}
      <label className="mb-1 block text-xs font-medium">Account</label>
      {me ? (
        <div className="mb-4 flex items-center justify-between rounded-lg bg-black/5 px-3 py-2 text-sm dark:bg-white/5">
          <span>
            {me.email} <span className="ink-soft">· {me.role}</span>
          </span>
          <button onClick={signOut} className="ink-soft text-xs">
            Sign out
          </button>
        </div>
      ) : (
        <div className="mb-4 space-y-2">
          <input
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@ties.org"
            className={input}
          />
          <input
            value={secret}
            onChange={(e) => setSecret(e.target.value)}
            type="password"
            placeholder="shared secret (if required)"
            className={input}
          />
          <button
            onClick={signIn}
            className="rounded-lg bg-jalebi-500 px-3 py-1.5 text-sm font-semibold text-white transition hover:bg-jalebi-600"
          >
            Sign in
          </button>
          {authErr && <span className="block text-xs text-rose-500">{authErr}</span>}
        </div>
      )}

      {/* Inline checking */}
      <label className="mb-2 flex items-center justify-between text-xs font-medium">
        <span>Inline grammar checking on the web</span>
        <input
          type="checkbox"
          checked={inlineOn}
          onChange={(e) => toggleInline(e.target.checked)}
          className="h-4 w-4 accent-jalebi-500"
        />
      </label>
      <p className="ink-soft mb-4 text-[11px]">
        Underlines issues and offers fixes in any text field (email, social, CMS…).
        Google Docs uses the sidebar instead.
      </p>

      {/* Backend */}
      <label className="mb-1 block text-xs font-medium">Backend URL</label>
      <input
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        placeholder="http://127.0.0.1:8000"
        className={input}
      />
      <div className="mt-3 flex items-center gap-2">
        <button
          onClick={save}
          className="rounded-lg bg-jalebi-500 px-3 py-1.5 text-sm font-semibold text-white transition hover:bg-jalebi-600"
        >
          Save & test
        </button>
        {status === 'checking' && <span className="ink-soft text-xs">Checking…</span>}
        {status === 'ok' && <span className="text-xs text-emerald-500">Connected ✓</span>}
        {status === 'fail' && (
          <span className="text-xs text-rose-500">Cannot reach backend</span>
        )}
      </div>
    </div>
  );
}
