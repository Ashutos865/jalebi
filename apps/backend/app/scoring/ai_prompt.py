"""The AI-judgment half of the hybrid scorer.

The model does NOT assign the final number. It scores each dimension against the
Constitution and detects issues — concentrating on what rules cannot measure
(originality, insight, narrative, depth). The engine blends this with the
deterministic rules and applies the weights and caps.
"""
from __future__ import annotations

import json
import re
from typing import List, Optional

from pydantic import ValidationError

from app.scoring import constitution as C
from app.scoring.engine import AIReport
from app.schemas.evaluation import Issue, Priority

_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)
# Reject echoed schema examples / placeholders (never show these to the user).
_PLACEHOLDER = re.compile(
    r"^\s*(<.*>|(grounded\s+)?rewrite\s*\d*|option\s*\d*|placeholder|\.\.\.|"
    r"a (second )?(distinct )?rewrite.*|an actual rewritten.*)\s*$",
    re.IGNORECASE,
)


def _clean_options(options) -> List[str]:
    out = []
    for o in options or []:
        s = str(o).strip()
        if s and not _PLACEHOLDER.match(s):
            out.append(s)
    return out[:4]


def _brief(content_type: str) -> str:
    w = C.weights_for(content_type)
    dims = "\n".join(
        f"  - {d.name} [{d.key}] — {int(round(w[d.key] * 100))}%" for d in C.DIMENSIONS
    )
    caps = "\n".join(f"  - {c.label} → score capped at {c.ceiling}" for c in C.HARD_CAPS.values())
    tiers = "; ".join(f"T{t}: {', '.join(v[:3])}" for t, v in C.SOURCE_TIERS.items())
    return (
        "TIES is a research-first publication. A piece is worth publishing only if, "
        "after reading it, the reader understands the world better than before. "
        "Optimise for accuracy, depth, originality, and long-term credibility over virality.\n\n"
        f"DIMENSIONS AND WEIGHTS (for this content type):\n{dims}\n\n"
        "SCORE BANDS: 90-100 immediately publishable and genuinely insightful; 80-89 "
        "strong, minor refinement; 70-79 informative but lacks depth/originality; 60-69 "
        "competent but ordinary, reads like a generic AI article, do not publish; below 60 "
        "fails standards. Publication threshold is 85.\n\n"
        f"HARD RULES (the engine enforces these caps deterministically):\n{caps}\n\n"
        f"SOURCE HIERARCHY: {tiers}. Social media is never sufficient alone.\n\n"
        "NEUTRALITY: evidence must lead conclusions. Emotion is fine; manipulation is not."
    )


def build_system(content_type: str, knowledge: Optional[List[str]] = None) -> str:
    kb = ""
    if knowledge:
        kb = "\n\nRELEVANT EDITORIAL STANDARDS (retrieved):\n" + "\n---\n".join(knowledge[:4])
    return (
        "You are the Senior Managing Editor of TIES, grading against the TIES Editorial "
        "Constitution below. You are a line editor and judge, NOT a fact generator.\n\n"
        f"{_brief(content_type)}{kb}\n\n"
        "DIVISION OF LABOUR: a deterministic engine already checks spelling, em dashes, "
        "AI clichés, absolutist bias phrases, source counts, unsourced statistics, headline "
        "alignment, and the hard-rule caps. Do NOT re-score mechanics. Concentrate your "
        "judgment on what rules cannot measure: original insight, narrative quality, depth, "
        "and genuine accuracy concerns.\n\n"
        "STRICT FACTUALITY: never invent facts, numbers, names, sources, or quotes. In "
        "rewrite options, rephrase the writer's own words only; where a fact is missing, use "
        "a bracketed placeholder like [cite source] or [figure].\n\n"
        "Return ONLY a JSON object with exactly these keys:\n"
        "{\n"
        '  "dim_scores": {"accuracy":0-100,"insight":0-100,"narrative":0-100,"depth":0-100,'
        '"sourcing":0-100,"writing":0-100,"headline":0-100},\n'
        '  "issues": [{"dimension":"insight","problem":"short label","explanation":"why it '
        'matters","impact":"editorial cost","suggestion":"how to fix","priority":'
        '"critical|high|medium|low","quote":"the exact passage copied from the article",'
        '"options":["an actual rewritten version of that passage","a second distinct rewrite"]}],\n'
        '  "strengths": ["..."],\n'
        '  "weaknesses": ["..."],\n'
        '  "summary": "2-3 sentences on why the piece lands where it does"\n'
        "}\n"
        "CRITICAL: every value must be real content about THIS article. `options` must be "
        "the passage genuinely rewritten in the author's voice — NEVER placeholder text like "
        "\"rewrite 1\", \"option 1\", or \"...\". If a passage cannot be improved by rephrasing "
        "(e.g. it needs a source that doesn't exist), return \"options\": [].\n"
        "Do NOT output an overall score — the engine computes it. Score honestly and "
        "consistently: the same article must always receive the same scores."
    )


def build_user(title: Optional[str], text: str) -> str:
    head = f"HEADLINE: {title}\n\n" if title else "HEADLINE: (none supplied)\n\n"
    return f"{head}ARTICLE:\n\"\"\"\n{text}\n\"\"\"\n\nReturn the JSON object now."


def strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = _FENCE.sub("", text)
    return text.strip()


def parse(raw: str) -> AIReport:
    """Parse the model's JSON into an AIReport. Tolerant: bad issues are skipped,
    missing dim scores fall back to the rule score later in the engine."""
    data = json.loads(strip_fences(raw))
    dim_scores = {}
    for k, v in (data.get("dim_scores") or {}).items():
        if k in C.DIM_KEYS:
            try:
                dim_scores[k] = max(0, min(100, int(round(float(v)))))
            except (TypeError, ValueError):
                continue

    issues = []
    for raw_issue in data.get("issues") or []:
        if not isinstance(raw_issue, dict):
            continue
        dim = str(raw_issue.get("dimension", "accuracy"))
        if dim not in C.DIM_KEYS:
            dim = "accuracy"
        try:
            issue = Issue(
                problem=str(raw_issue.get("problem", "")).strip() or "Editorial issue",
                explanation=str(raw_issue.get("explanation", "")).strip(),
                impact=str(raw_issue.get("impact", "")).strip(),
                suggestion=str(raw_issue.get("suggestion", "")).strip(),
                priority=_priority(raw_issue.get("priority")),
                quote=(str(raw_issue["quote"]).strip() if raw_issue.get("quote") else None),
                options=_clean_options(raw_issue.get("options")),
            )
        except ValidationError:
            continue
        issues.append((dim, issue))

    return AIReport(
        dim_scores=dim_scores,
        issues=issues,
        strengths=[str(s).strip() for s in (data.get("strengths") or []) if str(s).strip()],
        weaknesses=[str(s).strip() for s in (data.get("weaknesses") or []) if str(s).strip()],
        summary=str(data.get("summary", "")).strip(),
    )


def _priority(v) -> Priority:
    try:
        return Priority(str(v).lower())
    except ValueError:
        return Priority.medium
