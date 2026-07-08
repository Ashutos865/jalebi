"""Tracked-document insights — the link database + each article's trajectory.

Answers "what article is going where, and how": for every Google Doc Jalebi has seen,
its link, latest score & readiness, how many revisions, and whether it's improving.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Document, Evaluation, User


async def list_documents(session: AsyncSession) -> List[dict]:
    docs = (await session.execute(select(Document))).scalars().all()
    evals = (await session.execute(select(Evaluation))).scalars().all()
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
        owner = users.get((latest or first).owner_id) if (latest or first) else None
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
            "title": (latest.title if latest else (doc.title if doc else "Untitled")),
            "content_type": latest.content_type if latest else (doc.content_type if doc else ""),
            "owner": owner.email if owner else None,
            # SOP tracking-sheet fields
            "status": doc.status if doc else "draft",
            "suggested_status": suggested,
            "editor": doc.editor if doc else "",
            "published_for": doc.published_for if doc else "",
            "co_authors": doc.co_authors if doc else "",
            "revisions": len(rows),
            "first_score": first_score,
            "latest_score": latest_score,
            "trend": trend,
            "latest_readiness": readiness,
            "publication_ready": latest.publication_ready if latest else False,
            "last_evaluated": latest.created_at.isoformat() if latest and latest.created_at else None,
        })
    out.sort(key=lambda d: d["last_evaluated"] or "", reverse=True)
    return out
