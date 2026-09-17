# Display labels for the sidebar dropdown and classifier response.
# Extracted from the retired app/rubrics module, which also carried a
# 15-dimension weighting vocabulary that no scoring path ever read.

from app.schemas.evaluation import ContentType

CONTENT_TYPE_LABELS: dict[ContentType, str] = {
    ContentType.breaking_news: "Breaking News / Matter Coverage",
    ContentType.analysis: "Analytical / Insight",
    ContentType.investigative: "Investigative / Observatory",
    ContentType.news_article: "News Article",
    ContentType.policy_analysis: "Policy Analysis",
    ContentType.research_paper: "Research Paper",
    ContentType.opinion: "Opinion Piece",
    ContentType.editorial: "Editorial",
    ContentType.youtube_script: "YouTube Script",
    ContentType.instagram_script: "Instagram Script",
    ContentType.linkedin_article: "LinkedIn Article",
    ContentType.twitter_thread: "Twitter Thread",
    ContentType.newsletter: "Newsletter",
    ContentType.press_release: "Press Release",
    ContentType.speech: "Speech",
    ContentType.explainer: "Explainer",
    ContentType.case_study: "Case Study",
}


def label_for(content_type: ContentType) -> str:
    return CONTENT_TYPE_LABELS.get(content_type, content_type.value.replace("_", " ").title())
