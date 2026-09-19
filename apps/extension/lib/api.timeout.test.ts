// Request budget.
//
// Without a timeout, a hung backend left the side panel on "Evaluating…"
// indefinitely — no error, no way to cancel, nothing in the console.

import { afterEach, describe, expect, it, vi } from 'vitest';

vi.stubGlobal('chrome', {
  storage: {
    local: {
      get: async () => ({ 'jalebi.backendUrl': 'https://backend.test' }),
      set: async () => {},
    },
  },
});

const api = await import('./api');

afterEach(() => {
  // Only the fetch stub is cleared — unstubbing everything would also remove
  // the `chrome` stub the module reads at call time.
  vi.restoreAllMocks();
  vi.useRealTimers();
});

function stubFetch(impl: (url: string, init: RequestInit) => Promise<Response>) {
  const spy = vi.fn(impl as never);
  vi.stubGlobal('fetch', spy);
  return spy;
}

/** A fetch that never settles until its signal aborts — a hung backend. */
function hangingFetch() {
  return stubFetch(
    (_url, init) =>
      new Promise<Response>((_resolve, reject) => {
        init.signal?.addEventListener('abort', () =>
          reject(new DOMException('Aborted', 'AbortError')),
        );
      }),
  );
}

describe('timeouts', () => {
  it('passes an abort signal on every request', async () => {
    const spy = stubFetch(async () =>
      new Response(JSON.stringify({ status: 'ok' }), { status: 200 }),
    );
    await api.checkHealth();
    const init = spy.mock.calls[0]![1] as RequestInit;
    expect(init.signal).toBeInstanceOf(AbortSignal);
  });

  it('gives up on a hung backend instead of waiting forever', async () => {
    vi.useFakeTimers();
    hangingFetch();

    const pending = api.checkHealth();
    // checkHealth swallows errors and returns false; without a timeout this
    // promise would never settle.
    await vi.advanceTimersByTimeAsync(6_000);
    await expect(pending).resolves.toBe(false);
  });

  it('reports a timeout in words a user can act on', async () => {
    vi.useFakeTimers();
    hangingFetch();

    const pending = api.fetchProviders();
    const assertion = expect(pending).rejects.toThrow(/did not respond in time/i);
    await vi.advanceTimersByTimeAsync(25_000);
    await assertion;
  });

  it('allows an evaluation longer than an ordinary call', async () => {
    vi.useFakeTimers();
    hangingFetch();

    const pending = api.evaluate({
      text: 'Exports rose.',
      content_type: 'analysis',
    } as never);
    const assertion = expect(pending).rejects.toThrow();

    // Still in flight well past the 20s default budget.
    await vi.advanceTimersByTimeAsync(30_000);
    // And it does eventually give up rather than hanging forever.
    await vi.advanceTimersByTimeAsync(160_000);
    await assertion;
  });

  it('turns an unreachable backend into a clear message', async () => {
    stubFetch(async () => {
      throw new TypeError('Failed to fetch');
    });
    await expect(api.fetchProviders()).rejects.toThrow(/Could not reach the backend/i);
  });

  it('clears its timer on a successful response', async () => {
    const clearSpy = vi.spyOn(globalThis, 'clearTimeout');
    stubFetch(async () =>
      new Response(JSON.stringify({ providers: [], active: 'mock' }), { status: 200 }),
    );
    await api.fetchProviders();
    expect(clearSpy).toHaveBeenCalled();
  });
});
