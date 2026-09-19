"""Machine-readable form of the TIES Editorial Constitution.

Every constant here maps directly to a clause in
`app/knowledge/ties_constitution.md`. Changing a weight, cap, or phrase list here
changes how the editor scores — this is the single tunable source of truth.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, List, Optional

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
    # insight/depth/narrative were 0.15/0.60/0.60 when their rules were
    # placeholders (insight returned a constant). app/scoring/reasoning.py now
    # measures reasoning structure — inference, causal chains, comparison,
    # counter-argument, specificity, filler — so the deterministic share is
    # raised to reflect rules that actually discriminate. The AI layer still
    # leads on insight, which is the hardest to judge mechanically.
    Dimension("insight", "Original Insight", 0.20, 0.45),
    Dimension("narrative", "Narrative Structure", 0.15, 0.70),
    Dimension("depth", "Depth", 0.10, 0.70),
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


# ── Admin weight overrides ───────────────────────────────────────────────────
# Editors tune the per-content-type weighting from the admin panel. Overrides are
# persisted in the DB (RubricOverride) and reloaded into this map at startup, so
# they survive restarts and apply to every worker.
_overrides: Dict[str, Dict[str, float]] = {}

DIMENSION_KEYS: List[str] = [d.key for d in DIMENSIONS]


class WeightError(ValueError):
    """Rejected weight override."""


def validate_weights(weights: Dict[str, float]) -> Dict[str, float]:
    """Check an override and return it normalised to sum to 1.0.

    Strict on purpose. The previous implementation validated only the dimension
    *keys*, so an all-zero override normalised to every weight being 0.0 (every
    document scoring 0), and negative values inverted the score. Both are silent
    and catastrophic.
    """
    if not weights:
        raise WeightError("Provide a weight for at least one dimension.")

    unknown = sorted(set(weights) - set(DIMENSION_KEYS))
    if unknown:
        raise WeightError(
            f"Unknown dimension keys: {unknown}. Valid keys: {DIMENSION_KEYS}."
        )

    for key, value in weights.items():
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise WeightError(f"Weight for {key!r} must be a number.")
        if value != value or value in (float("inf"), float("-inf")):
            raise WeightError(f"Weight for {key!r} must be a finite number.")
        if value < 0:
            raise WeightError(f"Weight for {key!r} cannot be negative.")

    total = sum(weights.values())
    if total <= 0:
        raise WeightError("Weights must add up to more than zero.")

    # Fill unspecified dimensions from the base, then normalise the whole vector
    # so the stored result is exactly what scoring will use — no silent rescaling
    # of a number the admin never entered.
    return {k: round(v, 6) for k, v in weights.items()}


def set_override(content_type: str, weights: Dict[str, float]) -> Dict[str, float]:
    """Validate, store and apply an override. Returns the effective weights."""
    validate_weights(weights)
    _overrides[content_type] = dict(weights)
    return weights_for(content_type)


def clear_override(content_type: str) -> None:
    _overrides.pop(content_type, None)


def get_override(content_type: str) -> Optional[Dict[str, float]]:
    return _overrides.get(content_type)


def weights_for(content_type: str) -> Dict[str, float]:
    """Effective weights: the content-type base, with any admin override applied
    on top, normalised to sum to 1.0."""
    base = dict(WEIGHTS_BY_TYPE.get(content_type, DEFAULT_WEIGHTS))
    override = _overrides.get(content_type)
    if not override:
        return base

    merged = {**base, **override}
    total = sum(merged.values())
    if total <= 0:
        # Defensive: validate_weights rejects this, so it can only arise from a
        # legacy DB row. Fall back to the base rather than zeroing every score.
        return base

    out = {k: round(v / total, 6) for k, v in merged.items()}
    # Rounding each weight independently leaves the sum a hair off 1.0, which
    # would quietly skew every score. Push the residue onto the largest weight,
    # where it is proportionally smallest.
    drift = round(1.0 - sum(out.values()), 6)
    if drift:
        heaviest = max(out, key=lambda k: out[k])
        out[heaviest] = round(out[heaviest] + drift, 6)
    return out


# ── Research-integrity caps (TIES Content SOP §2, §4, "Zero-Tolerance") ──────
# AI-generated text must not exceed 20% of the article; plagiarism must be under
# 15%. These are recorded from a real checker (Quillbot / CopyLeaks /
# SmallSEOTools / DupliChecker), never estimated by Jalebi.
MAX_AI_PERCENT = 20.0
MAX_PLAGIARISM_PERCENT = 15.0


def integrity_verdict(ai_percent, plagiarism_percent) -> dict:
    """Judge recorded AI/plagiarism percentages against the SOP caps.

    `unchecked` is a distinct state from a pass: an article nobody has run
    through a checker has not satisfied the SOP, it simply has no result yet.
    """
    if ai_percent is None or plagiarism_percent is None:
        return {
            "checked": False, "passed": False, "breaches": [],
            "ai_percent": ai_percent, "plagiarism_percent": plagiarism_percent,
            "ai_limit": MAX_AI_PERCENT, "plagiarism_limit": MAX_PLAGIARISM_PERCENT,
        }

    breaches = []
    if ai_percent > MAX_AI_PERCENT:
        breaches.append(
            f"AI-generated content is {ai_percent:.0f}% — the SOP allows at most "
            f"{MAX_AI_PERCENT:.0f}%."
        )
    if plagiarism_percent > MAX_PLAGIARISM_PERCENT:
        breaches.append(
            f"Plagiarism is {plagiarism_percent:.0f}% — the SOP requires under "
            f"{MAX_PLAGIARISM_PERCENT:.0f}%."
        )
    return {
        "checked": True, "passed": not breaches, "breaches": breaches,
        "ai_percent": ai_percent, "plagiarism_percent": plagiarism_percent,
        "ai_limit": MAX_AI_PERCENT, "plagiarism_limit": MAX_PLAGIARISM_PERCENT,
    }


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
        "official statistics", "census", "peer-reviewed", "peer reviewed",
        "journal of", "filing", "annual report", "gazette", "parliament",
        "regulator",
        # The TIES Content SOP names Google Scholar as the primary route to
        # peer-reviewed research and empirical data.
        "google scholar", "scholar.google", "doi.org", "pubmed", "arxiv",
        "rbi", "reserve bank of india", "niti aayog", "sebi", "trai"],
    2: ["reuters", "associated press", "(ap)", "afp", "bloomberg", "pti",
        "press trust of india"],
    3: ["new york times", "the guardian", "bbc", "the hindu", "financial times",
        "washington post", "university", "institute", "think tank", "council on",
        # Verified media houses named in the TIES Content SOP.
        "indian express", "firstpost", "the print", "scroll.in", "mint",
        "business standard", "economic times", "hindustan times"],
    4: ["expert", "professor", "analyst", "industry report", "according to a report"],
    5: ["blog", "op-ed", "opinion piece", "medium.com", "substack"],
    6: ["twitter", "x.com", "facebook", "instagram", "tiktok", "telegram", "whatsapp"],
}

@lru_cache(maxsize=1)
def _tier_patterns() -> Dict[int, "re.Pattern[str]"]:
    """Word-boundary matchers per tier.

    Plain substring matching produced false positives that scored the top media
    tier: "he went to university" matched "university", "the hospital" matched
    "pti". Boundaries are only applied where the term starts/ends with a word
    character, so "(ap)" and "scholar.google" still match literally.
    """
    out: Dict[int, "re.Pattern[str]"] = {}
    for tier, terms in SOURCE_TIERS.items():
        parts = []
        for term in terms:
            esc = re.escape(term)
            if term[:1].isalnum():
                esc = r"\b" + esc
            if term[-1:].isalnum():
                esc = esc + r"\b"
            parts.append(esc)
        out[tier] = re.compile("|".join(parts), re.IGNORECASE)
    return out


def tiers_present(text: str) -> List[int]:
    """Source tiers cited anywhere in `text`, best (lowest number) first."""
    return sorted(t for t, pat in _tier_patterns().items() if pat.search(text))


def best_tier(text: str) -> int:
    """Best source tier cited, or 99 when none is found."""
    found = tiers_present(text)
    return found[0] if found else 99


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
