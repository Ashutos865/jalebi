"""Production hardening tests: login gating, rate limiting, security headers."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

import app.auth.service as svc
import app.config as cfg
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


# --- production config gate -------------------------------------------------

def _cfg(**over):
    base = dict(
        environment="production",
        jwt_secret="x" * 40,
        allow_dev_login=False,
        signup_secret="",
        allowed_emails=[],
        allowed_domains=[],
        cors_origins=["https://jalebi.ties.org"],
    )
    base.update(over)
    return SimpleNamespace(**base)


def test_safe_production_config_passes():
    assert cfg.unsafe_production_settings(_cfg()) == []
    cfg.enforce_production_safety(_cfg())  # must not raise


def test_default_jwt_secret_blocks_startup():
    problems = cfg.unsafe_production_settings(_cfg(jwt_secret=cfg.INSECURE_JWT_SECRET))
    assert any("JALEBI_JWT_SECRET" in p for p in problems)
    with pytest.raises(RuntimeError, match="unsafe production configuration"):
        cfg.enforce_production_safety(_cfg(jwt_secret=cfg.INSECURE_JWT_SECRET))


def test_short_jwt_secret_blocks_startup():
    assert cfg.unsafe_production_settings(_cfg(jwt_secret="tooshort"))


def test_open_dev_login_blocks_startup():
    """Passwordless login with no allow-list = anyone can mint an account."""
    problems = cfg.unsafe_production_settings(_cfg(allow_dev_login=True))
    assert len(problems) == 2  # missing signup secret AND missing allow-list
    # Fully configured dev-login is allowed through.
    assert cfg.unsafe_production_settings(
        _cfg(allow_dev_login=True, signup_secret="s3cret", allowed_domains=["ties.org"])
    ) == []


def test_wildcard_cors_blocks_startup():
    assert any(
        "CORS" in p for p in cfg.unsafe_production_settings(_cfg(cors_origins=["*"]))
    )


def test_gate_is_inert_outside_production():
    """Dev must keep running on an empty .env — that is the project's promise."""
    unsafe = _cfg(
        environment="development",
        jwt_secret=cfg.INSECURE_JWT_SECRET,
        allow_dev_login=True,
        cors_origins=["*"],
    )
    cfg.enforce_production_safety(unsafe)  # must not raise


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


def test_rate_limit_survives_cleanup_past_10k_keys():
    """The internal store is pruned once it passes 10,000 keys. A previous version
    rebuilt it as a plain dict from a defaultdict, so the next unseen key raised
    KeyError -> HTTP 500 for every new client, permanently."""
    async def ep(_req):
        return PlainTextResponse("ok")

    mini = Starlette(routes=[Route("/api/x", ep)])
    mini.add_middleware(RateLimitMiddleware, limit_per_min=1_000_000)
    client = TestClient(mini)

    # Distinct forwarded IPs mint distinct window keys and trip the cleanup.
    for i in range(10_050):
        client.get("/api/x", headers={"X-Forwarded-For": f"10.0.{i // 256}.{i % 256}"})

    # The key that used to blow up: one never seen before, after a prune.
    r = client.get("/api/x", headers={"X-Forwarded-For": "203.0.113.7"})
    assert r.status_code == 200


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
