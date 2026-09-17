"""Machine-readable form of the TIES Editorial Constitution.

Every constant here maps directly to a clause in
`app/knowledge/ties_constitution.md`. Changing a weight, cap, or phrase list here
changes how the editor scores — this is the single tunable source of truth.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

# ── Dimensions ───────────────────────────────────────────────────────────────
# key -> (display name, default weight, alpha)
#   weight = share of the final score (must sum to 1.0 per content type)
#   alpha  = share of THAT dimension driven by deterministic rules (rest is AI).
#            Higher alpha = more reproducible. Overall determinism ≈ Σ weight*alpha.


@dataclass(frozen=True)
class Dimension:
    key: str
    name: str
    weight: float
    alpha: float  # 0..1 rule-share for this dimension


DIMENSIONS: List[Dimension] = [
    Dimension("accuracy", "Research Accuracy", 0.30, 0.75),
    Dimension("insight", "Original Insight", 0.20, 0.15),
    Dimension("narrative", "Narrative Structure", 0.15, 0.60),
    Dimension("depth", "Depth", 0.10, 0.60),
    Dimension("sourcing", "Credibility & Sourcing", 0.10, 0.95),
    Dimension("writing", "Writing Quality", 0.10, 0.95),
    Dimension("headline", "Headline", 0.05, 0.85),
]
DIM_BY_KEY: Dict[str, Dimension] = {d.key: d for d in DIMENSIONS}
DIM_KEYS: List[str] = [d.key for d in DIMENSIONS]

# ── Weight overrides by content type (Constitution §B) ───────────────────────
# Only the dimensions the Constitution specifies are pinned; the remainder is
# distributed so every vector sums to 1.0 (see _fill).
_BASE = {d.key: d.weight for d in DIMENSIONS}


def _fill(pinned: Dict[str, float]) -> Dict[str, float]:
    """Complete a partial weight vector, spreading the remainder proportionally
    across the unpinned dimensions using their base weights, so it sums to 1.0."""
    remaining = 1.0 - sum(pinned.values())
    unpinned = [k for k in DIM_KEYS if k not in pinned]
    base_sum = sum(_BASE[k] for k in unpinned) or 1.0
    out = dict(pinned)
    for k in unpinned:
        out[k] = round(remaining * (_BASE[k] / base_sum), 4)
    # Correct any rounding drift onto the largest unpinned dimension.
    drift = round(1.0 - sum(out.values()), 4)
    if unpinned and abs(drift) >= 0.0001:
        big = max(unpinned, key=lambda k: out[k])
        out[big] = round(out[big] + drift, 4)
    return out


WEIGHTS_BY_TYPE: Dict[str, Dict[str, float]] = {
    "breaking_news": _fill({"accuracy": 0.40, "sourcing": 0.20, "insight": 0.10}),
    "opinion": _fill({"insight": 0.30, "accuracy": 0.25}),
    "analysis": _fill({"accuracy": 0.25, "insight": 0.25, "narrative": 0.20}),
    "investigative": _fill({"accuracy": 0.40, "sourcing": 0.20, "insight": 0.15}),
}
DEFAULT_WEIGHTS: Dict[str, float] = dict(_BASE)


def weights_for(content_type: str) -> Dict[str, float]:
    return WEIGHTS_BY_TYPE.get(content_type, DEFAULT_WEIGHTS)


# ── Short-form (TIES Content SOP) ────────────────────────────────────────────
# The SOP governs standard short-form analytical articles: 300–350 words, with
# "innovative bullet points, numbered lists, or key takeaways" required.
#
# Two Constitution-derived rules conflict with that and must not apply here:
#   * the bullet-list penalty  (SOP mandates bulleted takeaways)
#   * the length reward at 800/1500 words (SOP caps the piece at ~350)
# Long-form types keep both, where "prefer flowing prose" and "reward depth"
# remain the right call.
SHORT_FORM_TYPES = frozenset({
    "breaking_news", "analysis", "opinion",
    "instagram_script", "twitter_thread", "linkedin_article",
})

# SOP word window for short-form pieces (inclusive).
SHORT_FORM_WORD_MIN = 300
SHORT_FORM_WORD_MAX = 350


def is_short_form(content_type: str) -> bool:
    return content_type in SHORT_FORM_TYPES


# ── Hard caps (Constitution §C) ──────────────────────────────────────────────
# code -> (score ceiling, human label). A triggered cap limits the FINAL score to
# at most the ceiling, regardless of everything else.
HARD_CAPS: Dict[str, "HardCap"] = {}


@dataclass(frozen=True)
class HardCap:
    code: str
    ceiling: int
    label: str


for _c in [
    HardCap("fabricated_quote", 0, "Fabricated quotation"),
    HardCap("fabricated_statistic", 20, "Fabricated statistic"),
    HardCap("major_factual_error", 40, "Major factual error"),
    HardCap("sensitive_allegation_unsourced", 45, "Unsourced sensitive allegation"),
    HardCap("unsupported_claim", 50, "Unsupported factual claim"),
    HardCap("opinion_as_fact", 65, "Opinion presented as fact"),
    HardCap("headline_unsupported", 70, "Headline unsupported by the article"),
]:
    HARD_CAPS[_c.code] = _c

# ── Publication bands (Constitution §A) ──────────────────────────────────────
PUBLICATION_THRESHOLD = 85  # >= this is normally approved

# (floor, readiness label, publication_ready)
BANDS = [
    (85, "Ready to Publish", True),
    (75, "Needs Minor Revision", False),
    (60, "Needs Major Revision", False),
    (0, "Not Ready", False),
]


def band_for(score: int):
    for floor, label, ready in BANDS:
        if score >= floor:
            return label, ready
    return "Not Ready", False


# ── Source hierarchy (Constitution §D) ───────────────────────────────────────
# tier -> substrings (lowercase) that signal a source of that tier.
SOURCE_TIERS: Dict[int, List[str]] = {
    1: ["government", "ministry", "court", "supreme court", "judgment", "legislation",
        "official statistics", "census", "peer-reviewed", "journal of", "filing",
        "annual report", "gazette", "parliament", "regulator"],
    2: ["reuters", "associated press", "(ap)", "afp", "bloomberg", "pti",
        "press trust of india"],
    3: ["new york times", "the guardian", "bbc", "the hindu", "financial times",
        "washington post", "university", "institute", "think tank", "council on"],
    4: ["expert", "professor", "analyst", "industry report", "according to a report"],
    5: ["blog", "op-ed", "opinion piece", "medium.com", "substack"],
    6: ["twitter", "x.com", "facebook", "instagram", "tiktok", "telegram", "whatsapp"],
}

# Words/patterns that signal an attribution is present near a claim.
ATTRIBUTION_MARKERS = [
    "according to", "said", "says", "reported", "stated", "cited", "per ",
    "sources said", "data from", "study by", "research by", "found that",
    "as reported by", "in a statement", "confirmed", "disclosed",
]

# ── Bias / neutrality (Constitution §E) ──────────────────────────────────────
BIAS_PHRASES = [
    "obviously", "clearly", "everyone knows", "undeniably", "without question",
    "always", "never", "of course", "needless to say", "it goes without saying",
]

# Topics needing extra scrutiny — used to escalate unsourced allegations.
HIGH_SCRUTINY_TERMS = [
    "alleged", "allegation", "accused", "war", "attack", "strike", "genocide",
    "corruption", "scandal", "terrorist", "coup", "fraud", "killed", "massacre",
    "airspace", "airbase", "nuclear", "military", "regime",
]

# ── House style (Constitution §G) ────────────────────────────────────────────
AI_CLICHES = [
    "in today's fast-paced world", "it is worth noting", "this highlights",
    "this underscores", "the bottom line", "in conclusion", "one thing is clear",
    "as we move forward", "needless to say", "now more than ever", "let's dive in",
    "in the ever-evolving", "at the end of the day", "when it comes to",
]

# American -> British spellings (Constitution: British English).
AMERICAN_SPELLINGS = {
    "color": "colour", "favor": "favour", "honor": "honour", "labor": "labour",
    "behavior": "behaviour", "organize": "organise", "organized": "organised",
    "organization": "organisation", "realize": "realise", "recognize": "recognise",
    "analyze": "analyse", "defense": "defence", "offense": "offence",
    "center": "centre", "meter": "metre", "theater": "theatre", "traveled": "travelled",
    "canceled": "cancelled", "fulfill": "fulfil", "enroll": "enrol",
    "program": "programme", "catalog": "catalogue", "dialog": "dialogue",
}

# Clickbait signals in a headline.
CLICKBAIT_MARKERS = [
    "you won't believe", "shocking", "this is why", "what happens next",
    "will blow your mind", "the truth about", "nobody is talking about",
    "here's why", "the real reason", "mind-blowing", "gone wrong", "?!",
]

# Phrasings that assert opinion as fact without hedging.
OPINION_AS_FACT_MARKERS = [
    "the best", "the worst", "the greatest", "everyone should", "no one should",
    "is a disaster", "is a triumph", "proves that", "there is no doubt",
]
