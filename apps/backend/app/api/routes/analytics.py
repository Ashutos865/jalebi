"""Analytics API — editor/founder metrics."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_role
from app.db.base import get_session
from app.db.models import ROLE_EDITOR, User
from app.services import analytics

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview")
async def overview(
    _: User = Depends(require_role(ROLE_EDITOR)),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await analytics.overview(session)
