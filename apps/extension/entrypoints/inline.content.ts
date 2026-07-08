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

    // Live toggle from Settings.
    chrome.storage.onChanged.addListener((changes, area) => {
      if (area === 'local' && INLINE_FLAG in changes) {
        enabled = changes[INLINE_FLAG].newValue !== false;
        if (!enabled) detach();
      }
    });
  },
});
