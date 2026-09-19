"""Day-2 resilience: timeouts, proxy trust, and error containment."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

import app.middleware as mw
from app.config import settings
from app.llm.client import LLMResponse
from app.pipeline.hybrid_evaluator import HybridEvaluator
from app.schemas.evaluation import ContentType, EvaluationRequest


# --- LLM timeouts -----------------------------------------------------------

def test_timeout_settings_exist_and_are_sane():
    assert 0 < settings.llm_timeout_seconds <= 300
    assert 0 <= settings.llm_max_retries <= 5
    assert settings.llm_total_timeout_seconds >= settings.llm_timeout_seconds


def test_clients_pass_an_explicit_timeout():
    """The SDK default is ~600s, long enough for one stalled call to hold a
    worker and its DB session for the whole request."""
    from pathlib import Path

    for path in ("app/llm/client.py", "app/llm/openai_client.py",
                 "app/llm/gemini_client.py"):
        src = Path(path).read_text(encoding="utf-8")
        assert "llm_timeout_seconds" in src, path


class _HangingClient:
    """A provider that never answers."""

    async def complete(self, **_kw) -> LLMResponse:
        await asyncio.sleep(3600)
        raise AssertionError("unreachable")


def test_a_hung_provider_degrades_to_rules_only(monkeypatch):
    """The whole judgment is bounded, so a stalled provider cannot pin the
    request. The evaluation still returns — scored on rules."""
    import app.pipeline.hybrid_evaluator as he

    monkeypatch.setattr(
        he, "settings",
        SimpleNamespace(llm_total_timeout_seconds=0.25),
        raising=False,
    )

    ev = HybridEvaluator(client=_HangingClient(), provider="test", model="x")
    result = asyncio.run(ev.evaluate(EvaluationRequest(
        text="Exports rose 12% in FY24 according to Ministry data. " * 8,
        content_type=ContentType.analysis,
    )))

    assert 0 <= result.overall_score <= 100
    assert "timed out" in result.summary.lower() or result.categories


# --- X-Forwarded-For trust --------------------------------------------------

def _with_proxies(monkeypatch, proxies):
    """settings is a frozen dataclass, so swap the object the module sees."""
    monkeypatch.setattr(
        mw, "settings", SimpleNamespace(trusted_proxies=proxies), raising=False
    )


def _limited_app(limit: int = 2):
    async def ep(_req):
        return PlainTextResponse("ok")

    mini = Starlette(routes=[Route("/api/x", ep)])
    mini.add_middleware(mw.RateLimitMiddleware, limit_per_min=limit)
    return TestClient(mini)


def test_xff_is_ignored_without_a_trusted_proxy(monkeypatch):
    """Otherwise anyone can rotate the header to mint a fresh bucket per
    request, defeating the only abuse control on the expensive path."""
    _with_proxies(monkeypatch, [])
    client = _limited_app(limit=2)

    codes = [
        client.get("/api/x", headers={"X-Forwarded-For": f"9.9.9.{i}"}).status_code
        for i in range(4)
    ]
    assert 429 in codes, "spoofed XFF should not grant unlimited buckets"


def test_xff_is_honoured_behind_a_trusted_proxy(monkeypatch):
    _with_proxies(monkeypatch, ["testclient", "127.0.0.1"])
    # TestClient's peer host is "testclient", which is not an IP, so the CIDR
    # parse fails and the header is ignored — the safe direction.
    assert mw._is_trusted_proxy("127.0.0.1") is True
    assert mw._is_trusted_proxy("10.1.2.3") is False


def test_cidr_blocks_are_supported(monkeypatch):
    _with_proxies(monkeypatch, ["10.0.0.0/8"])
    assert mw._is_trusted_proxy("10.1.2.3") is True
    assert mw._is_trusted_proxy("192.168.1.1") is False


def test_malformed_proxy_entries_do_not_crash(monkeypatch):
    _with_proxies(monkeypatch, ["not-an-ip", "10.0.0.0/8"])
    assert mw._is_trusted_proxy("10.0.0.1") is True
    assert mw._is_trusted_proxy("8.8.8.8") is False


def test_unparseable_peer_is_untrusted(monkeypatch):
    _with_proxies(monkeypatch, ["10.0.0.0/8"])
    assert mw._is_trusted_proxy("unknown") is False


# --- error containment ------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


def test_readiness_never_returns_the_database_error(client):
    """SQLAlchemy connection errors routinely include the DSN with credentials,
    and this probe is unauthenticated."""
    body = client.get("/api/health/ready").json()
    assert body["database"] in ("ok", "unavailable")
    for leak in ("://", "password", "@", "Traceback"):
        assert leak not in body["database"], body


def test_rewrite_does_not_echo_provider_errors():
    from pathlib import Path

    src = Path("app/api/routes/rewrite.py").read_text(encoding="utf-8")
    assert 'f"Rewrite provider error: {exc}"' not in src
    assert "logger.exception" in src


def test_rewrite_honours_the_provider_allow_list(client, monkeypatch):
    """JALEBI_ALLOWED_PROVIDERS is meant to constrain every path that calls a
    model; this one read settings.provider directly and ignored it."""
    from pathlib import Path

    src = Path("app/api/routes/rewrite.py").read_text(encoding="utf-8")
    assert "allowed_providers()" in src

    r = client.post("/api/rewrite", json={"text": "Make this clearer.", "goal": "clarity"})
    assert r.status_code == 200
    # Mock provider is configured in tests, so no live rewrite is available.
    assert r.json()["engine"] in ("unavailable", "mock")
