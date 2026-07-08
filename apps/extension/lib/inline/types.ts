// Mirrors apps/backend/app/schemas/grammar.py (GrammarIssue / CheckResponse).

export type Severity = 'spelling' | 'grammar' | 'punctuation' | 'style';

export interface GrammarIssue {
  offset: number;
  length: number;
  message: string;
  short: string;
  replacements: string[];
  rule: string;
  category: string;
  severity: Severity;
  context: string;
}

export interface CheckResponse {
  issues: GrammarIssue[];
  engine: string;
  language: string;
}

/** Actions a suggestion surface (panel or hover card) can trigger. */
export interface IssueHandlers {
  apply: (issue: GrammarIssue, replacement: string) => void;
  dismiss: (issue: GrammarIssue) => void;
  addWord: (issue: GrammarIssue) => void;
  /** Ask the LLM to rewrite the sentence around the issue; returns options. */
  requestRewrite: (issue: GrammarIssue) => Promise<RewriteResult>;
  /** Replace the whole sentence around the issue with the chosen rewrite. */
  applyRewrite: (issue: GrammarIssue, replacement: string) => void;
}

export interface RewriteResult {
  options: string[];
  sentence: string;
  engine: string;
}

/** A flagged issue paired with the viewport rects of its span (for hit-testing). */
export interface IssueRects {
  issue: GrammarIssue;
  rects: DOMRect[];
}

export const SEVERITY_COLOR: Record<Severity, string> = {
  spelling: '#f43f5e', // red
  grammar: '#f43f5e',
  punctuation: '#3b82f6', // blue
  style: '#a855f7', // purple
};
