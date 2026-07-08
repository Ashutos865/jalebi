// Content script — runs on Google Docs.
// 1. Injects a floating "Jalebi" button that opens the side panel.
// 2. Answers the side panel's request for the document text via the export endpoint.

import { parseDocId, cleanTitle, fetchDocText } from '@/lib/doc';
import { logoSvg } from '@/lib/logo';
import type { DocPayload, JalebiMessage } from '@/lib/messaging';

export default defineContentScript({
  matches: ['https://docs.google.com/document/*'],
  runAt: 'document_idle',
  main() {
    injectFab();

    chrome.runtime.onMessage.addListener(
      (msg: JalebiMessage, _sender, sendResponse) => {
        if (msg?.type === 'JALEBI_EXTRACT_DOC') {
          extractDoc().then(sendResponse);
          return true; // async response
        }
        return undefined;
      },
    );
  },
});

async function extractDoc(): Promise<DocPayload> {
  const docId = parseDocId(location.href);
  if (!docId) return { ok: false, error: 'Not a Google Doc.' };

  // Prefer the background worker (cookies + host permission, no page CORS/CSP).
  let text = '';
  try {
    if (!chrome.runtime?.id) throw new Error('stale');
    const resp = (await chrome.runtime.sendMessage({
      type: 'JALEBI_FETCH_DOC',
      docId,
    })) as { ok: boolean; text?: string; error?: string };
    if (resp?.ok && resp.text) {
      text = resp.text;
    } else if (resp?.error) {
      // Fall back to a direct content-script fetch before giving up.
      try {
        text = await fetchDocText(docId);
      } catch (e) {
        return { ok: false, error: resp.error || (e instanceof Error ? e.message : String(e)) };
      }
    }
  } catch {
    try {
      text = await fetchDocText(docId);
    } catch (e) {
      return { ok: false, error: e instanceof Error ? e.message : String(e) };
    }
  }

  if (!text) return { ok: false, error: 'The document appears to be empty.' };
  return { ok: true, docId, title: cleanTitle(document.title), text, url: location.href };
}

function injectFab() {
  if (document.getElementById('jalebi-fab')) return;
  const btn = document.createElement('button');
  btn.id = 'jalebi-fab';
  btn.title = 'Evaluate with Jalebi';
  btn.setAttribute('aria-label', 'Evaluate with Jalebi');
  btn.innerHTML = logoSvg(30, undefined, 8, true);
  Object.assign(btn.style, {
    position: 'fixed',
    right: '20px',
    bottom: '20px',
    zIndex: '2147483647',
    width: '50px',
    height: '50px',
    borderRadius: '50%',
    border: '0',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    cursor: 'pointer',
    background: '#fff',
    boxShadow: '0 6px 20px rgba(0,0,0,0.25)',
  } as CSSStyleDeclaration);
  btn.addEventListener('click', () => {
    // Guard against a stale content script after an extension reload
    // ("Extension context invalidated"). Reloading the tab clears it.
    try {
      if (chrome.runtime?.id) {
        chrome.runtime.sendMessage({ type: 'JALEBI_OPEN_PANEL' });
      }
    } catch {
      /* extension was reloaded — reload the doc tab */
    }
  });
  document.body.appendChild(btn);
}
