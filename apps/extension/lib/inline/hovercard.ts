// Hover card — the Grammarly-style popover that appears when the pointer is over
// an underlined span. We hit-test pointer position against each issue's rects
// (instead of putting interactive elements over the field, which would swallow
// clicks/selection). Offers one-click fixes, dismiss, and add-to-dictionary.

import { SEVERITY_COLOR, type GrammarIssue, type IssueRects, type IssueHandlers } from './types';
import { BRAND } from '@/lib/logo';

const SEVERITY_LABEL: Record<string, string> = {
  spelling: 'Spelling',
  grammar: 'Grammar',
  punctuation: 'Punctuation',
  style: 'Clarity',
};

export class HoverCards {
  private card: HTMLDivElement;
  private rewriteZone: HTMLDivElement | null = null;
  private data: IssueRects[] = [];
  private active: GrammarIssue | null = null;
  private overCard = false;
  private hideTimer: number | undefined;
  private rafPending = false;

  constructor(private handlers: IssueHandlers) {
    this.card = document.createElement('div');
    Object.assign(this.card.style, {
      position: 'fixed',
      zIndex: '2147483647',
      display: 'none',
      maxWidth: '320px',
      padding: '10px 12px',
      borderRadius: '12px',
      background: '#fff',
      color: '#18181b',
      font: '13px system-ui,-apple-system,sans-serif',
      boxShadow: '0 12px 40px rgba(0,0,0,.22)',
      border: '1px solid rgba(0,0,0,.08)',
    } as CSSStyleDeclaration);
    this.card.addEventListener('mousedown', (e) => e.preventDefault()); // keep field focus
    this.card.addEventListener('mouseenter', () => {
      this.overCard = true;
      clearTimeout(this.hideTimer);
    });
    this.card.addEventListener('mouseleave', () => {
      this.overCard = false;
      this.scheduleHide();
    });
    document.body.appendChild(this.card);
    document.addEventListener('mousemove', this.onMove, true);
  }

  /** Update the flagged spans to hit-test against; hide if the active one is gone. */
  setData(data: IssueRects[]): void {
    this.data = data;
    if (this.active && !data.some((d) => d.issue === this.active)) this.hide();
  }

  private onMove = (e: MouseEvent): void => {
    if (this.rafPending) return;
    this.rafPending = true;
    const x = e.clientX;
    const y = e.clientY;
    requestAnimationFrame(() => {
      this.rafPending = false;
      const hit = this.hitTest(x, y);
      if (hit) this.show(hit);
      else if (!this.overCard) this.scheduleHide();
    });
  };

  private hitTest(x: number, y: number): IssueRects | null {
    const pad = 3;
    for (const d of this.data) {
      for (const r of d.rects) {
        if (x >= r.left - pad && x <= r.right + pad && y >= r.top - pad && y <= r.bottom + pad) {
          return d;
        }
      }
    }
    return null;
  }

  private show(d: IssueRects): void {
    clearTimeout(this.hideTimer);
    if (this.active !== d.issue) {
      this.active = d.issue;
      this.render(d.issue);
    }
    const anchor = d.rects[0];
    this.card.style.display = 'block';
    const cw = this.card.offsetWidth;
    const ch = this.card.offsetHeight;
    let top = anchor.bottom + 8;
    if (top + ch > window.innerHeight) top = Math.max(8, anchor.top - ch - 8);
    const left = Math.max(8, Math.min(window.innerWidth - cw - 8, anchor.left));
    this.card.style.top = `${top}px`;
    this.card.style.left = `${left}px`;
  }

  private scheduleHide(): void {
    clearTimeout(this.hideTimer);
    this.hideTimer = window.setTimeout(() => {
      if (!this.overCard) this.hide();
    }, 160);
  }

  private hide(): void {
    this.card.style.display = 'none';
    this.active = null;
  }

