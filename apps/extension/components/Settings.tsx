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
import { Eyebrow, ToggleSwitch, SettingRow, Legend, CircleButton } from './controls';
import { Icon } from './icons';

// How overall scores map to the publishing decision (Constitution §A bands).
const BAND_LEGEND = [
  { color: '#17B26A', label: '85+ Publish' },
  { color: '#2E90FA', label: '75–84 Minor edits' },
  { color: '#F79009', label: '60–74 Major edits' },
  { color: '#F04438', label: 'Below 60 Not ready' },
];

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
    let origin: string;
    try {
      origin = new URL(url).origin;
    } catch {
      setStatus('fail');
      return;
    }
    const isLocal = /^https?:\/\/(localhost|127\.0\.0\.1)(:|$)/.test(origin);
    // Document text is sent to this host, so refuse plaintext anywhere but a local
    // dev server. The manifest only grants https origins on demand, so an http URL
    // would otherwise fail later with no explanation.
    if (!isLocal && !origin.startsWith('https://')) {
      setStatus('fail');
      return;
    }
    await setBackendUrl(url);
    if (!isLocal) {
      try {
        await chrome.permissions.request({ origins: [`${origin}/*`] });
      } catch {
        /* user declined — checkHealth will report the failure */
      }
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
      {/* Header */}
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Icon name="model" size={16} />
          <h2 className="text-sm font-bold">Settings</h2>
        </div>
        <CircleButton variant="light" size={28} onClick={onClose} title="Close settings">
          <Icon name="cross" size={14} />
        </CircleButton>
      </div>

      {/* Account */}
      <div className="border-t border-black/[0.06] pt-1 dark:border-white/10">
        <SettingRow label="Account" hint={me ? `${me.email} · ${me.role}` : 'Sign in to sync & track'}>
          {me && (
            <button onClick={signOut} className="ink-soft text-xs font-semibold">
              Sign out
            </button>
          )}
        </SettingRow>
        {!me && (
          <div className="space-y-2 pb-2">
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
              className="rounded-full bg-jalebi-500 px-3 py-1.5 text-sm font-semibold text-white transition hover:bg-jalebi-600"
            >
              Sign in
            </button>
            {authErr && <span className="block text-xs text-rose-500">{authErr}</span>}
          </div>
        )}
      </div>

      {/* Inline checking */}
      <div className="border-t border-black/[0.06] dark:border-white/10">
        <SettingRow
          label="Inline checking on the web"
          hint="Underlines & fixes in any text field. Google Docs uses the sidebar."
        >
          <ToggleSwitch checked={inlineOn} onChange={toggleInline} />
        </SettingRow>
      </div>

      {/* Backend */}
      <div className="border-t border-black/[0.06] py-2 dark:border-white/10">
        <label className="mb-1.5 block text-[13px] font-semibold">Backend URL</label>
        <input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="http://127.0.0.1:8000"
          className={input}
        />
        <div className="mt-2 flex items-center gap-2">
          <button
            onClick={save}
            className="rounded-full bg-jalebi-500 px-3 py-1.5 text-sm font-semibold text-white transition hover:bg-jalebi-600"
          >
            Save & test
          </button>
          {status === 'checking' && <span className="ink-soft text-xs">Checking…</span>}
          {status === 'ok' && (
            <span className="inline-flex items-center gap-1 text-xs text-emerald-500">
              <Icon name="check" size={13} /> Connected
            </span>
          )}
          {status === 'fail' && (
            <span className="text-xs text-rose-500">Cannot reach backend</span>
          )}
        </div>
      </div>

      {/* Publishing guide — score-band legend */}
      <div className="border-t border-black/[0.06] pt-3 dark:border-white/10">
        <Eyebrow>Publishing guide</Eyebrow>
        <div className="mt-2">
          <Legend items={BAND_LEGEND} />
        </div>
      </div>
    </div>
  );
}
