"""Production hardening tests: login gating, rate limiting, security headers."""
from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

import app.auth.service as svc
from app.middleware import RateLimitMiddleware


# --- login gating (pure) ----------------------------------------------------

def _fake(monkeypatch, **over):
    base = dict(allow_dev_login=True, signup_secret="", allowed_emails=[],
                allowed_domains=[])
    base.update(over)
    monkeypatch.setattr(svc, "settings", SimpleNamespace(**base))


def test_login_open_when_unconfigured(monkeypatch):
    _fake(monkeypatch)
    ok, status, _ = svc.check_login_allowed("anyone@x.com", "")
    assert ok and status == 200


def test_login_requires_secret(monkeypatch):
    _fake(monkeypatch, signup_secret="s3cret")
    assert svc.check_login_allowed("a@ties.org", "wrong")[1] == 401
    assert svc.check_login_allowed("a@ties.org", "s3cret")[0] is True


def test_login_respects_allow_list(monkeypatch):
    _fake(monkeypatch, allowed_domains=["ties.org"])
    assert svc.check_login_allowed("intruder@evil.com", "")[1] == 403
    assert svc.check_login_allowed("editor@ties.org", "")[0] is True


def test_login_can_be_disabled(monkeypatch):
    _fake(monkeypatch, allow_dev_login=False)
    assert svc.check_login_allowed("a@ties.org", "")[1] == 403


# --- rate limiting ----------------------------------------------------------

def test_rate_limit_returns_429_over_limit():
    async def ep(_req):
        return PlainTextResponse("ok")

    mini = Starlette(routes=[Route("/api/x", ep)])
    mini.add_middleware(RateLimitMiddleware, limit_per_min=2)
    client = TestClient(mini)
    assert client.get("/api/x").status_code == 200
    assert client.get("/api/x").status_code == 200
    r = client.get("/api/x")
    assert r.status_code == 429 and r.headers.get("Retry-After") == "60"


def test_rate_limit_excludes_health():
    async def ep(_req):
        return PlainTextResponse("ok")

    mini = Starlette(routes=[Route("/api/health", ep)])
    mini.add_middleware(RateLimitMiddleware, limit_per_min=1)
    client = TestClient(mini)
    for _ in range(5):
        assert client.get("/api/health").status_code == 200


# --- security headers -------------------------------------------------------

def test_security_headers_present():
    from app.main import app

    with TestClient(app) as client:
        r = client.get("/api/health")
        assert r.headers.get("X-Content-Type-Options") == "nosniff"
        assert r.headers.get("X-Frame-Options") == "DENY"
        assert r.headers.get("X-Request-ID")
