// Abstraction over the two editable-field kinds: <textarea>/<input> and
// contenteditable. Provides text access + range replacement, so the checker and
// overlay don't care which kind they're driving.

const INPUT_TYPES = new Set(['text', 'search', 'email', 'url', 'tel', '']);

// This content script runs on every site, and whatever a field contains is sent to
// the backend to be checked. Anything below is therefore never read: credentials,
// payment details and one-time codes must not leave the page.
const SENSITIVE_AUTOCOMPLETE =
  /(^|\s)(current-password|new-password|one-time-code|cc-(number|csc|exp|name|type|exp-month|exp-year))(\s|$)/i;

// Heuristics for "this is a real writing surface", not a search box or a PIN entry.
const MIN_CONTENTEDITABLE_WIDTH = 240;
const MIN_CONTENTEDITABLE_HEIGHT = 40;
const MIN_INPUT_LENGTH = 25; // maxlength below this is a code/postcode/PIN field

function isSensitiveField(el: HTMLElement): boolean {
  if (SENSITIVE_AUTOCOMPLETE.test(el.getAttribute('autocomplete') ?? '')) return true;
  // A field sitting in a login/payment form is treated as sensitive by association:
  // "confirm password" hints, security answers, and card fields often lack their own
  // autocomplete attribute.
  const form = el.closest('form');
  if (form?.querySelector('input[type="password"]')) return true;
  // Sites commonly mark sensitive inputs for their own tooling; respect that.
  if (el.closest('[data-sensitive], [data-private], .sensitive, .private')) return true;
  return false;
}

/** isContentEditable is not implemented everywhere (notably jsdom), so fall back
 *  to the attribute rather than treating `undefined` as "not editable". */
function contentEditable(el: HTMLElement): boolean {
  if (typeof el.isContentEditable === 'boolean') return el.isContentEditable;
  const attr = el.getAttribute('contenteditable');
  return attr === '' || attr === 'true' || attr === 'plaintext-only';
}

export function isEditable(el: Element | null): el is HTMLElement {
  if (!el || !(el instanceof HTMLElement)) return false;
  if (el.closest('[contenteditable="false"]')) return false;
  if (isSensitiveField(el)) return false;

  if (el instanceof HTMLTextAreaElement) return !el.readOnly && !el.disabled;

  if (el instanceof HTMLInputElement) {
    // type=password is excluded by INPUT_TYPES, but be explicit: this is the one
    // exclusion that must never regress if that set is edited later.
    if (el.type === 'password') return false;
    if (!INPUT_TYPES.has(el.type) || el.readOnly || el.disabled) return false;
    // A short maxlength means a code, PIN, postcode or OTP box — not prose.
    if (el.maxLength > 0 && el.maxLength < MIN_INPUT_LENGTH) return false;
    return true;
  }

  // Password managers and search widgets often mark small nodes editable. Require a
  // reasonable size so we only attach to genuine writing surfaces. (This check was
  // previously described in a comment here but never implemented.)
  if (!contentEditable(el)) return false;
  const rect = el.getBoundingClientRect();
  // A zero rect means detached or not yet laid out — allow it rather than silently
  // refusing to work in editors that mount hidden and are revealed on focus.
  if (rect.width === 0 && rect.height === 0) return true;
  return (
    rect.width >= MIN_CONTENTEDITABLE_WIDTH && rect.height >= MIN_CONTENTEDITABLE_HEIGHT
  );
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
