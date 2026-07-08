"""Google OAuth 2.0 (authorization-code flow), no extra dependency — httpx only."""
from __future__ import annotations

from urllib.parse import urlencode

import httpx

from app.config import settings

_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN = "https://oauth2.googleapis.com/token"
_USERINFO = "https://openidconnect.googleapis.com/v1/userinfo"


def is_configured() -> bool:
    return bool(settings.google_client_id and settings.google_client_secret)


def authorize_url(state: str) -> str:
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "online",
        "state": state,
        "prompt": "select_account",
    }
    return f"{_AUTH}?{urlencode(params)}"


async def exchange_code(code: str) -> dict:
    """Exchange an auth code for the Google userinfo (email, name, sub)."""
    async with httpx.AsyncClient(timeout=15) as client:
        token_resp = await client.post(
            _TOKEN,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        token_resp.raise_for_status()
        access_token = token_resp.json()["access_token"]
        info = await client.get(
            _USERINFO, headers={"Authorization": f"Bearer {access_token}"}
        )
        info.raise_for_status()
        return info.json()
