// Google Doc helpers — pure, unit-testable.

/** Extract the document id from a Google Docs URL. */
export function parseDocId(url: string): string | null {
  const m = url.match(/\/document\/d\/([a-zA-Z0-9_-]+)/);
  return m ? m[1] : null;
}

export function isGoogleDocUrl(url: string | undefined): boolean {
  return !!url && /^https:\/\/docs\.google\.com\/document\/d\//.test(url);
}

/** Strip Google's " - Google Docs" suffix from the tab title. */
export function cleanTitle(title: string): string {
  return title.replace(/\s*-\s*Google Docs$/i, '').trim();
}

/**
 * Fetch the document's plain text via the Docs export endpoint.
 *
 * This runs inside a content script on docs.google.com, so the request is
 * same-origin and carries the user's session cookies. It sidesteps canvas
 * rendering entirely — no DOM scraping, no OAuth, no Annotated-Canvas whitelist.
 */
export async function fetchDocText(docId: string): Promise<string> {
  const res = await fetch(
    `https://docs.google.com/document/d/${docId}/export?format=txt`,
    { credentials: 'include' },
  );
  if (!res.ok) {
    throw new Error(`Export failed (${res.status}). Make sure the doc is open and you can edit it.`);
  }
  const text = await res.text();
  // A login/redirect page comes back as HTML, not the doc.
  if (/^\s*<(!doctype|html)/i.test(text)) {
    throw new Error('Could not read the document text. Try reloading the doc.');
  }
  return text.trim();
}
