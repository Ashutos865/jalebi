// Per-field orchestrator: debounce typing → ask the backend → draw underlines +
// update the hover cards and summary panel. Filters out anything the user has
// dismissed (this session) or added to their personal dictionary (persistent).
// One instance per focused editable field.

import { EditableField } from './editable';
import { UnderlineLayer, type Underline } from './overlay';
import { SuggestionPanel } from './panel';
import { HoverCards } from './hovercard';
import { rangeRects } from './rects';
import {
  SEVERITY_COLOR,
  type GrammarIssue,
  type IssueRects,
  type IssueHandlers,
  type RewriteResult,
} from './types';
import { loadDict, addWord, onDictChange } from './dictionary';

const DEBOUNCE_MS = 550;
const MAX_LEN = 20000;

export class FieldChecker {
  private field: EditableField;
  private layer = new UnderlineLayer();
  private panel = new SuggestionPanel();
  private hover: HoverCards;
  private timer: number | undefined;
  private allIssues: GrammarIssue[] = []; // everything the backend returned
  private issues: GrammarIssue[] = []; // after dictionary + dismiss filtering
  private text = ''; // snapshot the current issues were computed against
  private dict = new Set<string>();
  private dismissed = new Set<string>(); // session-only, keyed by rule+span text
  private unsubDict: () => void;
  private destroyed = false;
  private rafPending = false;

  private onInput = () => this.schedule();
  private onScroll = () => this.throttledReposition();

  constructor(el: HTMLElement) {
    this.field = new EditableField(el);
    this.hover = new HoverCards(this.buildHandlers());
    el.addEventListener('input', this.onInput);
    window.addEventListener('scroll', this.onScroll, true);
    window.addEventListener('resize', this.onScroll);
    // Load the personal dictionary, then re-filter; keep it live across sites.
    void loadDict().then((d) => {
      this.dict = d;
      this.refilter();
    });
    this.unsubDict = onDictChange((d) => {
      this.dict = d;
      this.refilter();
    });
    this.schedule();
  }

  private schedule(): void {
    clearTimeout(this.timer);
    this.timer = window.setTimeout(() => void this.run(), DEBOUNCE_MS);
  }

  private async run(): Promise<void> {
    const text = this.field.getText();
    if (!text.trim() || text.length > MAX_LEN) {
      this.text = text;
      this.setIssues([]);
      return;
    }
    let issues: GrammarIssue[] = [];
    try {
      if (!chrome.runtime?.id) return; // stale content script after extension reload
      const resp = await chrome.runtime.sendMessage({ type: 'JALEBI_CHECK', text });
      if (resp?.ok) issues = resp.issues as GrammarIssue[];
    } catch {
      /* backend unreachable or extension reloaded — leave field unmarked */
    }
    if (this.destroyed) return;
    this.text = text;
    this.setIssues(issues);
  }

  private setIssues(issues: GrammarIssue[]): void {
    this.allIssues = issues;
    this.refilter();
  }

  // Span text an issue covers, from the snapshot it was computed against.
  private span(issue: GrammarIssue): string {
    return this.text.slice(issue.offset, issue.offset + issue.length);
  }

  private key(issue: GrammarIssue): string {
    return `${issue.rule}::${this.span(issue).toLowerCase()}`;
  }

  private isIgnored(issue: GrammarIssue): boolean {
    const word = this.span(issue).trim().toLowerCase();
    if (word && this.dict.has(word)) return true;
    return this.dismissed.has(this.key(issue));
  }

  private refilter(): void {
    this.issues = this.allIssues.filter((i) => !this.isIgnored(i));
    this.render();
  }

  private dismiss(issue: GrammarIssue): void {
    this.dismissed.add(this.key(issue));
    this.refilter();
  }

  private addToDictionary(issue: GrammarIssue): void {
    const word = this.span(issue).trim();
    if (!word) return;
    this.dict.add(word.toLowerCase());
    void addWord(word);
    this.refilter();
  }

