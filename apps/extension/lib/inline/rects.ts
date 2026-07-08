// Compute viewport rectangles for a [start,end) character span of an editable.
// - contenteditable: native Range.getClientRects() (already viewport coords).
// - <textarea>/<input>: the well-known "mirror div" caret technique.

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

function caretCoordinates(
  el: HTMLTextAreaElement | HTMLInputElement,
  position: number,
): Caret {
  const isInput = el.nodeName === 'INPUT';
  const style = window.getComputedStyle(el);
  const div = document.createElement('div');
  const s = div.style;
  s.position = 'absolute';
  s.visibility = 'hidden';
  s.whiteSpace = isInput ? 'pre' : 'pre-wrap';
  s.wordWrap = 'break-word';
  s.overflow = 'hidden';
  for (const p of MIRROR_PROPS) {
    s[p] = style[p];
  }
  if (isInput) s.width = 'auto';
  div.textContent = el.value.substring(0, position);
  if (isInput) div.textContent = div.textContent.replace(/\s/g, ' ');

  const span = document.createElement('span');
  span.textContent = el.value.substring(position) || '.';
  div.appendChild(span);
  document.body.appendChild(div);
  const caret: Caret = {
    top: span.offsetTop + parseFloat(style.borderTopWidth || '0'),
    left: span.offsetLeft + parseFloat(style.borderLeftWidth || '0'),
    height: parseFloat(style.lineHeight) || span.offsetHeight || 16,
  };
  document.body.removeChild(div);
  return caret;
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
    return Array.from(range.getClientRects());
  }

  const field = el as HTMLTextAreaElement | HTMLInputElement;
  const box = field.getBoundingClientRect();
  const from = caretCoordinates(field, start);
  const to = caretCoordinates(field, end);
  const ox = box.left - field.scrollLeft;
  const oy = box.top - field.scrollTop;

  // Same visual line → single rect. Different line (wrapped) → approximate with a
  // rect from the start caret to the field's right edge (short spans rarely wrap).
  if (Math.abs(to.top - from.top) < 1) {
    return [
      new DOMRect(ox + from.left, oy + from.top, Math.max(2, to.left - from.left), from.height),
    ];
  }
  const rightEdge = box.right - parseFloat(getComputedStyle(field).paddingRight || '0');
  return [new DOMRect(ox + from.left, oy + from.top, Math.max(2, rightEdge - (ox + from.left)), from.height)];
}
