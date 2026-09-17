// Mirrors apps/backend/app/schemas/evaluation.py (the source of truth).
// P2 replaces this hand-mirror with schema codegen so the two can't drift.

export type Priority = 'critical' | 'high' | 'medium' | 'low';

export type PublicationReadiness =
  | 'Ready to Publish'
  | 'Needs Minor Revision'
  | 'Needs Major Revision'
  | 'Not Ready';

export type ContentTypeValue =
  | 'breaking_news'
  | 'analysis'
  | 'investigative'
  | 'news_article'
  | 'policy_analysis'
  | 'research_paper'
  | 'opinion'
  | 'editorial'
  | 'youtube_script'
  | 'instagram_script'
  | 'linkedin_article'
  | 'twitter_thread'
  | 'newsletter'
  | 'press_release'
  | 'speech'
  | 'explainer'
  | 'case_study';

export interface Issue {
  problem: string;
  explanation: string;
  impact: string;
  suggestion: string;
  priority: Priority;
  quote?: string | null;
  options?: string[];
  example?: string | null;
}

export interface CategoryScore {
  name: string;
  key: string;
  score: number;
  weight: number;
  summary: string;
  issues: Issue[];
  recommendations: string[];
}

// Every field except content_type has a default on the backend, so a response
// may legitimately omit them. Optional here to match reality.
export interface EvaluationMeta {
  evaluator?: string;
  model?: string;
  schema_version?: string;
  content_type: ContentTypeValue;
  word_count?: number;
  duration_ms?: number;
  knowledge_used?: number;
}

// ── Production loop (TIES SOP §3) ────────────────────────────────────────────

/** Mirrors app/workflow/states.py. */
export type WorkflowStatus =
  | 'assigned'
  | 'drafting'
  | 'submitted'
  | 'under_review'
  | 'revising'
  | 'approved'
  | 'published'
  | 'reassigned'
  | 'scrapped'
  // Legacy free-text statuses that predate the state machine.
  | 'draft'
  | 'finalized';

export interface WorkflowSla {
  phase: 'drafting' | 'editing' | null;
  due_at?: string | null;
  target_at?: string | null;
  hours_remaining?: number | null;
  overdue: boolean;
  at_risk: boolean;
}

export interface WorkflowState {
  status: WorkflowStatus;
  next_states: WorkflowStatus[];
  assigned_to: string;
  assigned_by: string;
  editor: string;
  word_min?: number | null;
  word_max?: number | null;
  assigned_at?: string | null;
  submitted_at?: string | null;
  approved_at?: string | null;
  approved_by: string;
  override_reason: string;
  escalation_reason: string;
  /** Why this is not cleanly approvable. Advisory: the editor keeps final say. */
  blocking_reasons: string[];
  sla: WorkflowSla;
}

/** One mechanical TIES SOP check (header, word count, structure, references). */
export interface SopCheckItem {
  name: string;
  passed: boolean;
  detail: string;
  severity: 'required' | 'advisory';
}

/** SOP compliance — reported beside the editorial score, never mixed into it. */
export interface SopComplianceReport {
  checked: boolean; // false when the document has no SOP header
  compliant: boolean;
  checks: SopCheckItem[];
  header_present: boolean;
  header_fields: Record<string, string>;
  missing_fields: string[];
  word_count: number;
  word_min?: number | null;
  word_max?: number | null;
  reference_urls: string[];
}

export interface EvaluationResult {
  overall_score: number;
  publication_ready: boolean;
  publication_readiness: PublicationReadiness;
  content_type: ContentTypeValue;
  summary: string;
  categories: CategoryScore[];
  critical_issues: Issue[];
  strengths: string[];
  next_steps: string[];
  sop?: SopComplianceReport;
  meta: EvaluationMeta;
}

export interface EvaluationRequest {
  text: string;
  content_type: ContentTypeValue;
  title?: string | null;
  doc_id?: string | null;
  doc_url?: string | null;
  provider?: string | null;
}

export interface ContentTypeOption {
  value: ContentTypeValue;
  label: string;
}

export interface ProviderOption {
  id: string;
  label: string;
  open_source: boolean;
  model: string;
  available: boolean;
  note: string;
}

export interface ProvidersResponse {
  active: string;
  providers: ProviderOption[];
}

export interface ClassifyResponse {
  content_type: ContentTypeValue;
  confidence: number;
  label: string;
  scores: Record<string, number>;
}