  private render(): void {
    const underlines: Underline[] = [];
    const hoverData: IssueRects[] = [];
    for (const issue of this.issues) {
      const rects = rangeRects(
        this.field.el,
        this.field.isInput,
        issue.offset,
        issue.offset + issue.length,
      );
      if (rects.length) hoverData.push({ issue, rects });
      for (const rect of rects) {
        underlines.push({ rect, color: SEVERITY_COLOR[issue.severity] });
      }
    }
    this.layer.draw(underlines);
    this.hover.setData(hoverData);
    this.panel.update(this.field.el.getBoundingClientRect(), this.issues, this.buildHandlers());
  }

  private buildHandlers(): IssueHandlers {
    return {
      apply: (i, r) => this.apply(i, r),
      dismiss: (i) => this.dismiss(i),
      addWord: (i) => this.addToDictionary(i),
      requestRewrite: (i) => this.requestRewrite(i),
      applyRewrite: (i, r) => this.applyRewrite(i, r),
    };
  }

  // Bounds of the sentence containing [offset, offset+length), so AI rewrites
  // operate on a whole sentence rather than a fragment.
  private sentenceRange(offset: number, length: number): [number, number] {
    const t = this.text;
    let start = 0;
    for (let i = Math.min(offset, t.length) - 1; i >= 0; i--) {
      const ch = t[i];
      if (ch === '\n') {
        start = i + 1;
        break;
      }
      if ((ch === '.' || ch === '!' || ch === '?') && /\s/.test(t[i + 1] ?? ' ')) {
        start = i + 1;
        break;
      }
    }
    while (start < t.length && /\s/.test(t[start])) start++;
    let end = t.length;
    for (let i = Math.max(offset + length, 0); i < t.length; i++) {
      const ch = t[i];
      if (ch === '\n') {
        end = i;
        break;
      }
      if (ch === '.' || ch === '!' || ch === '?') {
        const next = t[i + 1];
        if (next === undefined || /\s/.test(next)) {
          end = i + 1;
          break;
        }
      }
    }
    return [start, end];
  }

  private rewriteGoal(issue: GrammarIssue): string {
    if (issue.rule === 'WORDY' || issue.rule === 'REDUNDANT') return 'conciseness';
    if (issue.rule === 'FILLER' || issue.rule === 'PASSIVE' || issue.severity === 'style')
      return 'tone';
    if (issue.severity === 'grammar' || issue.severity === 'spelling') return 'grammar';
    return 'clarity';
  }

  private async requestRewrite(issue: GrammarIssue): Promise<RewriteResult> {
    const [s, e] = this.sentenceRange(issue.offset, issue.length);
    const sentence = this.text.slice(s, e).trim();
    const empty: RewriteResult = { options: [], sentence, engine: '' };
    try {
      if (!chrome.runtime?.id) return empty;
      const resp = await chrome.runtime.sendMessage({
        type: 'JALEBI_REWRITE',
        text: sentence,
        goal: this.rewriteGoal(issue),
        context: '',
      });
      if (resp?.ok) return { options: resp.options as string[], sentence, engine: resp.engine };
    } catch {
      /* provider/network error — treated as no options */
    }
    return empty;
  }

  private applyRewrite(issue: GrammarIssue, replacement: string): void {
    const [s, e] = this.sentenceRange(issue.offset, issue.length);
    this.field.replaceRange(s, e - s, replacement);
    this.schedule();
  }

  private throttledReposition(): void {
    if (this.rafPending || this.destroyed) return;
    this.rafPending = true;
    requestAnimationFrame(() => {
      this.rafPending = false;
      if (!this.destroyed && this.issues.length) this.render();
    });
  }

  private apply(issue: GrammarIssue, replacement: string): void {
    this.field.replaceRange(issue.offset, issue.length, replacement);
    // Offsets shift after an edit — the simplest correct move is to re-check.
    this.schedule();
  }

  destroy(): void {
    this.destroyed = true;
    clearTimeout(this.timer);
    this.unsubDict?.();
    this.field.el.removeEventListener('input', this.onInput);
    window.removeEventListener('scroll', this.onScroll, true);
    window.removeEventListener('resize', this.onScroll);
    this.layer.destroy();
    this.panel.destroy();
    this.hover.destroy();
  }
}
