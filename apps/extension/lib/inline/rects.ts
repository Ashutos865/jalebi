// Viewport rectangles for a [start,end) character span of an editable field.
//
// - contenteditable: native Range.getClientRects(), which already returns one
//   rect per visual line in viewport coordinates.
// - <textarea>/<input>: the mirror-div technique, since neither exposes caret
//   geometry. A hidden div is styled to match the field, filled with the text up
//   to a character offset, and the resulting caret position measured.
//
// Four things this has to get right, each of which was previously wrong:
//
//   1. A wrapped span needs one rect per visual line. Returning a single rect
//      from the start caret to the right edge underlined one line of a
//      three-line span and drew over unrelated text on that line.
//   2. Rects must be clipped to the field's own box. A span scrolled out of view
//      in a textarea otherwise had its underline drawn floating over the page,
//      because the overlay is position:fixed with no clip.
//   3. The mirror must be positioned off-screen. Appending a visible-height
//      element to the body contributes to document height and can shift layout
//      or introduce a scrollbar on tight pages.
//   4. The mirror should be reused. It was created and destroyed twice per issue
//      per render, each time forcing a synchronous layout — and render() runs on
//      every scroll frame.

import { charRange } from './editable';

const MIRROR_PROPS = [
  'boxSizing', 'width', 'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft',
  'borderTopWidth', 'borderRightWidth', 'borderBottomWidth', 'borderLeftWidth',
  'fontFamily', 'fontSize', 'fontWeight', 'fontStyle', 'fontVariant', 'letterSpacing',
  'lineHeight', 'textTransform', 'wordSpacing', 'textIndent', 'textAlign', 'tabSize',
] as const;

interface Caret {
  top: number;
  left: number;
  height: number;
}

// One reusable mirror for the whole page. Creating and destroying it per
// measurement forced a layout each time, and rect computation runs for every
// issue on every scroll frame.
let mirror: HTMLDivElement | null = null;
let mirrorSpan: HTMLSpanElement | null = null;

function getMirror(): { div: HTMLDivElement; span: HTMLSpanElement } {
  if (!mirror || !mirror.isConnected) {
    mirror = document.createElement('div');
    mirrorSpan = document.createElement('span');
    mirror.appendChild(mirrorSpan);
    document.body.appendChild(mirror);
  }
  return { div: mirror, span: mirrorSpan! };
}

/** Release the shared mirror. Called when the last checker is torn down. */
export function disposeMirror(): void {
  mirror?.remove();
  mirror = null;
  mirrorSpan = null;
}

function caretCoordinates(
  el: HTMLTextAreaElement | HTMLInputElement,
  position: number,
): Caret {
  const isInput = el.nodeName === 'INPUT';
  const style = window.getComputedStyle(el);
  const { div, span } = getMirror();
  const s = div.style;

  s.position = 'absolute';
  // Off-screen rather than merely hidden: a visibility:hidden element still
  // occupies layout and can extend the document.
  s.top = '-9999px';
  s.left = '-9999px';
  s.visibility = 'hidden';
  s.whiteSpace = isInput ? 'pre' : 'pre-wrap';
  s.wordWrap = 'break-word';
  s.overflow = 'hidden';
  for (const p of MIRROR_PROPS) {
    s[p] = style[p];
  }
  if (isInput) s.width = 'auto';

  const before = el.value.substring(0, position);
  div.textContent = isInput ? before.replace(/\s/g, ' ') : before;
  // textContent replaced the span, so re-attach it.
  div.appendChild(span);
  span.textContent = el.value.substring(position) || '.';

  // line-height: normal parses as NaN. For a textarea the span's height is the
  // line box; for an input it is the full control height, so fall back to the
  // font size scaled by a typical leading instead of underlining the whole box.
  const fontSize = px(style.fontSize, 16);
  const fallbackHeight = Math.round(fontSize * 1.2);
  const lineHeight = px(style.lineHeight, NaN);
  const height = Number.isFinite(lineHeight)
    ? lineHeight
    : isInput
      ? fallbackHeight
      : span.offsetHeight || fallbackHeight;

  return {
    top: span.offsetTop + px(style.borderTopWidth),
    left: span.offsetLeft + px(style.borderLeftWidth),
    height,
  };
}

/** parseFloat over a computed style that may be '' or 'normal'. */
function px(value: string | null | undefined, fallback = 0): number {
  const n = parseFloat(value ?? '');
  return Number.isFinite(n) ? n : fallback;
}

/** Intersect `r` with the field's content box, dropping it if nothing remains.
 *  Without this, an underline for a span scrolled out of view is drawn over the
 *  surrounding page — the overlay is position:fixed and does not clip.
 *
 *  Also the last line of defence against a non-finite coordinate: a rect with a
 *  NaN edge would otherwise render as an invisible or full-width underline. */
function clipToField(r: DOMRect, box: DOMRect): DOMRect | null {
  const left = Math.max(r.left, box.left);
  const right = Math.min(r.right, box.right);
  const top = Math.max(r.top, box.top);
  const bottom = Math.min(r.bottom, box.bottom);
  if (![left, right, top, bottom].every(Number.isFinite)) return null;
  if (right - left < 1 || bottom - top < 1) return null;
  return new DOMRect(left, top, right - left, bottom - top);
}

export function rangeRects(
  el: HTMLElement,
  isInput: boolean,
  start: number,
  end: number,
): DOMRect[] {
  if (!isInput) {
    const range = charRange(el, start, end);
    if (!range) return [];
    // getClientRects already yields one rect per visual line; still clip, since
    // a contenteditable can scroll independently of the page.
    const box = el.getBoundingClientRect();
    return Array.from(range.getClientRects())
      .map((r) => clipToField(r, box))
      .filter((r): r is DOMRect => r !== null);
  }

  const field = el as HTMLTextAreaElement | HTMLInputElement;
  const box = field.getBoundingClientRect();
  const style = window.getComputedStyle(field);
  const from = caretCoordinates(field, start);
  const to = caretCoordinates(field, end);
  const ox = box.left - field.scrollLeft;
  const oy = box.top - field.scrollTop;

  const padLeft = px(style.paddingLeft);
  const padRight = px(style.paddingRight);
  const contentLeft = box.left + padLeft;
  const contentRight = box.right - padRight;

  const rects: DOMRect[] = [];

  if (Math.abs(to.top - from.top) < 1) {
    // Single visual line.
    rects.push(
      new DOMRect(
        ox + from.left,
        oy + from.top,
        Math.max(2, to.left - from.left),
        from.height,
      ),
    );
  } else {
    // Wrapped. Emit the first partial line, any full lines between, and the
    // final partial line — rather than one rect that covers only the first.
    rects.push(
      new DOMRect(
        ox + from.left,
        oy + from.top,
        Math.max(2, contentRight - (ox + from.left)),
        from.height,
      ),
    );

    const step = from.height || to.height || 16;
    for (let y = from.top + step; y < to.top - 0.5; y += step) {
      rects.push(
        new DOMRect(contentLeft, oy + y, Math.max(2, contentRight - contentLeft), step),
      );
    }

    rects.push(
      new DOMRect(
        contentLeft,
        oy + to.top,
        Math.max(2, ox + to.left - contentLeft),
        to.height,
      ),
    );
  }

  return rects
    .map((r) => clipToField(r, box))
    .filter((r): r is DOMRect => r !== null);
}
