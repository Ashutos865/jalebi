"""Shared scoring/aggregation policy.

Used by every evaluator that assembles categories itself (the mock and the
multi-agent pipeline) so publication-readiness and next-steps are computed one way.
The single-call LLM evaluator lets the model author these directly.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

from app.schemas.evaluation import (
    CategoryScore,
    Issue,
    Priority,
    PublicationReadiness,
)

PRIORITY_RANK = {
    Priority.critical: 0,
    Priority.high: 1,
    Priority.medium: 2,
    Priority.low: 3,
}


def judge_readiness(overall: int, issues: List[Issue]) -> PublicationReadiness:
    has_critical = any(i.priority == Priority.critical for i in issues)
    high_count = sum(1 for i in issues if i.priority == Priority.high)
    if has_critical or overall < 65:
        return PublicationReadiness.not_ready
    if overall >= 90 and high_count == 0:
        return PublicationReadiness.ready
    if overall >= 80 and high_count <= 1:
        return PublicationReadiness.minor
    return PublicationReadiness.major


def summarize(overall: int, readiness: PublicationReadiness, criticals: int,
              label: str) -> str:
    lead = {
        PublicationReadiness.ready: "This piece meets TIES standards and is ready to publish.",
        PublicationReadiness.minor: "This piece is close — a light editorial pass will get it there.",
        PublicationReadiness.major: "This piece needs substantive revision before it's publishable.",
        PublicationReadiness.not_ready: "This piece is not yet ready for publication.",
    }[readiness]
    tail = (f" {criticals} priority issue(s) to address first."
            if criticals else " No blocking issues stand out.")
    return f"{label} scored {overall}/100. {lead}{tail}"


def aggregate(categories: List[CategoryScore]) -> Dict:
    """Weighted overall + readiness + critical/strengths/next-steps from categories."""
    all_issues: List[Issue] = [i for c in categories for i in c.issues]
    overall = round(sum(c.score * c.weight for c in categories)) if categories else 0
    readiness = judge_readiness(overall, all_issues)

    critical = sorted(
        [i for i in all_issues if i.priority in (Priority.critical, Priority.high)],
        key=lambda i: PRIORITY_RANK[i.priority],
    )
    strengths = [
        f"{c.name} is strong ({c.score}/100)."
        for c in sorted(categories, key=lambda c: c.score, reverse=True)
        if c.score >= 85
    ][:4]
    if not strengths and categories:
        top = max(categories, key=lambda c: c.score)
        strengths = [f"{top.name} is the strongest area ({top.score}/100)."]

    next_steps: List[str] = []
    seen = set()
    for i in sorted(all_issues, key=lambda i: PRIORITY_RANK[i.priority]):
        if i.suggestion not in seen:
            seen.add(i.suggestion)
            next_steps.append(i.suggestion)
        if len(next_steps) >= 5:
            break
    if not next_steps:
        next_steps = ["No blocking issues — do a final read-through and publish."]

    return {
        "overall": overall,
        "readiness": readiness,
        "publication_ready": readiness == PublicationReadiness.ready,
        "critical_issues": critical,
        "strengths": strengths,
        "next_steps": next_steps,
    }
