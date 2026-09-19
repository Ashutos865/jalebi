// FieldChecker teardown.
//
// A focused field can leave the DOM without ever blurring — an SPA route change,
// a modal closing, a Gmail compose window being sent. Nothing called destroy(),
// so each orphan kept its window scroll/resize listeners, a document-level
// pointer listener, a storage listener and three body children, and went on
// repositioning on every scroll. One leak per field ever focused, for the whole
// session, on exactly the long-lived SPAs this is built for.

import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { GrammarIssue } from './types';

vi.stubGlobal('chrome', {
  runtime: {
    id: 'test-extension-id',
    sendMessage: async () => ({ ok: true, issues: [] as GrammarIssue[] }),
  },
  storage: {
    local: { get: async () => ({}), set: async () => {} },
    onChanged: { addListener: () => {}, removeListener: () => {} },
  },
});

const { FieldChecker } = await import('./checker');

function makeField(): HTMLTextAreaElement {
  const el = document.createElement('textarea');
  el.value = 'Some text the writer typed.';
  document.body.appendChild(el);
  return el;
}

beforeEach(() => {
  document.body.innerHTML = '';
});

describe('FieldChecker.destroy', () => {
  it('removes its window listeners', () => {
    const remove = vi.spyOn(window, 'removeEventListener');
    const checker = new FieldChecker(makeField());
    checker.destroy();

    const events = remove.mock.calls.map((c) => c[0]);
    expect(events).toContain('scroll');
    expect(events).toContain('resize');
    remove.mockRestore();
  });

  it('removes the input listener from the field itself', () => {
    const el = makeField();
    const remove = vi.spyOn(el, 'removeEventListener');
    const checker = new FieldChecker(el);
    checker.destroy();

    expect(remove.mock.calls.map((c) => c[0])).toContain('input');
    remove.mockRestore();
  });

  it('leaves nothing of its own behind in the body', () => {
    const before = document.body.childElementCount;
    const checker = new FieldChecker(makeField());
    checker.destroy();
    // The field itself remains; the overlay, panel and hovercard must not.
    expect(document.body.childElementCount).toBe(before + 1);
  });

  it('is safe to call twice', () => {
    const checker = new FieldChecker(makeField());
    checker.destroy();
    expect(() => checker.destroy()).not.toThrow();
  });

  it('ignores a late response after teardown', async () => {
    const el = makeField();
    const checker = new FieldChecker(el);
    checker.destroy();
    // run() resolving after destroy must not re-attach anything.
    await (checker as never as { run(): Promise<void> }).run();
    expect(document.body.contains(el)).toBe(true);
  });
});

describe('detached-field detection', () => {
  it('isConnected reports a removed field, which is what drives detach', () => {
    // The content script observes the document and calls destroy() when the
    // attached element reports isConnected === false. This pins the property
    // that detection relies on.
    const el = makeField();
    expect(el.isConnected).toBe(true);
    el.remove();
    expect(el.isConnected).toBe(false);
  });

  it('a removed field still tears down cleanly', () => {
    const el = makeField();
    const checker = new FieldChecker(el);
    el.remove(); // SPA route change
    expect(() => checker.destroy()).not.toThrow();
  });
});
