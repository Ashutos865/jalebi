"""Evaluation history — a writer sees their own; editors/admins see all."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import current_user
from app.auth.service import has_role
from app.db.base import get_session
from app.db.models import ROLE_EDITOR, User
from app.services import history

router = APIRouter(prefix="/evaluations", tags=["history"])


@router.get("")
async def list_mine(
    limit: int = 50,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    # Editors and admins can see everyone's; writers see their own.
    owner_id = None if has_role(user, ROLE_EDITOR) else user.id
    return await history.list_evaluations(session, owner_id=owner_id, limit=limit)


@router.get("/{eval_id}")
async def get_one(
    eval_id: int,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    row = await history.get_evaluation(session, eval_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Evaluation not found.")
    if not has_role(user, ROLE_EDITOR) and row.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Not your evaluation.")
    return row.result
