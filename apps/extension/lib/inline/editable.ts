// Abstraction over the two editable-field kinds: <textarea>/<input> and
// contenteditable. Provides text access + range replacement, so the checker and
// overlay don't care which kind they're driving.

const INPUT_TYPES = new Set(['text', 'search', 'email', 'url', 'tel', '']);

export function isEditable(el: Element | null): el is HTMLElement {
  if (!el || !(el instanceof HTMLElement)) return false;
  if (el instanceof HTMLTextAreaElement) return !el.readOnly && !el.disabled;
  if (el instanceof HTMLInputElement) {
    return INPUT_TYPES.has(el.type) && !el.readOnly && !el.disabled;
  }
  // Password managers/search widgets often mark things editable we don't want;
  // require a reasonable size to avoid tiny one-line search boxes elsewhere.
  return el.isContentEditable;
}

export class EditableField {
  readonly el: HTMLElement;
  readonly isInput: boolean;

  constructor(el: HTMLElement) {
    this.el = el;
    this.isInput =
      el instanceof HTMLTextAreaElement || el instanceof HTMLInputElement;
  }

  getText(): string {
    if (this.isInput) return (this.el as HTMLInputElement).value;
    return this.el.textContent ?? '';
  }

  /** Replace [offset, offset+length) with `text` and fire an input event. */
  replaceRange(offset: number, length: number, text: string): void {
    if (this.isInput) {
      const input = this.el as HTMLInputElement | HTMLTextAreaElement;
      input.setRangeText(text, offset, offset + length, 'end');
      input.dispatchEvent(new Event('input', { bubbles: true }));
      return;
    }
    const range = charRange(this.el, offset, offset + length);
    if (!range) return;
    range.deleteContents();
    range.insertNode(document.createTextNode(text));
    this.el.dispatchEvent(new Event('input', { bubbles: true }));
  }
}

/** Build a DOM Range spanning [start, end) characters of a contenteditable. */
export function charRange(root: HTMLElement, start: number, end: number): Range | null {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let pos = 0;
  const range = document.createRange();
  let startSet = false;
  let node = walker.nextNode() as Text | null;
  while (node) {
    const len = node.data.length;
    if (!startSet && pos + len >= start) {
      range.setStart(node, Math.max(0, start - pos));
      startSet = true;
    }
    if (startSet && pos + len >= end) {
      range.setEnd(node, Math.max(0, end - pos));
      return range;
    }
    pos += len;
    node = walker.nextNode() as Text | null;
  }
  return startSet ? range : null;
}
