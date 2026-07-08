"""Rubrics — editorial dimensions as data, not code.

A rubric is a content type plus a weighted list of `Dimension`s. Weights within a
rubric sum to 1.0 and drive the overall score. Editorial DNA (evidence before
opinion, no sensationalism, provide context, India-first but evidence-based, no AI
clichés) is expressed as the dimensions we choose to weight and, at review time, as
the heuristics/prompts each dimension applies.

Adding a content type or re-weighting a rubric is a data edit here — no pipeline
changes required.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from app.schemas.evaluation import ContentType


@dataclass(frozen=True)
class Dimension:
    key: str          # stable id, used by reviewers
    name: str         # human label shown in the sidebar
    weight: float     # contribution to the overall score (per-rubric, sums to 1.0)
    description: str   # what a strong result on this dimension looks like


@dataclass(frozen=True)
class Rubric:
    content_type: ContentType
    label: str
    dimensions: List[Dimension]

    def weight_of(self, key: str) -> float:
        for d in self.dimensions:
            if d.key == key:
                return d.weight
        return 0.0


# --- Dimension library -------------------------------------------------------
# Canonical descriptions reused across rubrics. Weights are assigned per-rubric.

_D = {
    "research": "Depth and rigor of research; claims are grounded in verifiable primary sources.",
    "evidence": "Evidence precedes opinion; data, examples, and citations support each claim.",
    "accuracy": "Facts, figures, names, and dates are correct and internally consistent.",
    "narrative": "A clear through-line; the piece builds an argument rather than listing facts.",
    "neutrality": "Neutral, non-sensational language; balanced viewpoints; no clickbait or exaggeration.",
    "context": "Historical, strategic, economic and India/global context where it matters.",
    "structure": "Logical flow; strong introduction and conclusion; coherent sections.",
    "writing": "Clarity without oversimplifying; no AI clichés or generic corporate filler.",
    "readability": "Sentence and paragraph length suit the audience; easy to follow.",
    "grammar": "Grammar, spelling, and mechanics are clean.",
    "headline": "Headline is accurate, specific, and non-sensational.",
    "citations": "Factual claims are attributed; sources are credible and cited.",
    "formatting": "Consistent formatting appropriate to the medium.",
    "seo": "Discoverability: keywords, structure, and metadata where the medium calls for it.",
    "engagement": "Hooks and pacing suited to the platform, without resorting to clickbait.",
}


def _dim(key: str, name: str, weight: float) -> Dimension:
    return Dimension(key=key, name=name, weight=weight, description=_D[key])


# --- Rubrics ----------------------------------------------------------------

def _rubric(ct: ContentType, label: str, weighted: List[tuple]) -> Rubric:
    dims = [_dim(k, n, w) for (k, n, w) in weighted]
    total = round(sum(d.weight for d in dims), 4)
    if abs(total - 1.0) > 1e-6:
        raise ValueError(f"Rubric {ct} weights sum to {total}, expected 1.0")
    return Rubric(content_type=ct, label=label, dimensions=dims)


RUBRICS: Dict[ContentType, Rubric] = {
    # --- TIES SOP categories ---
    ContentType.breaking_news: _rubric(
        ContentType.breaking_news, "Breaking News / Matter Coverage",
        [
            ("accuracy", "Accuracy", 0.24),
            ("citations", "Fact Attribution", 0.18),
            ("evidence", "Evidence", 0.14),
            ("structure", "Structure", 0.14),
            ("neutrality", "Neutrality", 0.12),
            ("writing", "Writing", 0.10),
            ("grammar", "Grammar", 0.08),
        ],
    ),
    ContentType.analysis: _rubric(
        ContentType.analysis, "Analytical / Insight",
        [
            ("research", "Research Quality", 0.20),
            ("evidence", "Evidence", 0.20),
            ("context", "Context & Implications", 0.16),
            ("narrative", "Argument & Connections", 0.16),
            ("accuracy", "Accuracy", 0.12),
            ("writing", "Writing", 0.08),
            ("grammar", "Grammar", 0.08),
        ],
    ),
    ContentType.investigative: _rubric(
        ContentType.investigative, "Investigative / Observatory",
        [
            ("evidence", "Evidence", 0.22),
            ("research", "Research Quality", 0.18),
            ("accuracy", "Accuracy", 0.16),
            ("narrative", "Interpretation & Insight", 0.16),
            ("context", "Context", 0.12),
            ("citations", "Citations", 0.08),
            ("grammar", "Grammar", 0.08),
        ],
    ),
    ContentType.news_article: _rubric(
        ContentType.news_article, "News Article",
        [
            ("accuracy", "Accuracy", 0.18),
            ("evidence", "Evidence", 0.15),
            ("neutrality", "Neutrality", 0.15),
            ("citations", "Fact Attribution", 0.14),
            ("structure", "Structure", 0.12),
            ("headline", "Headline", 0.10),
            ("writing", "Writing", 0.08),
            ("grammar", "Grammar", 0.08),
        ],
    ),
    ContentType.policy_analysis: _rubric(
        ContentType.policy_analysis, "Policy Analysis",
        [
            ("research", "Research Quality", 0.20),
            ("evidence", "Evidence", 0.18),
            ("context", "Context", 0.16),
            ("neutrality", "Objectivity", 0.14),
            ("narrative", "Argument", 0.12),
            ("citations", "Citations", 0.10),
            ("writing", "Writing", 0.05),
            ("grammar", "Grammar", 0.05),
        ],
    ),
    ContentType.research_paper: _rubric(
        ContentType.research_paper, "Research Paper",
        [
            ("research", "Research Quality", 0.24),
            ("evidence", "Evidence", 0.18),
            ("accuracy", "Accuracy", 0.16),
            ("citations", "Citations", 0.14),
            ("structure", "Structure", 0.12),
            ("writing", "Writing", 0.08),
            ("grammar", "Grammar", 0.08),
        ],
    ),
    ContentType.opinion: _rubric(
        ContentType.opinion, "Opinion Piece",
        [
            ("narrative", "Argument", 0.22),
            ("evidence", "Evidence", 0.20),
            ("neutrality", "Fairness", 0.14),
            ("context", "Context", 0.14),
            ("writing", "Writing", 0.12),
            ("structure", "Structure", 0.10),
            ("grammar", "Grammar", 0.08),
        ],
    ),
    ContentType.editorial: _rubric(
        ContentType.editorial, "Editorial",
        [
            ("narrative", "Argument", 0.22),
            ("evidence", "Evidence", 0.18),
            ("context", "Context", 0.16),
            ("neutrality", "Balance", 0.14),
            ("writing", "Writing", 0.12),
            ("structure", "Structure", 0.10),
            ("grammar", "Grammar", 0.08),
        ],
    ),
    ContentType.youtube_script: _rubric(
        ContentType.youtube_script, "YouTube Script",
        [
            ("narrative", "Narrative", 0.22),
            ("engagement", "Hook & Pacing", 0.20),
            ("accuracy", "Accuracy", 0.16),
            ("evidence", "Evidence", 0.14),
            ("structure", "Structure", 0.12),
            ("writing", "Writing", 0.10),
            ("grammar", "Grammar", 0.06),
        ],
    ),
    ContentType.instagram_script: _rubric(
        ContentType.instagram_script, "Instagram Script",
        [
            ("engagement", "Hook & Pacing", 0.28),
            ("narrative", "Narrative", 0.20),
            ("accuracy", "Accuracy", 0.16),
            ("writing", "Writing", 0.16),
            ("neutrality", "No Clickbait", 0.12),
            ("grammar", "Grammar", 0.08),
        ],
    ),
    ContentType.linkedin_article: _rubric(
        ContentType.linkedin_article, "LinkedIn Article",
        [
            ("narrative", "Narrative", 0.20),
            ("evidence", "Evidence", 0.18),
            ("writing", "Writing", 0.16),
            ("engagement", "Engagement", 0.14),
            ("context", "Context", 0.12),
            ("structure", "Structure", 0.12),
            ("grammar", "Grammar", 0.08),
        ],
    ),
    ContentType.twitter_thread: _rubric(
        ContentType.twitter_thread, "Twitter Thread",
        [
            ("engagement", "Hook & Pacing", 0.26),
            ("narrative", "Narrative", 0.20),
            ("accuracy", "Accuracy", 0.18),
            ("evidence", "Evidence", 0.14),
            ("neutrality", "No Sensationalism", 0.14),
            ("grammar", "Grammar", 0.08),
        ],
    ),
    ContentType.newsletter: _rubric(
        ContentType.newsletter, "Newsletter",
        [
            ("narrative", "Narrative", 0.20),
            ("writing", "Writing", 0.18),
            ("evidence", "Evidence", 0.16),
            ("engagement", "Engagement", 0.14),
            ("structure", "Structure", 0.12),
            ("context", "Context", 0.12),
            ("grammar", "Grammar", 0.08),
        ],
    ),
    ContentType.press_release: _rubric(
        ContentType.press_release, "Press Release",
        [
            ("accuracy", "Accuracy", 0.20),
            ("structure", "Structure", 0.18),
            ("citations", "Attribution", 0.16),
            ("neutrality", "Neutral Tone", 0.14),
            ("writing", "Writing", 0.12),
            ("headline", "Headline", 0.12),
            ("grammar", "Grammar", 0.08),
        ],
    ),
    ContentType.speech: _rubric(
        ContentType.speech, "Speech",
        [
            ("narrative", "Narrative", 0.26),
            ("engagement", "Delivery & Pacing", 0.20),
            ("writing", "Writing", 0.18),
            ("context", "Context", 0.14),
            ("structure", "Structure", 0.14),
            ("grammar", "Grammar", 0.08),
        ],
    ),
    ContentType.explainer: _rubric(
        ContentType.explainer, "Explainer",
        [
            ("accuracy", "Accuracy", 0.20),
            ("readability", "Readability", 0.18),
            ("structure", "Structure", 0.16),
            ("evidence", "Evidence", 0.14),
            ("context", "Context", 0.12),
            ("writing", "Writing", 0.12),
            ("grammar", "Grammar", 0.08),
        ],
    ),
    ContentType.case_study: _rubric(
        ContentType.case_study, "Case Study",
        [
            ("evidence", "Evidence", 0.22),
            ("narrative", "Narrative", 0.18),
            ("research", "Research Quality", 0.16),
            ("structure", "Structure", 0.14),
            ("accuracy", "Accuracy", 0.12),
            ("writing", "Writing", 0.10),
            ("grammar", "Grammar", 0.08),
        ],
    ),
}


# Admin weight overrides (P5). Loaded from the DB on startup; applied in-memory and
# renormalized so the rubric always sums to 1.0.
_overrides: Dict[ContentType, Dict[str, float]] = {}


def set_override(content_type: ContentType, weights: Dict[str, float]) -> None:
    _overrides[content_type] = dict(weights)


def clear_override(content_type: ContentType) -> None:
    _overrides.pop(content_type, None)


def get_override(content_type: ContentType) -> Dict[str, float] | None:
    return _overrides.get(content_type)


def get_rubric(content_type: ContentType) -> Rubric:
    base = RUBRICS[content_type]
    ov = _overrides.get(content_type)
    if not ov:
        return base
    raw = [
        Dimension(d.key, d.name, ov.get(d.key, d.weight), d.description)
        for d in base.dimensions
    ]
    total = round(sum(d.weight for d in raw), 6) or 1.0
    dims = [Dimension(d.key, d.name, round(d.weight / total, 4), d.description) for d in raw]
    return Rubric(content_type=content_type, label=base.label, dimensions=dims)
