"""Authentication routes: dev login, Google OAuth, and current user."""
from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import oauth
from app.auth.deps import current_user
from app.auth.security import create_access_token
from app.auth.service import check_login_allowed, get_or_create_user
from app.config import settings
from app.db.base import get_session
from app.db.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_out(u: User) -> dict:
    return {"id": u.id, "email": u.email, "name": u.name, "role": u.role,
            "department": u.department}


def _issue(u: User) -> dict:
    return {
        "access_token": create_access_token(user_id=u.id, email=u.email, role=u.role),
        "token_type": "bearer",
        "user": _user_out(u),
    }


class DevLogin(BaseModel):
    email: str
    name: str = ""
    secret: str = ""


@router.post("/dev-login")
async def dev_login(body: DevLogin, session: AsyncSession = Depends(get_session)) -> dict:
    """Email + shared-secret login. In production, gate with JALEBI_SIGNUP_SECRET and
    JALEBI_ALLOWED_EMAILS/DOMAINS so it isn't an open admin backdoor."""
    ok, status, message = check_login_allowed(body.email, body.secret)
    if not ok:
        raise HTTPException(status_code=status, detail=message)
    user = await get_or_create_user(session, email=body.email, name=body.name)
    return _issue(user)


@router.get("/google/login")
async def google_login() -> dict:
    if not oauth.is_configured():
        raise HTTPException(status_code=503, detail="Google OAuth is not configured.")
    state = secrets.token_urlsafe(16)
    return {"authorize_url": oauth.authorize_url(state), "state": state}


@router.get("/google/callback")
async def google_callback(
    code: str = Query(...), session: AsyncSession = Depends(get_session)
) -> HTMLResponse:
    if not oauth.is_configured():
        raise HTTPException(status_code=503, detail="Google OAuth is not configured.")
    info = await oauth.exchange_code(code)
    user = await get_or_create_user(
        session, email=info["email"], name=info.get("name", ""),
        google_sub=info.get("sub"),
    )
    token = _issue(user)["access_token"]
    # Minimal success page — the extension reads the token from here (or the user
    # pastes it into settings). In production, use chrome.identity.launchWebAuthFlow.
    html = f"""<!doctype html><meta charset=utf-8>
<title>Jalebi — signed in</title>
<body style="font-family:system-ui;padding:40px;max-width:640px;margin:auto">
<h2>✅ Signed in to Jalebi as {user.email}</h2>
<p>Copy this token into the Jalebi extension settings:</p>
<textarea style="width:100%;height:120px">{token}</textarea>
<script>window.opener && window.opener.postMessage(
  {{type:'jalebi-auth', token:{token!r}}}, '*');</script>
</body>"""
    return HTMLResponse(html)


@router.get("/me")
async def me(user: User = Depends(current_user)) -> dict:
    return _user_out(user)
