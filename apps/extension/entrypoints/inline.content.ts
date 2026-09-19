// Universal inline grammar/style layer — attaches to any editable field on any
// site (Gmail, LinkedIn, X, Notion, textareas, …). Google Docs' canvas editor is
// excluded (no standard editable target + the doc sidebar handles it).

import { isEditable } from '@/lib/inline/editable';
import { FieldChecker } from '@/lib/inline/checker';

const INLINE_FLAG = 'jalebi.inline';

export default defineContentScript({
  matches: ['<all_urls>'],
  excludeMatches: ['https://docs.google.com/document/*'],
  runAt: 'document_idle',
  async main() {
    // Respect the on/off toggle (default on). Guard against a dead context.
    let enabled = true;
    try {
      const stored = await chrome.storage.local.get(INLINE_FLAG);
      enabled = stored[INLINE_FLAG] !== false;
    } catch {
      return; // extension reloaded before this injected — nothing to do
    }

    let current: FieldChecker | null = null;
    let currentEl: HTMLElement | null = null;

    const detach = () => {
      current?.destroy();
      current = null;
      currentEl = null;
    };

    const onFocusIn = (e: Event) => {
      if (!enabled) return;
      const target = e.target as Element | null;
      if (isEditable(target) && target !== currentEl) {
        detach();
        currentEl = target;
        current = new FieldChecker(target);
      }
    };

    document.addEventListener('focusin', onFocusIn, true);

    // A focused field can leave the DOM without ever blurring: an SPA route
    // change, a modal closing, a Gmail compose window being sent. Nothing then
    // called destroy(), so the checker kept its window scroll/resize listeners,
    // its document-level pointer listener, its storage listener and three
    // orphaned body children — one full leak per field the user ever focused,
    // each still repositioning on every scroll. On a long-lived SPA that
    // accumulates for the whole session.
    // The callback is deliberately trivial — a busy SPA fires thousands of
    // mutations a second, so it exits immediately when nothing is attached, and
    // otherwise does one isConnected check (a cheap flag read, not a tree walk).
    // The observer is only armed while a field is attached.
    let pendingCheck = false;
    const observer = new MutationObserver(() => {
      if (!currentEl || pendingCheck) return;
      // Coalesce a burst of mutations into a single check next frame.
      pendingCheck = true;
      requestAnimationFrame(() => {
        pendingCheck = false;
        if (currentEl && !currentEl.isConnected) detach();
      });
    });
    observer.observe(document.documentElement, {
      childList: true,
      subtree: true,
    });

    // Live toggle from Settings. Kept so it can be removed on teardown.
    const onStorageChanged = (
      changes: Record<string, chrome.storage.StorageChange>,
      area: string,
    ) => {
      if (area === 'local' && INLINE_FLAG in changes) {
        enabled = changes[INLINE_FLAG].newValue !== false;
        if (!enabled) detach();
      }
    };
    chrome.storage.onChanged.addListener(onStorageChanged);

    // Tear everything down when the page goes away (including bfcache), so a
    // navigation does not leave listeners attached to a dead document.
    const teardown = () => {
      observer.disconnect();
      document.removeEventListener('focusin', onFocusIn, true);
      try {
        chrome.storage.onChanged.removeListener(onStorageChanged);
      } catch {
        /* extension context already gone */
      }
      detach();
    };
    window.addEventListener('pagehide', teardown, { once: true });
  },
});
