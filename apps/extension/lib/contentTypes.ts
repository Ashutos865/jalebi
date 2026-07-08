import type { ContentTypeOption } from './types';

// Fallback used if the backend can't be reached when the panel loads. Mirrors the
// rubric labels in apps/backend/app/rubrics.
export const FALLBACK_CONTENT_TYPES: ContentTypeOption[] = [
  { value: 'breaking_news', label: 'Breaking News / Matter Coverage' },
  { value: 'analysis', label: 'Analytical / Insight' },
  { value: 'investigative', label: 'Investigative / Observatory' },
  { value: 'opinion', label: 'Opinion Piece' },
  { value: 'news_article', label: 'News Article' },
  { value: 'policy_analysis', label: 'Policy Analysis' },
  { value: 'research_paper', label: 'Research Paper' },
  { value: 'editorial', label: 'Editorial' },
  { value: 'youtube_script', label: 'YouTube Script' },
  { value: 'instagram_script', label: 'Instagram Script' },
  { value: 'linkedin_article', label: 'LinkedIn Article' },
  { value: 'twitter_thread', label: 'Twitter Thread' },
  { value: 'newsletter', label: 'Newsletter' },
  { value: 'press_release', label: 'Press Release' },
  { value: 'speech', label: 'Speech' },
  { value: 'explainer', label: 'Explainer' },
  { value: 'case_study', label: 'Case Study' },
];