  private render(issue: GrammarIssue): void {
    this.card.textContent = '';
    const color = SEVERITY_COLOR[issue.severity];

    const head = document.createElement('div');
    head.style.cssText = 'display:flex;gap:6px;align-items:center;margin-bottom:6px;';
    const tag = document.createElement('span');
    tag.style.cssText = `font:700 10px system-ui;text-transform:uppercase;letter-spacing:.06em;color:${color};`;
    tag.textContent = SEVERITY_LABEL[issue.severity] ?? issue.category;
    head.appendChild(tag);
    this.card.appendChild(head);

    const msg = document.createElement('div');
    msg.style.cssText = 'font-weight:600;line-height:1.35;margin-bottom:8px;';
    msg.textContent = issue.message || issue.short;
    this.card.appendChild(msg);

    const fixes = document.createElement('div');
    fixes.style.cssText = 'display:flex;flex-wrap:wrap;gap:6px;margin-bottom:8px;';
    for (const rep of issue.replacements.slice(0, 4)) {
      const btn = document.createElement('button');
      btn.textContent = rep === '' ? 'Remove' : rep === ' ' ? '␣ (single space)' : rep;
      btn.style.cssText =
        `border:0;border-radius:8px;padding:5px 11px;background:${BRAND};color:#fff;font:600 12px system-ui;cursor:pointer;`;
      btn.addEventListener('mousedown', (e) => e.preventDefault());
      btn.addEventListener('click', () => {
        this.handlers.apply(issue, rep);
        this.hide();
      });
      fixes.appendChild(btn);
    }
    if (issue.replacements.length === 0) {
      const none = document.createElement('span');
      none.style.cssText = 'color:#a1a1aa;font-size:12px;';
      none.textContent = 'No automatic fix — review manually.';
      fixes.appendChild(none);
    }
    this.card.appendChild(fixes);

    const actions = document.createElement('div');
    actions.style.cssText =
      'display:flex;gap:12px;align-items:center;border-top:1px solid rgba(0,0,0,.07);padding-top:7px;';
    // AI rewrite of the whole sentence (on demand — this is the one LLM call).
    const ai = this.textButton('✦ Rewrite with AI', () => this.runRewrite(issue));
    ai.style.color = BRAND;
    actions.appendChild(ai);
    actions.appendChild(
      this.textButton('Dismiss', () => {
        this.handlers.dismiss(issue);
        this.hide();
      }),
    );
    if (issue.severity === 'spelling') {
      actions.appendChild(
        this.textButton('＋ Dictionary', () => {
          this.handlers.addWord(issue);
          this.hide();
        }),
      );
    }
    this.card.appendChild(actions);

    // Zone the rewrite results render into (kept empty until requested).
    this.rewriteZone = document.createElement('div');
    this.card.appendChild(this.rewriteZone);
  }

  private async runRewrite(issue: GrammarIssue): Promise<void> {
    const zone = this.rewriteZone;
    if (!zone) return;
    zone.style.cssText = 'margin-top:8px;color:#71717a;font:600 12px system-ui;';
    zone.textContent = '✦ Rewriting…';
    const result = await this.handlers.requestRewrite(issue);
    // The user may have moved on; only paint if this card is still for this issue.
    if (this.active !== issue || !this.rewriteZone) return;
    if (result.options.length === 0) {
      zone.textContent =
        result.engine === 'unavailable'
          ? '✦ AI rewrite needs a live model (currently on mock).'
          : '✦ No cleaner rewrite found.';
      return;
    }
    zone.textContent = '';
    zone.style.cssText = 'margin-top:8px;border-top:1px dashed rgba(0,0,0,.1);padding-top:8px;';
    const label = document.createElement('div');
    label.style.cssText = 'font:700 10px system-ui;text-transform:uppercase;letter-spacing:.06em;color:' + BRAND + ';margin-bottom:6px;';
    label.textContent = '✦ AI rewrites';
    zone.appendChild(label);
    for (const opt of result.options) {
      const b = document.createElement('button');
      b.textContent = opt;
      b.style.cssText =
        'display:block;width:100%;text-align:left;border:1px solid rgba(0,0,0,.1);border-radius:9px;padding:7px 9px;margin-bottom:6px;background:#fafafa;color:#18181b;font:500 12px system-ui;line-height:1.35;cursor:pointer;';
      b.addEventListener('mousedown', (e) => e.preventDefault());
      b.addEventListener('mouseenter', () => (b.style.background = '#f4f4f5'));
      b.addEventListener('mouseleave', () => (b.style.background = '#fafafa'));
      b.addEventListener('click', () => {
        this.handlers.applyRewrite(issue, opt);
        this.hide();
      });
      zone.appendChild(b);
    }
  }

  private textButton(label: string, onClick: () => void): HTMLButtonElement {
    const b = document.createElement('button');
    b.textContent = label;
    b.style.cssText =
      'border:0;background:none;color:#71717a;font:600 12px system-ui;cursor:pointer;padding:0;';
    b.addEventListener('mousedown', (e) => e.preventDefault());
    b.addEventListener('click', onClick);
    return b;
  }

  destroy(): void {
    document.removeEventListener('mousemove', this.onMove, true);
    clearTimeout(this.hideTimer);
    this.card.remove();
  }
}
