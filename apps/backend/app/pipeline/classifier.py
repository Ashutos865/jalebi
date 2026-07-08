"""Content-type auto-classifier.

Heuristic, dependency-free, deterministic — so it works in mock mode and offline, and
returns instantly for the sidebar's "Detect" button. It scores the document against
signal patterns for each content type and returns the best match plus a confidence.

Signals are structural/lexical cues an editor would recognize (a dateline for a press
release, scene directions for a script, an Abstract for a research paper, …).
"""
from __future__ import annotations

import re
from typing import Dict, List, Tuple

from app.schemas.evaluation import ContentType

# (weight, compiled pattern) per content type. Patterns are case-insensitive.
def _p(*patterns: str) -> List[re.Pattern]:
    return [re.compile(p, re.I) for p in patterns]


_SIGNALS: Dict[ContentType, List[re.Pattern]] = {
    ContentType.press_release: _p(
        r"for immediate release", r"\bhttps?://.*/(press|news)", r"###\s*$",
        r"\bmedia (contact|enquir)", r"\bannounc(ed|es|ing)\b",
    ),
    ContentType.research_paper: _p(
        r"\babstract\b", r"\bmethodolog", r"\breferences\b", r"\bhypothes",
        r"\bet al\.", r"\bfindings\b", r"\bliterature review\b",
    ),
    ContentType.policy_analysis: _p(
        r"\bpolicy\b", r"\bstakeholders?\b", r"\brecommendations?\b", r"\bregulat",
        r"\bimplications?\b", r"\bframework\b", r"\bgovernance\b",
    ),
    ContentType.youtube_script: _p(
        r"\[intro\]", r"\bb-?roll\b", r"\bcut to\b", r"\bsubscribe\b",
        r"\bvoice ?over\b", r"\bon screen\b", r"\bsmash that\b",
    ),
    ContentType.instagram_script: _p(
        r"\breel\b", r"\bswipe\b", r"\bhook:\b", r"#\w+", r"\bcaption:\b",
        r"\blink in bio\b",
    ),
    ContentType.twitter_thread: _p(
        r"🧵", r"^\s*\d+/\d*\s", r"\bthread\b", r"^\s*\d+\.\s", r"\bRT\b",
    ),
    ContentType.newsletter: _p(
        r"\bsubscribe\b", r"\bthis week\b", r"\bin this (issue|edition)\b",
        r"\bhey (there|friends|everyone)\b", r"\bforward this\b",
    ),
    ContentType.speech: _p(
        r"ladies and gentlemen", r"\bthank you (all|for)\b", r"\btoday,? i (want|stand)",
        r"\bmy fellow\b", r"\bin conclusion\b.*\bthank you\b",
    ),
    ContentType.explainer: _p(
        r"\bwhat is\b", r"\bhere'?s how\b", r"\blet'?s break (this |it )?down\b",
        r"\bin simple terms\b", r"\bstep \d\b", r"\bhow does\b",
    ),
    ContentType.case_study: _p(
        r"\bbackground\b", r"\bthe challenge\b", r"\bthe solution\b", r"\bresults?\b",
        r"\boutcome\b", r"\bclient\b", r"\bkey takeaways\b",
    ),
    ContentType.linkedin_article: _p(
        r"\bin my experience\b", r"\bfounder\b", r"\blessons? (i|we) learned\b",
        r"\bcareer\b", r"\bagree\?$", r"\bthoughts\?$",
    ),
    ContentType.opinion: _p(
        r"\bi (believe|think|argue)\b", r"\bin my (view|opinion)\b", r"\bwe must\b",
        r"\bshould\b.*\bnot\b", r"\bit'?s time (to|we)\b",
    ),
    ContentType.editorial: _p(
        r"\bthe government (must|should)\b", r"\bour (view|position)\b",
        r"\bthis newspaper\b", r"\bwe urge\b",
    ),
    ContentType.news_article: _p(
        r"\baccording to\b", r"\bsaid\b", r"\breuters\b", r"\bpti\b", r"\bon (monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        r"\breported\b", r"\bofficials?\b",
    ),
}


def classify(text: str, title: str = "") -> Dict:
    blob = f"{title}\n{text}"
    scores: Dict[str, int] = {}
    for ct, patterns in _SIGNALS.items():
        hits = sum(1 for p in patterns if p.search(blob))
        if hits:
            scores[ct.value] = hits

    if not scores:
        # No strong signal → default to the most general type, low confidence.
        return {"content_type": ContentType.news_article.value,
                "confidence": 0.2, "scores": {}}

    ranked: List[Tuple[str, int]] = sorted(scores.items(), key=lambda kv: -kv[1])
    top_key, top = ranked[0]
    total = sum(scores.values())
    # Confidence: share of matched signals going to the winner, tempered by how many
    # distinct signals it hit (a single lucky match shouldn't read as certain).
    confidence = round(min(0.95, (top / total) * min(1.0, top / 3 + 0.34)), 2)
    return {"content_type": top_key, "confidence": confidence, "scores": scores}
