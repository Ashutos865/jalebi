// Google Docs / Drive integration — highlight problem lines and drop native,
// resolvable comments into the doc. Uses chrome.identity for the token (no separate
// login), the Docs API for highlights, and the Drive API for comments.
//
// Requires: manifest `oauth2` client_id (Chrome-Extension OAuth client) + scopes,
// the "identity" permission, and host permissions for *.googleapis.com.

import type { Issue } from './types';

const DOCS = 'https://docs.googleapis.com/v1/documents';
const DRIVE = 'https://www.googleapis.com/drive/v3/files';
const HL_COLOR = { red: 1, green: 0.85, blue: 0.4 }; // jalebi-ish highlight

export function getToken(interactive = true): Promise<string> {
  return new Promise((resolve, reject) => {
    chrome.identity.getAuthToken({ interactive }, (token) => {
      if (chrome.runtime.lastError || !token) {
        reject(new Error(chrome.runtime.lastError?.message || 'Google authorization failed'));
      } else {
        resolve(token as string);
      }
    });
  });
}

async function api(url: string, token: string, init?: RequestInit): Promise<any> {
  const res = await fetch(url, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`Google API ${res.status}: ${body.slice(0, 200)}`);
  }
  return res.status === 204 ? null : res.json();
}

/** Concatenate the doc's text runs, tracking each character's Docs index. */
function buildIndex(doc: any): { fullText: string; idx: number[] } {
  let fullText = '';
  const idx: number[] = [];
  for (const el of doc.body?.content ?? []) {
    const para = el.paragraph;
    if (!para) continue;
    for (const pe of para.elements ?? []) {
      const tr = pe.textRun;
      if (!tr || tr.content == null || pe.startIndex == null) continue;
      const text: string = tr.content;
      for (let i = 0; i < text.length; i++) {
        fullText += text[i];
        idx.push(pe.startIndex + i);
      }
    }
  }
  return { fullText, idx };
}

interface Range {
  startIndex: number;
  endIndex: number;
}

function highlightReq(r: Range) {
  return {
    updateTextStyle: {
      range: r,
      textStyle: { backgroundColor: { color: { rgbColor: HL_COLOR } } },
      fields: 'backgroundColor',
    },
  };
}

function clearReq(r: Range) {
  return {
    updateTextStyle: { range: r, textStyle: {}, fields: 'backgroundColor' },
  };
}

const HL_KEY = (docId: string) => `jalebi.hl.${docId}`;

export interface MarkResult {
  marked: number;
  commented: number;
  /** Quotes that could not be located in the document. */
  missed: number;
  /** Comments the Drive API rejected. Surfaced so a partial write is visible. */
  commentsFailed: number;
}

/** Highlight each issue's quoted line and add a resolvable comment with the fixes.
 *
 *  Writes are ordered: highlights first, comments only if that succeeded. The
 *  reverse order left comments in the user's document when highlighting failed,
 *  with nothing to undo them.
 */
export async function markIssuesInDoc(
  docId: string,
  issues: Issue[],
): Promise<MarkResult> {
  const token = await getToken(true);
  const doc = await api(`${DOCS}/${docId}`, token);
  const { fullText, idx } = buildIndex(doc);

  const requests: any[] = [];
  const ranges: Range[] = [];
  // Comments are *prepared* here and only sent after the highlights succeed —
  // see below.
  const pendingComments: { content: string; quote: string }[] = [];
  let missed = 0;

  for (const issue of issues) {
    const quote = (issue.quote || '').trim();
    if (!quote) continue;
    const s = fullText.indexOf(quote);
    if (s === -1) {
      missed++;
      continue;
    }
    const e = s + quote.length;
    const range = { startIndex: idx[s], endIndex: idx[e - 1] + 1 };
    requests.push(highlightReq(range));
    ranges.push(range);

    const opts =
      issue.options && issue.options.length
        ? '\n\nRewrite options:\n' +
          issue.options.map((o, i) => `${String.fromCharCode(65 + i)}. ${o}`).join('\n')
        : '';
    pendingComments.push({
      content: `Jalebi: ${issue.problem}\n${issue.suggestion}${opts}`,
      quote,
    });
  }

  if (!requests.length) {
    return { marked: 0, commented: 0, missed, commentsFailed: 0 };
  }

  // Highlights first. Comments used to be fired as the loop built the request
  // list, so a failing batchUpdate left comments already posted in the user's
  // document with nothing to roll them back. Ordering the writes means a failure
  // here leaves the document untouched.
  await api(`${DOCS}/${docId}:batchUpdate`, token, {
    method: 'POST',
    body: JSON.stringify({ requests }),
  });

  // Accumulate rather than replace: a second run used to overwrite the stored
  // ranges, so the first run's highlights could never be cleared again.
  const previous =
    ((await chrome.storage.local.get(HL_KEY(docId)))[HL_KEY(docId)] as Range[]) || [];
  await chrome.storage.local.set({ [HL_KEY(docId)]: mergeRanges(previous, ranges) });

  const results = await Promise.all(
    pendingComments.map((c) =>
      api(`${DRIVE}/${docId}/comments?fields=id`, token, {
        method: 'POST',
        body: JSON.stringify({
          content: c.content,
          quotedFileContent: { value: c.quote },
        }),
      })
        .then(() => true)
        .catch(() => false),
    ),
  );
  const commented = results.filter(Boolean).length;

  return {
    marked: requests.length,
    commented,
    missed,
    // Reported rather than swallowed: `commented` coming back lower than
    // `marked` used to be the only clue that anything had gone wrong.
    commentsFailed: results.length - commented,
  };
}

/** Union of stored and new highlight ranges, de-duplicated and ordered, so
 *  clearDocMarks can always undo everything Jalebi has drawn. */
function mergeRanges(previous: Range[], added: Range[]): Range[] {
  const seen = new Set<string>();
  const out: Range[] = [];
  for (const r of [...previous, ...added]) {
    const key = `${r.startIndex}:${r.endIndex}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(r);
  }
  return out.sort((a, b) => a.startIndex - b.startIndex);
}

/** Remove the highlights Jalebi added to this doc. */
export async function clearDocMarks(docId: string): Promise<{ cleared: number }> {
  const token = await getToken(true);
  const stored = (await chrome.storage.local.get(HL_KEY(docId)))[HL_KEY(docId)] as
    | Range[]
    | undefined;
  if (!stored || !stored.length) return { cleared: 0 };
  await api(`${DOCS}/${docId}:batchUpdate`, token, {
    method: 'POST',
    body: JSON.stringify({ requests: stored.map(clearReq) }),
  });
  await chrome.storage.local.remove(HL_KEY(docId));
  return { cleared: stored.length };
}
