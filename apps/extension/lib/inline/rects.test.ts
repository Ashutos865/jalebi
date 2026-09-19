// Underline geometry.
//
// jsdom performs no layout, so offsetTop/offsetLeft are always 0 and real
// pixel positions cannot be asserted here. What *can* be tested is the logic
// layered on top of the measurements, which is where the defects were:
//
//   * a wrapped span returned one rect covering only its first line;
//   * nothing was clipped to the field, so an underline for text scrolled out
//     of view was drawn over the surrounding page;
//   * the mirror div was created and destroyed twice per issue per render, each
//     time forcing a layout, on every scroll frame.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const rects = await import('./rects');

/** jsdom gives every element a zero rect; stub a real one. */
function withBox(el: HTMLElement, box: Partial<DOMRect>): HTMLElement {
  const full = {
    x: 0, y: 0, top: 0, left: 0, right: 0, bottom: 0, width: 0, height: 0,
    ...box,
  };
  el.getBoundingClientRect = () => ({ ...full, toJSON: () => full }) as DOMRect;
  return el;
}

function textarea(value: string): HTMLTextAreaElement {
  const el = document.createElement('textarea');
  el.value = value;
  document.body.appendChild(el);
  withBox(el, { top: 100, left: 50, right: 450, bottom: 200, width: 400, height: 100 });
  return el;
}

beforeEach(() => {
  document.body.innerHTML = '';
  rects.disposeMirror();
});

afterEach(() => {
  rects.disposeMirror();
  vi.restoreAllMocks();
});

describe('the shared mirror', () => {
  it('is reused across measurements rather than rebuilt', () => {
    const el = textarea('Some text in a field.');
    rects.rangeRects(el, true, 0, 4); // warm up: creates the one mirror

    const created = vi.spyOn(document, 'createElement');
    rects.rangeRects(el, true, 5, 9);
    rects.rangeRects(el, true, 10, 14);
    rects.rangeRects(el, true, 0, 20);

    // Three further calls, six caret measurements, no new mirror. Previously
    // each measurement built and destroyed its own div, forcing a layout — and
    // this runs for every issue on every scroll frame.
    expect(created.mock.calls.filter((c) => c[0] === 'div')).toHaveLength(0);
    expect(document.querySelectorAll('body > div').length).toBe(1);
  });

  it('is created once on first use', () => {
    const el = textarea('Some text.');
    expect(document.querySelectorAll('body > div').length).toBe(0);
    rects.rangeRects(el, true, 0, 4);
    expect(document.querySelectorAll('body > div').length).toBe(1);
  });

  it('is positioned off-screen so it cannot affect page layout', () => {
    rects.rangeRects(textarea('Some text.'), true, 0, 4);
    const div = document.querySelector('body > div') as HTMLElement;
    expect(div.style.position).toBe('absolute');
    expect(parseFloat(div.style.top)).toBeLessThan(0);
    expect(parseFloat(div.style.left)).toBeLessThan(0);
  });

  it('is removed by disposeMirror', () => {
    rects.rangeRects(textarea('Some text.'), true, 0, 4);
    expect(document.querySelectorAll('body > div').length).toBe(1);
    rects.disposeMirror();
    expect(document.querySelectorAll('body > div').length).toBe(0);
  });

  it('recreates itself after disposal', () => {
    const el = textarea('Some text.');
    rects.rangeRects(el, true, 0, 4);
    rects.disposeMirror();
    expect(() => rects.rangeRects(el, true, 0, 4)).not.toThrow();
    expect(document.querySelectorAll('body > div').length).toBe(1);
  });
});

describe('clipping to the field', () => {
  it('drops a rect that falls entirely outside the field box', () => {
    const el = textarea('Text scrolled far out of view.');
    // Push the caret measurement well below the field.
    Object.defineProperty(el, 'scrollTop', { value: 10_000, writable: true });
    const out = rects.rangeRects(el, true, 0, 5);
    // Either clipped away entirely, or clipped to lie within the box.
    const box = el.getBoundingClientRect();
    for (const r of out) {
      expect(r.top).toBeGreaterThanOrEqual(box.top - 0.5);
      expect(r.bottom).toBeLessThanOrEqual(box.bottom + 0.5);
    }
  });

  it('never returns a rect wider than the field', () => {
    const el = textarea('A much longer line of text than the field can show.');
    const box = el.getBoundingClientRect();
    for (const r of rects.rangeRects(el, true, 0, 40)) {
      expect(r.left).toBeGreaterThanOrEqual(box.left - 0.5);
      expect(r.right).toBeLessThanOrEqual(box.right + 0.5);
    }
  });

  it('returns only positive-area rects', () => {
    const el = textarea('Some text in a field.');
    for (const r of rects.rangeRects(el, true, 0, 10)) {
      expect(r.width).toBeGreaterThan(0);
      expect(r.height).toBeGreaterThan(0);
    }
  });
});

describe('robustness', () => {
  it('handles an empty field', () => {
    expect(() => rects.rangeRects(textarea(''), true, 0, 0)).not.toThrow();
  });

  it('handles a zero-length span', () => {
    const el = textarea('Some text.');
    expect(() => rects.rangeRects(el, true, 3, 3)).not.toThrow();
  });

  it('handles offsets past the end of the value', () => {
    const el = textarea('Short.');
    expect(() => rects.rangeRects(el, true, 0, 500)).not.toThrow();
  });

  it('returns nothing for a contenteditable with no resolvable range', () => {
    const div = document.createElement('div');
    div.setAttribute('contenteditable', 'true');
    document.body.appendChild(div);
    expect(rects.rangeRects(withBox(div, { width: 300, height: 80 }), false, 0, 5))
      .toEqual([]);
  });

  it('does not leave the mirror visible to the user', () => {
    rects.rangeRects(textarea('Some text.'), true, 0, 4);
    const div = document.querySelector('body > div') as HTMLElement;
    expect(div.style.visibility).toBe('hidden');
  });
});
