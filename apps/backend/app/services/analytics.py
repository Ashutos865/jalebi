"""Analytics — aggregates over the evaluation history.

Computed in Python from the fetched rows: portable across SQLite/Postgres and plenty
fast at TIES' ~100-user scale. Powers the founder/editor dashboard and /api/analytics.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Evaluation, User


def _avg(nums: List[int]) -> float:
    return round(sum(nums) / len(nums), 1) if nums else 0.0


async def overview(session: AsyncSession) -> Dict:
    rows = (await session.execute(select(Evaluation))).scalars().all()
    users = {u.id: u for u in (await session.execute(select(User))).scalars().all()}
    total = len(rows)
    if total == 0:
        return {"total_evaluations": 0, "empty": True}

    scores = [r.overall_score for r in rows]
    ready = sum(1 for r in rows if r.publication_ready)

    by_ct: Dict[str, List[int]] = defaultdict(list)
    ct_ready: Dict[str, int] = defaultdict(int)
    for r in rows:
        by_ct[r.content_type].append(r.overall_score)
        ct_ready[r.content_type] += int(r.publication_ready)

    by_provider: Dict[str, List[int]] = defaultdict(list)
    for r in rows:
        by_provider[r.provider].append(r.overall_score)

    readiness = Counter(r.publication_readiness for r in rows)

    # Most common critical issues across all evaluations.
    issue_counter: Counter = Counter()
    for r in rows:
        for issue in (r.result or {}).get("critical_issues", []):
            issue_counter[issue.get("problem", "")] += 1

    # Writer performance.
    writer_scores: Dict[int, List[int]] = defaultdict(list)
    writer_ready: Dict[int, int] = defaultdict(int)
    for r in rows:
        if r.owner_id:
            writer_scores[r.owner_id].append(r.overall_score)
            writer_ready[r.owner_id] += int(r.publication_ready)

    writers = [
        {
            "email": users[uid].email if uid in users else f"user:{uid}",
            "department": users[uid].department if uid in users else "",
            "evaluations": len(s),
            "avg_score": _avg(s),
            "pass_rate": round(writer_ready[uid] / len(s) * 100, 1),
        }
        for uid, s in writer_scores.items()
    ]
    writers.sort(key=lambda w: w["avg_score"], reverse=True)

    # Revision frequency (docs evaluated more than once).
    per_doc: Counter = Counter(r.google_doc_id for r in rows if r.google_doc_id)
    revised = [c for c in per_doc.values() if c > 1]

    # Daily trend.
    daily: Dict[str, List[int]] = defaultdict(list)
    for r in rows:
        if r.created_at:
            daily[r.created_at.date().isoformat()].append(r.overall_score)
    trend = [
        {"date": d, "count": len(s), "avg_score": _avg(s)}
        for d, s in sorted(daily.items())
    ][-30:]

    return {
        "total_evaluations": total,
        "avg_score": _avg(scores),
        "pass_rate": round(ready / total * 100, 1),
        "readiness_breakdown": dict(readiness),
        "by_content_type": [
            {"content_type": ct, "count": len(s), "avg_score": _avg(s),
             "pass_rate": round(ct_ready[ct] / len(s) * 100, 1)}
            for ct, s in sorted(by_ct.items(), key=lambda kv: -len(kv[1]))
        ],
        "by_provider": [
            {"provider": p, "count": len(s), "avg_score": _avg(s)}
            for p, s in sorted(by_provider.items(), key=lambda kv: -len(kv[1]))
        ],
        "top_issues": [
            {"problem": prob, "count": c}
            for prob, c in issue_counter.most_common(10) if prob
        ],
        "writers": writers[:25],
        "revision_frequency": {
            "docs_revised": len(revised),
            "avg_revisions": round(sum(revised) / len(revised), 1) if revised else 0.0,
        },
        "trend": trend,
    }
