// Regression tests for the stale-response race in FieldChecker.
//
// Offsets returned by the backend are only meaningful against the exact text they
// were computed from. Previously the only guard on a returned response was
// `destroyed`, so a slow check could resolve after a newer one and pair its
// offsets with the wrong snapshot — and the apply path then rewrote an unrelated
// span of the user's live text.

import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { GrammarIssue } from './types';

// Minimal chrome stub — the checker talks to the backend via the background worker.
let respond: (text: string) => Promise<{ ok: boolean; issues: GrammarIssue[] }>;

vi.stubGlobal('chrome', {
  runtime: {
    id: 'test-extension-id',
    sendMessage: (msg: { type: string; text: string }) => respond(msg.text),
  },
  storage: {
    local: { get: async () => ({}), set: async () => {} },
    onChanged: { addListener: () => {}, removeListener: () => {} },
  },
});

const { FieldChecker } = await import('./checker');

const issue = (over: Partial<GrammarIssue> = {}): GrammarIssue => ({
  offset: 0,
  length: 5,
  message: 'test',
  short: '',
  replacements: ['REPLACED'],
  rule: 'TEST_RULE',
  category: 'grammar',
  severity: 'grammar',
  context: '',
  ...over,
});

function makeTextarea(value: string): HTMLTextAreaElement {
  const el = document.createElement('textarea');
  el.value = value;
  document.body.appendChild(el);
  return el;
}

const deferred = <T,>() => {
  let resolve!: (v: T) => void;
  const promise = new Promise<T>((r) => (resolve = r));
  return { promise, resolve };
};

const tick = () => new Promise((r) => setTimeout(r, 0));

describe('FieldChecker stale-response race', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
    vi.useRealTimers();
  });

  it('drops an out-of-order response instead of pairing it with newer text', async () => {
    const el = makeTextarea('hello world');
    const slow = deferred<{ ok: boolean; issues: GrammarIssue[] }>();
    const fast = deferred<{ ok: boolean; issues: GrammarIssue[] }>();

    // The constructor schedules its own debounced run; answer anything before the
    // two requests this test cares about.
    respond = async () => ({ ok: true, issues: [] });
    const checker = new FieldChecker(el);
    const run = () => (checker as never as { run(): Promise<void> }).run();

    let n = 0;
    respond = () => (++n === 1 ? slow.promise : fast.promise);

    // Request A against the original text (kept pending).
    const aDone = run();
    // The user keeps typing; request B goes out against the new text.
    el.value = 'hello world, much later';
    const bDone = run();

    // B resolves first, then the stale A arrives late.
    fast.resolve({ ok: true, issues: [issue({ offset: 12, length: 4 })] });
    await bDone;
    slow.resolve({ ok: true, issues: [issue({ offset: 0, length: 5 })] });
    await aDone;
    await tick();

    // The snapshot must still be B's text, not A's.
    const snapshot = (checker as never as { text: string }).text;
    expect(snapshot).toBe('hello world, much later');
    checker.destroy();
  });

  it('does not write to the field when the snapshot is stale', async () => {
    const el = makeTextarea('teh cat sat');
    respond = async () => ({ ok: true, issues: [issue({ offset: 0, length: 3 })] });

    const checker = new FieldChecker(el);
    await (checker as never as { run(): Promise<void> }).run();
    await tick();

    // The user edits after the underline was drawn but before clicking the fix.
    el.value = 'a completely different sentence entirely';

    (checker as never as {
      apply(i: GrammarIssue, r: string): void;
    }).apply(issue({ offset: 0, length: 3 }), 'the');

    // The stale fix must be refused — the user's text is left exactly as typed.
    expect(el.value).toBe('a completely different sentence entirely');
    checker.destroy();
  });

  it('applies a fix normally when the snapshot is current', async () => {
    const el = makeTextarea('teh cat sat');
    respond = async () => ({ ok: true, issues: [issue({ offset: 0, length: 3 })] });

    const checker = new FieldChecker(el);
    await (checker as never as { run(): Promise<void> }).run();
    await tick();

    (checker as never as {
      apply(i: GrammarIssue, r: string): void;
    }).apply(issue({ offset: 0, length: 3 }), 'the');

    expect(el.value).toBe('the cat sat');
    checker.destroy();
  });

  it('refuses a stale sentence rewrite, which would destroy more text', async () => {
    const el = makeTextarea('This is wrong. A second sentence follows.');
    respond = async () => ({ ok: true, issues: [issue({ offset: 8, length: 5 })] });

    const checker = new FieldChecker(el);
    await (checker as never as { run(): Promise<void> }).run();
    await tick();

    el.value = 'Something else entirely now.';
    (checker as never as {
      applyRewrite(i: GrammarIssue, r: string): void;
    }).applyRewrite(issue({ offset: 8, length: 5 }), 'This is correct.');

    expect(el.value).toBe('Something else entirely now.');
    checker.destroy();
  });
});
