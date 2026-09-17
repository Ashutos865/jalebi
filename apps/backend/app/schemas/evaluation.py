"""Evaluation contract — the single source of truth for Jalebi's scorecard.

These Pydantic models define the JSON exchanged between the extension and the
backend. The extension's `lib/types.ts` mirrors them. Every editorial issue carries
Problem / Explanation / Impact / Suggestion / Priority / Example / Quote so that
feedback is always actionable and grounded in the actual content.
"""
from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

SCHEMA_VERSION = "1.0"


class ContentType(str, Enum):
    """Supported evaluation modes. Each maps to a rubric."""

    # TIES SOP content categories
    breaking_news = "breaking_news"     # Matter Coverage / Breaking News
    analysis = "analysis"               # Insight / Analytical pieces
    investigative = "investigative"     # Observatory / Investigative content
    opinion = "opinion"                 # Opinion pieces
    # General editorial types
    news_article = "news_article"
    policy_analysis = "policy_analysis"
    research_paper = "research_paper"
    editorial = "editorial"
    youtube_script = "youtube_script"
    instagram_script = "instagram_script"
    linkedin_article = "linkedin_article"
    twitter_thread = "twitter_thread"
    newsletter = "newsletter"
    press_release = "press_release"
    speech = "speech"
    explainer = "explainer"
    case_study = "case_study"


class Priority(str, Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class PublicationReadiness(str, Enum):
    ready = "Ready to Publish"
    minor = "Needs Minor Revision"
    major = "Needs Major Revision"
    not_ready = "Not Ready"


class Issue(BaseModel):
    """A single editorial problem. Never generic — always references the content."""

    problem: str = Field(..., description="What is wrong, stated plainly.")
    explanation: str = Field(..., description="Why it is a problem.")
    impact: str = Field(..., description="The editorial cost of leaving it unfixed.")
    suggestion: str = Field(..., description="How to fix it.")
    priority: Priority = Priority.medium
    quote: Optional[str] = Field(
        None, description="The passage from the document this refers to."
    )
    # 2-4 concrete rewrite options of the quoted line. GROUNDED ONLY: rephrasing /
    # restructuring the writer's own words. Facts, numbers, sources, names, and dates
    # are NEVER invented — a missing fact becomes a bracketed placeholder to fill in.
    options: List[str] = Field(default_factory=list)
    example: Optional[str] = Field(
        None, description="Deprecated single example; prefer `options`."
    )


class CategoryScore(BaseModel):
    """One editorial dimension's score and findings."""

    name: str
    key: str
    score: int = Field(..., ge=0, le=100)
    weight: float = Field(..., ge=0.0, le=1.0)
    summary: str = ""
    issues: List[Issue] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)


class EvaluationMeta(BaseModel):
    evaluator: str = "mock"          # provider id, e.g. "mock" | "anthropic" | "openai"
    model: str = ""                  # concrete model id, when an LLM produced it
    schema_version: str = SCHEMA_VERSION
    content_type: ContentType
    word_count: int = 0
    duration_ms: int = 0
    knowledge_used: int = 0          # # of knowledge-base passages retrieved (RAG, P4)


class SopCheckItem(BaseModel):
    """One mechanical TIES SOP check (header, word count, structure, references)."""

    name: str
    passed: bool
    detail: str = ""
    severity: str = "required"       # required | advisory


class SopComplianceReport(BaseModel):
    """SOP compliance, reported alongside — never folded into — the editorial
    score. Process compliance and writing quality are different questions."""

    checked: bool = False            # False when the doc has no SOP header
    compliant: bool = False          # no failing `required` check
    checks: List[SopCheckItem] = Field(default_factory=list)
    header_present: bool = False
    header_fields: Dict[str, str] = Field(default_factory=dict)
    missing_fields: List[str] = Field(default_factory=list)
    word_count: int = 0
    word_min: Optional[int] = None
    word_max: Optional[int] = None
    reference_urls: List[str] = Field(default_factory=list)


class EvaluationRequest(BaseModel):
    text: str = Field(..., min_length=1, description="The document text to evaluate.")
    content_type: ContentType = ContentType.news_article
    title: Optional[str] = Field(
        None, description="Document title, if known (e.g. the Google Doc name)."
    )
    doc_id: Optional[str] = Field(None, description="Google Doc id, for history/audit.")
    doc_url: Optional[str] = Field(None, description="Full Google Doc URL, tracked.")
    provider: Optional[str] = Field(
        None, description="Requested AI provider (must be configured & allowed)."
    )
    word_min: Optional[int] = Field(
        None, ge=0, description="Assignment word floor; overrides the SOP default."
    )
    word_max: Optional[int] = Field(
        None, ge=0, description="Assignment word ceiling; overrides the SOP default."
    )


class EvaluationResult(BaseModel):
    overall_score: int = Field(..., ge=0, le=100)
    publication_ready: bool
    publication_readiness: PublicationReadiness
    content_type: ContentType
    summary: str
    categories: List[CategoryScore] = Field(default_factory=list)
    critical_issues: List[Issue] = Field(default_factory=list)
    strengths: List[str] = Field(default_factory=list)
    next_steps: List[str] = Field(default_factory=list)
    sop: SopComplianceReport = Field(default_factory=SopComplianceReport)
    meta: EvaluationMeta
