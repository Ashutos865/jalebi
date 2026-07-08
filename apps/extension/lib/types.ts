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

export interface EvaluationMeta {
  evaluator: string;
  model: string;
  schema_version: string;
  content_type: ContentTypeValue;
  word_count: number;
  duration_ms: number;
  knowledge_used: number;
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
