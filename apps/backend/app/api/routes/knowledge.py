"""Editorial knowledge base API (admin-managed; retrieval is internal to evaluators)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import current_user, require_role
from app.db.base import get_session
from app.db.models import ROLE_ADMIN, ROLE_EDITOR, KnowledgeDoc, User
from app.knowledge import service
from app.knowledge.store import get_store
from app.services.audit import log_action

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

KINDS = {"handbook", "approved", "rejected", "note", "example", "style", "methodology"}


class KnowledgeIn(BaseModel):
    kind: str
    title: str
    content: str
    content_type: Optional[str] = None


@router.get("")
async def list_docs(
    _: User = Depends(require_role(ROLE_EDITOR)),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    rows = (await session.execute(select(KnowledgeDoc))).scalars().all()
    return [
        {"id": d.id, "kind": d.kind, "title": d.title,
         "content_type": d.content_type, "chars": len(d.content)}
        for d in rows
    ]


@router.post("")
async def add_doc(
    body: KnowledgeIn,
    user: User = Depends(require_role(ROLE_EDITOR)),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if body.kind not in KINDS:
        raise HTTPException(status_code=422, detail=f"kind must be one of {sorted(KINDS)}")
    doc = await service.create_knowledge_doc(
        session, kind=body.kind, title=body.title, content=body.content,
        content_type=body.content_type, created_by=user.id,
    )
    await log_action(session, actor=user, action="knowledge.add", target=doc.title)
    return {"id": doc.id, "indexed_vectors": get_store().count()}


@router.delete("/{doc_id}")
async def delete_doc(
    doc_id: int,
    user: User = Depends(require_role(ROLE_ADMIN)),
    session: AsyncSession = Depends(get_session),
) -> dict:
    await session.execute(delete(KnowledgeDoc).where(KnowledgeDoc.id == doc_id))
    await session.commit()
    await service.reindex_all(session)
    await log_action(session, actor=user, action="knowledge.delete", target=str(doc_id))
    return {"ok": True, "indexed_vectors": get_store().count()}


@router.get("/search")
async def search(
    q: str, content_type: Optional[str] = None,
    _: User = Depends(current_user),
) -> list[dict]:
    passages = await service.retrieve_passages(q, content_type or "")
    return [{"passage": p} for p in passages]
