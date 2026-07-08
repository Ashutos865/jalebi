// Background service worker.
// - Opens the side panel when the toolbar icon / in-page button is clicked.
// - Proxies grammar checks and Google-Doc fetches (holds host permissions + cookies,
//   so these aren't blocked by the host page's CORS/CSP).

import { checkText, rewriteText } from '@/lib/api';
import { fetchDocText } from '@/lib/doc';

export default defineBackground(() => {
  chrome.sidePanel
    .setPanelBehavior({ openPanelOnActionClick: true })
    .catch((err) => console.warn('[Jalebi] setPanelBehavior failed', err));

  // On (re)load/update, refresh open Google Doc tabs so their stale content script
  // is replaced by the new one — this eliminates "Extension context invalidated".
  chrome.runtime.onInstalled.addListener(() => {
    chrome.tabs
      .query({ url: 'https://docs.google.com/document/*' })
      .then((tabs) => {
        for (const t of tabs) if (t.id != null) chrome.tabs.reload(t.id);
      })
      .catch(() => {});
  });

  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    // Open the side panel for the FAB's tab (must run in the gesture's task).
    if (msg?.type === 'JALEBI_OPEN_PANEL' && sender.tab?.id != null) {
      chrome.sidePanel.open({ tabId: sender.tab.id }).catch((err) =>
        console.warn('[Jalebi] sidePanel.open failed', err),
      );
      return undefined;
    }

    // Inline grammar check.
    if (msg?.type === 'JALEBI_CHECK') {
      checkText(msg.text, msg.language)
        .then((r) => sendResponse({ ok: true, issues: r.issues, engine: r.engine }))
        .catch((e) => sendResponse({ ok: false, error: String(e) }));
      return true; // async
    }

    // On-demand AI rewrite of a sentence (user-triggered from a hover card).
    if (msg?.type === 'JALEBI_REWRITE') {
      rewriteText(msg.text, msg.goal, msg.context)
        .then((r) => sendResponse({ ok: true, options: r.options, engine: r.engine }))
        .catch((e) => sendResponse({ ok: false, error: String(e) }));
      return true; // async
    }

    // Google Doc plain-text export.
    if (msg?.type === 'JALEBI_FETCH_DOC') {
      fetchDocText(msg.docId)
        .then((text) => sendResponse({ ok: true, text }))
        .catch((e) =>
          sendResponse({ ok: false, error: e instanceof Error ? e.message : String(e) }),
        );
      return true; // async
    }

    return undefined;
  });
});
