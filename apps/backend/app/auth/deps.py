"""FastAPI auth dependencies."""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import decode_token
from app.auth.service import has_role
from app.config import settings
from app.db.base import get_session
from app.db.models import User


def _bearer(request: Request) -> Optional[str]:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return None


async def current_user_optional(
    request: Request, session: AsyncSession = Depends(get_session)
) -> Optional[User]:
    token = _bearer(request)
    if not token:
        return None
    payload = decode_token(token)
    if not payload:
        return None
    try:
        return await session.get(User, int(payload["sub"]))
    except (KeyError, ValueError, TypeError):
        return None


async def current_user(
    user: Optional[User] = Depends(current_user_optional),
) -> User:
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return user


def require_role(minimum: str):
    async def _dep(user: User = Depends(current_user)) -> User:
        if not has_role(user, minimum):
            raise HTTPException(
                status_code=403, detail=f"Requires {minimum} role or higher."
            )
        return user

    return _dep


async def maybe_require_auth(
    user: Optional[User] = Depends(current_user_optional),
) -> Optional[User]:
    """Enforce auth only when JALEBI_REQUIRE_AUTH is on (keeps P1/P2 open by default)."""
    if settings.require_auth and user is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return user
