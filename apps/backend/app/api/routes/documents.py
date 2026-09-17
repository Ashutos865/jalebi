"""Documents — the tracked-link database + per-article trajectory + SOP tracking fields."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_role
from app.db.base import get_session
from app.db.models import ROLE_EDITOR, Document, User
from app.scoring.constitution import integrity_verdict
from app.services import documents
from app.services.audit import log_action
from app.util import utcnow

router = APIRouter(prefix="/documents", tags=["documents"])

_STATUSES = {"draft", "under_review", "finalized", "published"}


@router.get("")
async def list_docs(
    _: User = Depends(require_role(ROLE_EDITOR)),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    return await documents.list_documents(session)


class DocPatch(BaseModel):
    status: Optional[str] = None
    editor: Optional[str] = None
    published_for: Optional[str] = None
    co_authors: Optional[str] = None


@router.patch("/{google_doc_id}")
async def patch_doc(
    google_doc_id: str,
    body: DocPatch,
    user: User = Depends(require_role(ROLE_EDITOR)),
    session: AsyncSession = Depends(get_session),
) -> dict:
    doc = (
        await session.execute(
            select(Document).where(Document.google_doc_id == google_doc_id)
        )
    ).scalar_one_or_none()
    if doc is None:
        raise HTTPException(404, "Document not tracked yet.")
    if body.status is not None:
        if body.status not in _STATUSES:
            raise HTTPException(422, f"status must be one of {sorted(_STATUSES)}")
        doc.status = body.status
    if body.editor is not None:
        doc.editor = body.editor
    if body.published_for is not None:
        doc.published_for = body.published_for
    if body.co_authors is not None:
        doc.co_authors = body.co_authors
    await session.commit()
    await log_action(session, actor=user, action="document.update", target=doc.title,
                     meta={"status": doc.status})
    return {"ok": True, "status": doc.status, "editor": doc.editor,
            "published_for": doc.published_for, "co_authors": doc.co_authors}


class IntegrityPatch(BaseModel):
    """AI/plagiarism percentages from the editor's checker (SOP §4).

    Recorded, never estimated: the SOP names Quillbot, CopyLeaks, SmallSEOTools
    and DupliChecker for this, and a guessed number could wrongly accuse a
    writer in a process that affects their certificate and LOR.
    """

    ai_percent: float = Field(..., ge=0, le=100)
    plagiarism_percent: float = Field(..., ge=0, le=100)


@router.put("/{google_doc_id}/integrity")
async def set_integrity(
    google_doc_id: str,
    body: IntegrityPatch,
    user: User = Depends(require_role(ROLE_EDITOR)),
    session: AsyncSession = Depends(get_session),
) -> dict:
    doc = (
        await session.execute(
            select(Document).where(Document.google_doc_id == google_doc_id)
        )
    ).scalar_one_or_none()
    if doc is None:
        raise HTTPException(404, "Document not tracked yet.")

    doc.ai_percent = body.ai_percent
    doc.plagiarism_percent = body.plagiarism_percent
    doc.integrity_checked_by = user.email
    doc.integrity_checked_at = utcnow()
    await session.commit()

    verdict = integrity_verdict(doc.ai_percent, doc.plagiarism_percent)
    await log_action(
        session, actor=user, action="document.integrity", target=doc.title,
        meta={"ai_percent": doc.ai_percent,
              "plagiarism_percent": doc.plagiarism_percent,
              "passed": verdict["passed"]},
    )
    return {"ok": True, **verdict}
