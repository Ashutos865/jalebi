"""Tracked-document insights — the link database + each article's trajectory.

Answers "what article is going where, and how": for every Google Doc Jalebi has seen,
its link, latest score & readiness, how many revisions, and whether it's improving.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer

# Evaluations considered when building each document's trajectory. The tracker
# shows first/latest score and a revision count, so a bounded recent window is
# sufficient and keeps the query flat as history grows.
MAX_EVALUATIONS = 5000

from app.db.models import Document, Evaluation, User
from app.scoring.constitution import integrity_verdict
from app.util import iso
from app.workflow import service as workflow


def _sla_out(doc: Optional[Document]) -> dict:
    """Where the current SOP phase stands. Empty when the doc has no clock."""
    if doc is None:
        return {"phase": None, "overdue": False, "at_risk": False}
    sla = workflow.sla_for(doc)
    return {
        "phase": sla.phase,
        "due_at": iso(sla.due_at),
        "hours_remaining": sla.hours_remaining,
        "overdue": sla.overdue,
        "at_risk": sla.at_risk,
    }


async def list_documents(session: AsyncSession) -> List[dict]:
    docs = (await session.execute(select(Document))).scalars().all()
    # `result` is the full stored scorecard (10-50 kB per row) and nothing here
    # reads it — only scores, readiness and timestamps. Deferring it turns a
    # multi-megabyte fetch into a cheap one.
    evals = (await session.execute(
        select(Evaluation)
        .options(defer(Evaluation.result))
        .order_by(Evaluation.created_at.desc())
        .limit(MAX_EVALUATIONS)
    )).scalars().all()
    users = {u.id: u for u in (await session.execute(select(User))).scalars().all()}

    by_doc: Dict[str, List[Evaluation]] = defaultdict(list)
    for e in evals:
        if e.google_doc_id:
            by_doc[e.google_doc_id].append(e)

    url_by_id = {d.google_doc_id: d for d in docs if d.google_doc_id}
    # Also include docs known only from evaluations (no Document row yet).
    all_ids = set(by_doc) | set(url_by_id)

    out: List[dict] = []
    for gid in all_ids:
        rows = sorted(by_doc.get(gid, []), key=lambda e: e.created_at or 0)
        doc = url_by_id.get(gid)
        if not rows and not doc:
            continue
        first = rows[0] if rows else None
        latest = rows[-1] if rows else None
        # The first identified author keeps the credit. Taking it from the
        # latest evaluation meant one anonymous re-run blanked the writer's
        # name from the tracker.
        owner_id = next((e.owner_id for e in rows if e.owner_id), None)
        if owner_id is None and doc is not None:
            owner_id = doc.owner_id
        owner = users.get(owner_id) if owner_id else None
        first_score = first.overall_score if first else None
        latest_score = latest.overall_score if latest else None
        trend = (latest_score - first_score) if (first_score is not None and latest_score is not None) else 0
        readiness = latest.publication_readiness if latest else None
        suggested = {
            "Ready to Publish": "finalized",
            "Needs Minor Revision": "under_review",
            "Needs Major Revision": "under_review",
            "Not Ready": "draft",
        }.get(readiness or "", "draft")
        out.append({
            "google_doc_id": gid,
            "url": (doc.url if doc else None) or (
                f"https://docs.google.com/document/d/{gid}/edit" if gid else None
            ),
            # The Document's title is authoritative, since writing it is
            # permission-checked. Preferring the latest Evaluation's title let
            # an anonymous /api/evaluate rename someone else's tracked article.
            "title": (doc.title if doc else (latest.title if latest else "Untitled")),
            "content_type": latest.content_type if latest else (doc.content_type if doc else ""),
            "owner": owner.email if owner else None,
            # SOP tracking-sheet fields
            "status": doc.status if doc else "draft",
            "suggested_status": suggested,
            "editor": doc.editor if doc else "",
            "published_for": doc.published_for if doc else "",
            "co_authors": doc.co_authors if doc else "",
            # SOP §4 research integrity — recorded from the editor's checker.
            "integrity": integrity_verdict(
                doc.ai_percent if doc else None,
                doc.plagiarism_percent if doc else None,
            ),
            "integrity_checked_by": doc.integrity_checked_by if doc else "",
            "integrity_checked_at": iso(
                doc.integrity_checked_at if doc else None
            ),
            # Production loop (SOP §3): who owes what, and by when.
            "assigned_to": doc.assigned_to if doc else "",
            "approved_by": doc.approved_by if doc else "",
            "escalation_reason": doc.escalation_reason if doc else "",
            "override_reason": doc.override_reason if doc else "",
            "sla": _sla_out(doc),
            "revisions": len(rows),
            "first_score": first_score,
            "latest_score": latest_score,
            "trend": trend,
            "latest_readiness": readiness,
            "publication_ready": latest.publication_ready if latest else False,
            "last_evaluated": iso(latest.created_at if latest else None),
        })
    out.sort(key=lambda d: d["last_evaluated"] or "", reverse=True)
    return out
