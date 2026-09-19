"""User provisioning + role helpers."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import ROLE_ADMIN, ROLE_RANK, ROLE_WRITER, User
from app.util import utcnow


def _initial_role(email: str) -> str:
    return ROLE_ADMIN if email.lower() in {e.lower() for e in settings.admin_emails} else ROLE_WRITER


def _email_allowed(email: str) -> bool:
    email = email.lower()
    emails = {e.lower() for e in settings.allowed_emails}
    domains = {d.lower().lstrip("@") for d in settings.allowed_domains}
    if not emails and not domains:
        return True  # no allow-list configured (dev)
    if email in emails:
        return True
    domain = email.split("@")[-1]
    return domain in domains


def check_login_allowed(email: str, secret: str) -> tuple[bool, int, str]:
    """Gate email/secret login. Returns (ok, http_status, message)."""
    if not settings.allow_dev_login:
        return False, 403, "Email/secret login is disabled."
    if "@" not in email:
        return False, 422, "A valid email is required."
    if settings.signup_secret and secret != settings.signup_secret:
        return False, 401, "Invalid signup secret."
    if not _email_allowed(email):
        return False, 403, "This email is not on the allow-list."
    return True, 200, ""


async def _find(session: AsyncSession, email: str) -> Optional[User]:
    return (
        await session.execute(select(User).where(User.email == email))
    ).scalar_one_or_none()


def _apply_login(user: User, *, email: str, name: str, google_sub: Optional[str]) -> None:
    if name and not user.name:
        user.name = name
    if google_sub:
        user.google_sub = google_sub
    # Founders listed in admin_emails are always promoted.
    if email in {e.lower() for e in settings.admin_emails} and ROLE_RANK[user.role] < ROLE_RANK[ROLE_ADMIN]:
        user.role = ROLE_ADMIN
    user.last_login = utcnow()


async def get_or_create_user(
    session: AsyncSession, *, email: str, name: str = "", google_sub: Optional[str] = None
) -> User:
    """Look the user up, creating them on first sight.

    Check-then-insert races on `users.email`, which is unique: two logins
    arriving together both found no row, both inserted, and the second got an
    unhandled IntegrityError -- a 500 on a new writer's very first login, from
    nothing worse than a browser firing two auth requests. Losing the insert is
    expected here, so it is caught and the row the winner committed is read
    back.
    """
    email = email.strip().lower()

    user = await _find(session, email)
    if user is not None:
        _apply_login(user, email=email, name=name, google_sub=google_sub)
        await session.commit()
        await session.refresh(user)
        return user

    user = User(email=email, name=name or email.split("@")[0], role=_initial_role(email))
    _apply_login(user, email=email, name=name, google_sub=google_sub)
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:
        # Someone else created this user between our read and our insert.
        await session.rollback()
        user = await _find(session, email)
        if user is None:
            raise
        _apply_login(user, email=email, name=name, google_sub=google_sub)
        await session.commit()

    await session.refresh(user)
    return user


def has_role(user: User, minimum: str) -> bool:
    return ROLE_RANK.get(user.role, 0) >= ROLE_RANK.get(minimum, 0)
