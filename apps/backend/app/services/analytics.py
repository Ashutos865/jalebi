"""Analytics — aggregates over the evaluation history.

Aggregated in Python over a bounded, recent window rather than the whole table.
The previous version issued `SELECT *` over every evaluation on each dashboard
load, which pulled the full stored scorecard (10-50 kB of JSON per row) into
memory; the `result` column is now deferred and only sampled where it is
actually needed. Portable across SQLite/Postgres, and bounded regardless of how
much history accumulates.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Dict, List

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer

from app.db.models import Evaluation, User

# Most recent evaluations aggregated per dashboard load. Well above TIES' volume,
# and it keeps the query flat as history grows.
MAX_ROWS = 2000
# Smaller window for the critical-issue breakdown, which needs the JSON blob.
ISSUE_SAMPLE = 300


def _avg(nums: List[int]) -> float:
    return round(sum(nums) / len(nums), 1) if nums else 0.0


async def overview(session: AsyncSession) -> Dict:
    # Counted in SQL rather than in Python: an empty deployment must not pay for
    # a full scan just to learn there is nothing to report.
    total = (await session.execute(
        select(func.count()).select_from(Evaluation)
    )).scalar_one()
    if total == 0:
        return {"total_evaluations": 0, "empty": True}

    # `result` holds the complete EvaluationResult — realistically 10-50 kB per
    # row — and only its critical_issues list is read below. Deferring it keeps
    # a dashboard load from pulling every stored scorecard into memory.
    rows = (await session.execute(
        select(Evaluation)
        .options(defer(Evaluation.result))
        .order_by(Evaluation.created_at.desc())
        .limit(MAX_ROWS)
    )).scalars().all()
    # Critical issues come from a separate, smaller query over recent rows only.
    issue_rows = (await session.execute(
        select(Evaluation.result)
        .order_by(Evaluation.created_at.desc())
        .limit(ISSUE_SAMPLE)
    )).scalars().all()
    users = {u.id: u for u in (await session.execute(select(User))).scalars().all()}

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

    # Most common critical issues, over the recent sample.
    issue_counter: Counter = Counter()
    for result in issue_rows:
        for issue in (result or {}).get("critical_issues", []):
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
        # `total` is the true row count; every rate below is computed over the
        # analysed window, so they must divide by len(rows), not by total.
        "total_evaluations": total,
        "analysed": len(rows),
        "avg_score": _avg(scores),
        "pass_rate": round(ready / len(rows) * 100, 1) if rows else 0.0,
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
