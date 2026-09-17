"""Hybrid scorer — combines deterministic rules with AI judgment.

final_dimension = alpha * rule_score + (1 - alpha) * ai_score   (per dimension)
overall         = Σ weight[dimension] * final_dimension          (content-type weights)
overall         = min(overall, lowest triggered hard cap)        (Constitution §C)

AI dimension scores are quantised to the nearest 5 so residual model jitter cannot
move the final number. With rules driving ~70% and caps deterministic, identical
content yields an identical score.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from app.scoring import constitution as C
from app.scoring.rules import RuleReport, CheckItem
from app.schemas.evaluation import (
    CategoryScore, Issue, Priority, PublicationReadiness,
)

_PRIORITY = {"critical": Priority.critical, "high": Priority.high,
             "medium": Priority.medium, "low": Priority.low}
_PRANK = {Priority.critical: 0, Priority.high: 1, Priority.medium: 2, Priority.low: 3}


@dataclass
class AIReport:
    """The constrained output the model returns (see scoring/ai_prompt.py)."""
    dim_scores: Dict[str, int] = field(default_factory=dict)
    issues: List[Tuple[str, Issue]] = field(default_factory=list)  # (dim, issue)
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    summary: str = ""


@dataclass
class Composed:
    overall: int
    publication_ready: bool
    readiness: PublicationReadiness
    categories: List[CategoryScore]
    critical_issues: List[Issue]
    strengths: List[str]
    next_steps: List[str]
    summary: str


def _q5(v: int) -> int:
    return int(round(v / 5.0) * 5)


def combine(rules: RuleReport, ai: AIReport, content_type: str) -> Composed:
    weights = C.weights_for(content_type)

    # Bucket every issue (deterministic + AI) by dimension.
    by_dim: Dict[str, List[Issue]] = {k: [] for k in C.DIM_KEYS}
    for ri in rules.issues:
        by_dim.setdefault(ri.dim, []).append(Issue(
            problem=ri.problem, explanation=ri.explanation, impact=ri.impact,
            suggestion=ri.suggestion, priority=_PRIORITY.get(ri.priority, Priority.medium),
            quote=ri.quote, options=[],
        ))
    for dim, issue in ai.issues:
        by_dim.setdefault(dim if dim in by_dim else "accuracy", []).append(issue)

    # Per-dimension blend + build category rows.
    categories: List[CategoryScore] = []
    for d in C.DIMENSIONS:
        rule_s = rules.dim_scores.get(d.key, 60)
        ai_s = _q5(ai.dim_scores.get(d.key, rule_s))
        final = int(round(d.alpha * rule_s + (1 - d.alpha) * ai_s))
        final = max(0, min(100, final))
        categories.append(CategoryScore(
            name=d.name, key=d.key, score=final, weight=weights.get(d.key, d.weight),
            summary=_dim_summary(d.key, rule_s, ai_s, final),
            issues=sorted(by_dim.get(d.key, []), key=lambda i: _PRANK[i.priority]),
            recommendations=[],
        ))

    base = sum(weights.get(c.key, 0.0) * c.score for c in categories)
    overall = int(round(base))

    # Hard caps override everything.
    ceiling = 100
    worst_cap = None
    for cap in rules.caps:
        if cap.ceiling < ceiling:
            ceiling = cap.ceiling
            worst_cap = cap
    overall = max(0, min(overall, ceiling))

    readiness_label, ready = C.band_for(overall)
    readiness = PublicationReadiness(readiness_label)

    # Cap violations surface as critical issues, most severe first.
    critical: List[Issue] = []
    for cap in sorted(rules.caps, key=lambda c: c.ceiling):
        critical.append(Issue(
            problem=f"Hard rule: {cap.label}",
            explanation=f"This violates a TIES hard rule and caps the score at {cap.ceiling}.",
            impact="Publishing as-is would damage TIES' credibility.",
            suggestion="Resolve this before anything else — it limits the whole score.",
            priority=Priority.critical, quote=cap.quote or None, options=[],
        ))
    for c in categories:
        for i in c.issues:
            if i.priority in (Priority.critical, Priority.high):
                critical.append(i)
    # de-dup by (problem, quote), keep order
    seen = set()
    critical = [i for i in critical if (k := (i.problem, i.quote)) not in seen and not seen.add(k)]
    critical.sort(key=lambda i: _PRANK[i.priority])

    passed = sum(1 for c in rules.checklist if c.passed)
    total = len(rules.checklist)
    strengths = ai.strengths or _rule_strengths(rules.checklist)
    next_steps = _next_steps(critical, ai.weaknesses)

    summary = _summary(overall, readiness_label, passed, total, worst_cap, ai.summary)
    return Composed(
        overall=overall, publication_ready=ready, readiness=readiness,
        categories=categories, critical_issues=critical[:8],
        strengths=strengths[:5], next_steps=next_steps[:6], summary=summary,
    )


def _dim_summary(key: str, rule_s: int, ai_s: int, final: int) -> str:
    return f"{final}/100 · rules {rule_s}, judgment {ai_s}"


def _rule_strengths(checklist: List[CheckItem]) -> List[str]:
    return [f"{c.name}" for c in checklist if c.passed][:5]


def _next_steps(critical: List[Issue], weaknesses: List[str]) -> List[str]:
    steps = [i.suggestion for i in critical[:4] if i.suggestion]
    steps += [w for w in weaknesses if w]
    out, seen = [], set()
    for s in steps:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _summary(overall: int, readiness: str, passed: int, total: int, worst_cap, ai_summary: str) -> str:
    line = f"{readiness} — {overall}/100. Passed {passed} of {total} editorial checks."
    if worst_cap is not None:
        line += f" Score capped at {worst_cap.ceiling} by a hard rule: {worst_cap.label}."
    if ai_summary:
        line += " " + ai_summary.strip()
    return line
