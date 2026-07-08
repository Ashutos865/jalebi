"""Persist and query evaluation history."""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Document, Evaluation, User
from app.schemas.evaluation import EvaluationRequest, EvaluationResult
from app.util import utcnow


async def _upsert_document(
    session: AsyncSession, req: EvaluationRequest, owner: Optional[User]
) -> Optional[Document]:
    if not req.doc_id:
        return None
    doc = (
        await session.execute(
            select(Document).where(Document.google_doc_id == req.doc_id)
        )
    ).scalar_one_or_none()
    if doc is None:
        doc = Document(
            google_doc_id=req.doc_id,
            url=req.doc_url,
            title=req.title or "Untitled",
            owner_id=owner.id if owner else None,
            content_type=req.content_type.value,
        )
        session.add(doc)
    else:
        doc.title = req.title or doc.title
        if req.doc_url:
            doc.url = req.doc_url
        doc.updated_at = utcnow()
    await session.flush()
    return doc


async def save_evaluation(
    session: AsyncSession, *, req: EvaluationRequest, result: EvaluationResult,
    owner: Optional[User],
) -> Evaluation:
    doc = await _upsert_document(session, req, owner)
    row = Evaluation(
        owner_id=owner.id if owner else None,
        document_id=doc.id if doc else None,
        google_doc_id=req.doc_id,
        title=req.title or "Untitled",
        content_type=result.content_type.value,
        provider=result.meta.evaluator,
        model=result.meta.model,
        overall_score=result.overall_score,
        publication_ready=result.publication_ready,
        publication_readiness=result.publication_readiness.value,
        word_count=result.meta.word_count,
        duration_ms=result.meta.duration_ms,
        result=result.model_dump(mode="json"),
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


def _summary(e: Evaluation) -> dict:
    return {
        "id": e.id, "title": e.title, "content_type": e.content_type,
        "provider": e.provider, "model": e.model, "overall_score": e.overall_score,
        "publication_readiness": e.publication_readiness,
        "publication_ready": e.publication_ready, "word_count": e.word_count,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "owner_id": e.owner_id, "google_doc_id": e.google_doc_id,
    }


async def list_evaluations(
    session: AsyncSession, *, owner_id: Optional[int] = None, limit: int = 50
) -> List[dict]:
    q = select(Evaluation).order_by(desc(Evaluation.created_at)).limit(limit)
    if owner_id is not None:
        q = q.where(Evaluation.owner_id == owner_id)
    rows = (await session.execute(q)).scalars().all()
    return [_summary(r) for r in rows]


async def get_evaluation(session: AsyncSession, eval_id: int) -> Optional[Evaluation]:
    return await session.get(Evaluation, eval_id)
