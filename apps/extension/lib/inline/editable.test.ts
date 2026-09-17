// isEditable decides which fields get read and sent to the backend. This script
// runs on every site, so a false positive here means exfiltrating a password, a
// card number or a one-time code. These tests pin that boundary.

import { beforeEach, describe, expect, it } from 'vitest';
import { isEditable } from './editable';

// jsdom gives every element a zero rect, so contenteditable size checks need a stub.
function sized(el: HTMLElement, width: number, height: number): HTMLElement {
  el.getBoundingClientRect = () =>
    ({ width, height, top: 0, left: 0, right: width, bottom: height, x: 0, y: 0 }) as DOMRect;
  return el;
}

function input(attrs: Record<string, string> = {}): HTMLInputElement {
  const el = document.createElement('input');
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  document.body.appendChild(el);
  return el;
}

beforeEach(() => {
  document.body.innerHTML = '';
});

describe('sensitive fields are never read', () => {
  it('rejects password inputs', () => {
    expect(isEditable(input({ type: 'password' }))).toBe(false);
  });

  it('rejects one-time-code and password autocomplete hints', () => {
    for (const ac of ['one-time-code', 'current-password', 'new-password']) {
      expect(isEditable(input({ type: 'text', autocomplete: ac })), ac).toBe(false);
    }
  });

  it('rejects payment card fields', () => {
    for (const ac of ['cc-number', 'cc-csc', 'cc-exp', 'cc-name', 'cc-exp-month']) {
      expect(isEditable(input({ type: 'text', autocomplete: ac })), ac).toBe(false);
    }
  });

  it('rejects any field inside a form that contains a password', () => {
    const form = document.createElement('form');
    const user = document.createElement('input');
    user.type = 'text'; // the username box of a login form
    const pw = document.createElement('input');
    pw.type = 'password';
    form.append(user, pw);
    document.body.appendChild(form);
    expect(isEditable(user)).toBe(false);
  });

  it('rejects fields a site has marked sensitive', () => {
    const wrap = document.createElement('div');
    wrap.setAttribute('data-sensitive', '');
    const el = document.createElement('input');
    el.type = 'text';
    wrap.appendChild(el);
    document.body.appendChild(wrap);
    expect(isEditable(el)).toBe(false);
  });

  it('rejects short-maxlength inputs (PIN, OTP, postcode)', () => {
    expect(isEditable(input({ type: 'text', maxlength: '6' }))).toBe(false);
    expect(isEditable(input({ type: 'text', maxlength: '4' }))).toBe(false);
  });
});

describe('genuine writing surfaces are still read', () => {
  it('accepts a textarea', () => {
    const el = document.createElement('textarea');
    document.body.appendChild(el);
    expect(isEditable(el)).toBe(true);
  });

  it('accepts a normal text input with no maxlength', () => {
    expect(isEditable(input({ type: 'text' }))).toBe(true);
  });

  it('accepts a generous maxlength', () => {
    expect(isEditable(input({ type: 'text', maxlength: '500' }))).toBe(true);
  });

  it('accepts a large contenteditable', () => {
    const el = document.createElement('div');
    el.setAttribute('contenteditable', 'true');
    document.body.appendChild(el);
    expect(isEditable(sized(el, 600, 300))).toBe(true);
  });
});

describe('non-writing surfaces are skipped', () => {
  it('rejects a tiny contenteditable (search widget, tag chip)', () => {
    const el = document.createElement('div');
    el.setAttribute('contenteditable', 'true');
    document.body.appendChild(el);
    expect(isEditable(sized(el, 120, 20))).toBe(false);
  });

  it('rejects readonly and disabled fields', () => {
    expect(isEditable(input({ type: 'text', readonly: '' }))).toBe(false);
    expect(isEditable(input({ type: 'text', disabled: '' }))).toBe(false);
  });

  it('rejects non-text input types', () => {
    for (const t of ['checkbox', 'radio', 'file', 'range', 'color', 'date']) {
      expect(isEditable(input({ type: t })), t).toBe(false);
    }
  });

  it('rejects plain non-editable elements and null', () => {
    const div = document.createElement('div');
    document.body.appendChild(div);
    expect(isEditable(div)).toBe(false);
    expect(isEditable(null)).toBe(false);
  });
});
