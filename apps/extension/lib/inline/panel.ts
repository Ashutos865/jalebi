// Floating Jalebi chip anchored to the focused field + a popover listing issues
// with one-click fixes. The overlay underlines are visual-only (click-through), so
// this panel is the interaction surface.

import { SEVERITY_COLOR, type GrammarIssue, type IssueHandlers } from './types';
import { logoSvg, BRAND } from '@/lib/logo';

const CHIP = 32;

const NOOP_HANDLERS: IssueHandlers = {
  apply: () => {},
  dismiss: () => {},
  addWord: () => {},
  requestRewrite: async () => ({ options: [], sentence: '', engine: '' }),
  applyRewrite: () => {},
};

export class SuggestionPanel {
  private chip: HTMLDivElement;
  private badge: HTMLSpanElement;
  private pop: HTMLDivElement;
  private open = false;

  constructor() {
    // Circular logo badge (like Grammarly's) with a count bubble.
    this.chip = document.createElement('div');
    Object.assign(this.chip.style, {
      position: 'fixed',
      zIndex: '2147483647',
      display: 'none',
      width: `${CHIP}px`,
      height: `${CHIP}px`,
      borderRadius: '50%',
      background: '#fff',
      boxShadow: '0 3px 12px rgba(0,0,0,.28)',
      alignItems: 'center',
      justifyContent: 'center',
      cursor: 'pointer',
    } as CSSStyleDeclaration);
    this.chip.innerHTML = logoSvg(20, BRAND, 8, true);

    this.badge = document.createElement('span');
    Object.assign(this.badge.style, {
      position: 'absolute',
      top: '-4px',
      right: '-4px',
      minWidth: '16px',
      height: '16px',
      padding: '0 4px',
      borderRadius: '9999px',
      background: '#ef4444',
      color: '#fff',
      font: '700 10px system-ui,sans-serif',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      boxSizing: 'border-box',
    } as CSSStyleDeclaration);
    this.chip.appendChild(this.badge);

    this.chip.addEventListener('mousedown', (e) => e.preventDefault()); // keep field focus
    this.chip.addEventListener('click', () => this.toggle());

    this.pop = document.createElement('div');
    Object.assign(this.pop.style, {
      position: 'fixed',
      zIndex: '2147483647',
      display: 'none',
      maxWidth: '340px',
      maxHeight: '320px',
      overflowY: 'auto',
      padding: '8px',
      borderRadius: '12px',
      background: '#fff',
      color: '#18181b',
      font: '13px system-ui,sans-serif',
      boxShadow: '0 12px 40px rgba(0,0,0,.22)',
      border: '1px solid rgba(0,0,0,.08)',
    } as CSSStyleDeclaration);
    this.pop.addEventListener('mousedown', (e) => e.preventDefault());

    document.body.append(this.chip, this.pop);
  }

  private issues: GrammarIssue[] = [];
  private handlers: IssueHandlers = NOOP_HANDLERS;

  update(fieldRect: DOMRect, issues: GrammarIssue[], handlers: IssueHandlers): void {
    this.issues = issues;
    this.handlers = handlers;
    if (issues.length === 0) {
      this.chip.style.display = 'none';
      this.pop.style.display = 'none';
      this.open = false;
      return;
    }
    this.badge.textContent = String(issues.length);
    this.chip.style.display = 'flex';
    this.position(fieldRect);
    if (this.open) this.renderPop(fieldRect);
  }

  reposition(fieldRect: DOMRect): void {
    if (this.chip.style.display !== 'none') this.position(fieldRect);
    if (this.open) this.renderPop(fieldRect);
  }

  private position(rect: DOMRect): void {
    const top = Math.min(window.innerHeight - CHIP - 6, rect.bottom + 6);
    const left = Math.max(8, Math.min(window.innerWidth - CHIP - 8, rect.right - CHIP));
    this.chip.style.top = `${top}px`;
    this.chip.style.left = `${left}px`;
  }

  private toggle(): void {
    this.open = !this.open;
    this.pop.style.display = this.open ? 'block' : 'none';
    if (this.open) {
      const r = this.chip.getBoundingClientRect();
      this.renderPop(new DOMRect(r.left, r.top - 6, r.width, 0));
    }
  }

  private renderPop(anchor: DOMRect): void {
    this.pop.textContent = '';
    for (const issue of this.issues) {
      const row = document.createElement('div');
      row.style.cssText =
        'padding:8px;border-bottom:1px solid rgba(0,0,0,.06);';
      const head = document.createElement('div');
      head.style.cssText = 'display:flex;gap:6px;align-items:center;margin-bottom:4px;';
      const dot = document.createElement('span');
      dot.style.cssText = `width:8px;height:8px;border-radius:9999px;background:${SEVERITY_COLOR[issue.severity]};flex:0 0 auto;`;
      const msg = document.createElement('span');
      msg.style.cssText = 'font-weight:600;line-height:1.3;';
      msg.textContent = issue.short || issue.message;
      head.append(dot, msg);
      row.appendChild(head);

      if (issue.context) {
        const ctx = document.createElement('div');
        ctx.style.cssText = 'color:#71717a;font-size:11px;margin-bottom:6px;';
        ctx.textContent = issue.context;
        row.appendChild(ctx);
      }

      const fixes = document.createElement('div');
      fixes.style.cssText = 'display:flex;flex-wrap:wrap;gap:5px;';
      if (issue.replacements.length === 0) {
        const none = document.createElement('span');
        none.style.cssText = 'color:#a1a1aa;font-size:11px;';
        none.textContent = 'No automatic fix';
        fixes.appendChild(none);
      }
      for (const rep of issue.replacements.slice(0, 4)) {
        const btn = document.createElement('button');
        btn.textContent = rep === ' ' ? '␣' : rep || '(remove)';
        btn.style.cssText =
          `border:0;border-radius:7px;padding:4px 9px;background:${BRAND};color:#fff;font:600 12px system-ui;cursor:pointer;`;
        btn.addEventListener('mousedown', (e) => e.preventDefault());
        btn.addEventListener('click', () => this.handlers.apply(issue, rep));
        fixes.appendChild(btn);
      }
      row.appendChild(fixes);

      // Dismiss + (for spelling) add-to-dictionary.
      const actions = document.createElement('div');
      actions.style.cssText = 'display:flex;gap:12px;margin-top:6px;';
      actions.appendChild(this.textButton('Dismiss', () => this.handlers.dismiss(issue)));
      if (issue.severity === 'spelling') {
        actions.appendChild(
          this.textButton('＋ Dictionary', () => this.handlers.addWord(issue)),
        );
      }
      row.appendChild(actions);

      this.pop.appendChild(row);
    }
    // Position popover below the chip, flipped up if it would overflow.
    this.pop.style.display = 'block';
    const ph = this.pop.offsetHeight;
    const below = anchor.bottom + 6;
    const top = below + ph > window.innerHeight ? Math.max(8, anchor.top - ph - 6) : below;
    this.pop.style.top = `${top}px`;
    this.pop.style.left = `${Math.max(8, Math.min(window.innerWidth - 348, anchor.left - 250))}px`;
  }

  private textButton(label: string, onClick: () => void): HTMLButtonElement {
    const b = document.createElement('button');
    b.textContent = label;
    b.style.cssText =
      'border:0;background:none;color:#71717a;font:600 11px system-ui;cursor:pointer;padding:0;';
    b.addEventListener('mousedown', (e) => e.preventDefault());
    b.addEventListener('click', onClick);
    return b;
  }

  destroy(): void {
    this.chip.remove();
    this.pop.remove();
  }
}
