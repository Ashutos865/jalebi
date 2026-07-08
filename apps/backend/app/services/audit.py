"""Audit logging helper (best-effort)."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog, User


async def log_action(
    session: AsyncSession, *, actor: Optional[User], action: str,
    target: str = "", meta: Optional[dict] = None,
) -> None:
    try:
        session.add(AuditLog(
            actor_id=actor.id if actor else None,
            actor_email=actor.email if actor else "",
            action=action, target=target, meta=meta or {},
        ))
        await session.commit()
    except Exception:
        await session.rollback()
