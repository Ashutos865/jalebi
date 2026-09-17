"""Authentication routes: dev login, Google OAuth, and current user."""
from __future__ import annotations

import html
import json
import secrets
import time

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

# --- OAuth CSRF state ----------------------------------------------------------
# Single-use, short-lived `state` values issued by /google/login and consumed by
# /google/callback. Without this check an attacker can feed a victim their own
# authorization code and silently log the victim into the attacker's account.
# In-memory, so it is per-worker: with multiple workers, back this with Redis or a
# signed cookie so a login started on one worker can finish on another.
_STATE_TTL_SECONDS = 600
_pending_states: dict[str, float] = {}


def _issue_state() -> str:
    now = time.time()
    # Opportunistic sweep of expired states; the map stays small in normal use.
    for s, exp in list(_pending_states.items()):
        if exp < now:
            _pending_states.pop(s, None)
    state = secrets.token_urlsafe(32)
    _pending_states[state] = now + _STATE_TTL_SECONDS
    return state


def _consume_state(state: str) -> bool:
    """Validate and burn a state value. False if unknown, replayed, or expired."""
    expiry = _pending_states.pop(state, None)
    return expiry is not None and expiry >= time.time()


def _js_string(value: str) -> str:
    """Serialise `value` as a JS string literal that is safe inside <script>.

    json.dumps handles quotes/backslashes but leaves "</script>" intact, which
    terminates the block early. Escaping the slash (and the JS-only U+2028/9 line
    terminators) closes that. A Python !r repr is not valid JS escaping at all.
    """
    return (
        json.dumps(value)
        .replace("</", "<\\/")
        .replace(" ", "\\u2028")
        .replace(" ", "\\u2029")
    )


def _post_message_origin() -> str:
    """Exact origin the success page may postMessage the token to.

    Configured value wins; otherwise derive the origin of the redirect URI, which
    is this backend. Falls back to "null" (an origin nothing matches) rather than
    "*" so a misconfiguration cannot leak the token.
    """
    if settings.oauth_post_message_origin:
        return settings.oauth_post_message_origin
    from urllib.parse import urlsplit

    parts = urlsplit(settings.google_redirect_uri)
    return f"{parts.scheme}://{parts.netloc}" if parts.scheme and parts.netloc else "null"


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
    state = _issue_state()
    return {"authorize_url": oauth.authorize_url(state), "state": state}


@router.get("/google/callback")
async def google_callback(
    code: str = Query(...),
    state: str = Query(...),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    if not oauth.is_configured():
        raise HTTPException(status_code=503, detail="Google OAuth is not configured.")
    # CSRF: the state must be one we issued, unused, and unexpired.
    if not _consume_state(state):
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired OAuth state. Start the sign-in again.",
        )
    info = await oauth.exchange_code(code)
    user = await get_or_create_user(
        session, email=info["email"], name=info.get("name", ""),
        google_sub=info.get("sub"),
    )
    token = _issue(user)["access_token"]
    # Minimal success page — the extension reads the token from here (or the user
    # pastes it into settings). In production, use chrome.identity.launchWebAuthFlow.
    #
    # Escaping matters twice over here: html.escape() for the HTML context, and
    # json.dumps() for the JS string context. (A Python !r repr is *not* valid JS
    # escaping — different grammars.) The target origin is explicit, never "*",
    # which would hand the bearer token to any site that opened this popup.
    safe_email = html.escape(user.email)
    safe_token_html = html.escape(token)
    page = f"""<!doctype html><meta charset=utf-8>
<title>Jalebi — signed in</title>
<body style="font-family:system-ui;padding:40px;max-width:640px;margin:auto">
<h2>✅ Signed in to Jalebi as {safe_email}</h2>
<p>Copy this token into the Jalebi extension settings:</p>
<textarea style="width:100%;height:120px">{safe_token_html}</textarea>
<script>window.opener && window.opener.postMessage(
  {{type:'jalebi-auth', token:{_js_string(token)}}}, {_js_string(_post_message_origin())});</script>
</body>"""
    return HTMLResponse(page)


@router.get("/me")
async def me(user: User = Depends(current_user)) -> dict:
    return _user_out(user)
