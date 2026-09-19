// Writing marks into the user's Google Doc.
//
// These are destructive operations on someone's real document, so the ordering
// and cleanup guarantees matter more than the happy path:
//
//   * Comments were fired while the highlight request list was still being
//     built, so a failing batchUpdate left comments already posted with nothing
//     to roll them back.
//   * Every comment failure was swallowed by .catch(() => null); a lower count
//     was the only clue.
//   * A second run overwrote the stored highlight ranges, so the first run's
//     highlights could never be cleared again.

import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { Issue } from './types';

const store: Record<string, unknown> = {};

vi.stubGlobal('chrome', {
  identity: {
    getAuthToken: (_opts: unknown, cb: (t: string) => void) => cb('test-token'),
  },
  runtime: { lastError: undefined },
  storage: {
    local: {
      get: async (k: string) => ({ [k]: store[k] }),
      set: async (o: Record<string, unknown>) => Object.assign(store, o),
      remove: async (k: string) => {
        delete store[k];
      },
    },
  },
});

const docs = await import('./docs');

const DOC_TEXT = 'Exports rose sharply in FY24. A second flagged sentence here.\n';

/** A Docs API document whose body yields DOC_TEXT. */
function docPayload() {
  return {
    body: {
      content: [
        {
          paragraph: {
            elements: [
              { startIndex: 1, textRun: { content: DOC_TEXT } },
            ],
          },
        },
      ],
    },
  };
}

const issue = (quote: string): Issue => ({
  problem: 'Unsourced figure',
  explanation: 'Attribute it.',
  impact: 'Reads as invented.',
  suggestion: 'Cite the source.',
  priority: 'high',
  quote,
  options: [],
});

interface Call {
  url: string;
  method: string;
}

/** Records call order so the ordering guarantee can be asserted. */
function stubFetch(opts: { failBatch?: boolean; failComments?: boolean } = {}) {
  const calls: Call[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init: RequestInit = {}) => {
      calls.push({ url, method: init.method || 'GET' });
      if (url.includes(':batchUpdate') && opts.failBatch) {
        return new Response('{"error":"nope"}', { status: 500 });
      }
      if (url.includes('/comments') && opts.failComments) {
        return new Response('{"error":"nope"}', { status: 403 });
      }
      if (url.includes('/comments')) {
        return new Response(JSON.stringify({ id: 'c1' }), { status: 200 });
      }
      if (url.includes(':batchUpdate')) {
        return new Response('{}', { status: 200 });
      }
      return new Response(JSON.stringify(docPayload()), { status: 200 });
    }),
  );
  return calls;
}

beforeEach(() => {
  for (const k of Object.keys(store)) delete store[k];
  vi.restoreAllMocks();
});

describe('markIssuesInDoc', () => {
  it('highlights before commenting', async () => {
    const calls = stubFetch();
    await docs.markIssuesInDoc('doc1', [issue('Exports rose sharply')]);

    const batch = calls.findIndex((c) => c.url.includes(':batchUpdate'));
    const comment = calls.findIndex((c) => c.url.includes('/comments'));
    expect(batch).toBeGreaterThanOrEqual(0);
    expect(comment).toBeGreaterThan(batch);
  });

  it('posts no comments at all when highlighting fails', async () => {
    const calls = stubFetch({ failBatch: true });
    await expect(
      docs.markIssuesInDoc('doc1', [issue('Exports rose sharply')]),
    ).rejects.toThrow();

    // The user's document is left untouched — no orphaned comments.
    expect(calls.some((c) => c.url.includes('/comments'))).toBe(false);
  });

  it('reports comment failures instead of hiding them', async () => {
    stubFetch({ failComments: true });
    const res = await docs.markIssuesInDoc('doc1', [issue('Exports rose sharply')]);

    expect(res.marked).toBe(1);
    expect(res.commented).toBe(0);
    expect(res.commentsFailed).toBe(1);
  });

  it('accumulates highlight ranges across runs', async () => {
    stubFetch();
    await docs.markIssuesInDoc('doc1', [issue('Exports rose sharply')]);
    await docs.markIssuesInDoc('doc1', [issue('A second flagged sentence')]);

    const stored = store['jalebi.hl.doc1'] as { startIndex: number }[];
    expect(stored).toHaveLength(2);
  });

  it('does not duplicate a range marked twice', async () => {
    stubFetch();
    await docs.markIssuesInDoc('doc1', [issue('Exports rose sharply')]);
    await docs.markIssuesInDoc('doc1', [issue('Exports rose sharply')]);

    expect((store['jalebi.hl.doc1'] as unknown[]).length).toBe(1);
  });

  it('counts quotes it cannot locate', async () => {
    stubFetch();
    const res = await docs.markIssuesInDoc('doc1', [issue('not in the document')]);
    expect(res.missed).toBe(1);
    expect(res.marked).toBe(0);
  });

  it('writes nothing when there is nothing to mark', async () => {
    const calls = stubFetch();
    const res = await docs.markIssuesInDoc('doc1', [issue('absent')]);
    expect(res.marked).toBe(0);
    expect(calls.some((c) => c.method === 'POST')).toBe(false);
  });
});

describe('clearDocMarks', () => {
  it('clears every range accumulated across runs', async () => {
    stubFetch();
    await docs.markIssuesInDoc('doc1', [issue('Exports rose sharply')]);
    await docs.markIssuesInDoc('doc1', [issue('A second flagged sentence')]);

    const res = await docs.clearDocMarks('doc1');
    expect(res.cleared).toBe(2);
    expect(store['jalebi.hl.doc1']).toBeUndefined();
  });

  it('is a no-op when nothing was marked', async () => {
    stubFetch();
    expect(await docs.clearDocMarks('doc-none')).toEqual({ cleared: 0 });
  });
});
