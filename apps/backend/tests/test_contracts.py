"""Response contracts and multi-worker configuration.

Two loose ends from the audit:

  * /api/classify and /api/providers returned bare dicts, so the shapes the
    sidebar's TypeScript asserted were enforced nowhere. A rename on this side
    would have broken the panel silently and been invisible in the OpenAPI
    schema.
  * The in-memory vector store is a process global, so with several workers the
    same document retrieves different passages depending on which one answers.
    That was documented but not enforced.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import app.config as cfg


@pytest.fixture(scope="module")
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


# --- response contracts ------------------------------------------------------

def test_classify_returns_the_documented_shape(client):
    r = client.post(
        "/api/classify",
        json={"text": "Exports rose 12.7% in FY24 according to Ministry data. " * 4},
    )
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"content_type", "confidence", "label", "scores"}
    assert isinstance(body["label"], str) and body["label"]
    assert 0.0 <= body["confidence"] <= 1.0
    assert isinstance(body["scores"], dict)


def test_classify_is_documented_in_the_schema(client):
    spec = client.get("/openapi.json").json()
    ref = (
        spec["paths"]["/api/classify"]["post"]["responses"]["200"]
        ["content"]["application/json"]["schema"]
    )
    # A bare `-> dict` produces an empty schema; a response_model produces a ref.
    assert ref, "classify has no documented response schema"
    assert "ClassifyResponse" in str(ref)


def test_providers_returns_the_documented_shape(client):
    body = client.get("/api/providers").json()
    assert set(body) == {"active", "providers"}
    assert isinstance(body["active"], str)
    for p in body["providers"]:
        assert set(p) == {"id", "label", "open_source", "model", "available", "note"}


def test_providers_is_documented_in_the_schema(client):
    spec = client.get("/openapi.json").json()
    ref = (
        spec["paths"]["/api/providers"]["get"]["responses"]["200"]
        ["content"]["application/json"]["schema"]
    )
    assert "ProvidersResponse" in str(ref)


def test_providers_never_leaks_a_key(client):
    """Keys live only on the backend; this endpoint is unauthenticated."""
    raw = client.get("/api/providers").text.lower()
    for token in ("sk-", "api_key", "apikey", "secret"):
        assert token not in raw


# --- multi-worker configuration ---------------------------------------------

def _cfg(**over):
    base = dict(
        environment="production",
        jwt_secret="x" * 40,
        allow_dev_login=False,
        signup_secret="",
        allowed_emails=[],
        allowed_domains=[],
        cors_origins=["https://jalebi.ties.org"],
        rag_enabled=True,
        qdrant_url="",
        web_concurrency=1,
    )
    base.update(over)
    return SimpleNamespace(**base)


def test_single_worker_needs_no_shared_store():
    assert cfg.unsafe_production_settings(_cfg()) == []


def test_multiple_workers_without_qdrant_is_rejected():
    """Each worker holds its own index, so retrieval silently varies by which
    one answers — and the startup reindex runs once per worker."""
    problems = cfg.unsafe_production_settings(_cfg(web_concurrency=4))
    assert any("QDRANT_URL" in p for p in problems), problems


def test_multiple_workers_with_qdrant_is_fine():
    assert cfg.unsafe_production_settings(
        _cfg(web_concurrency=4, qdrant_url="http://qdrant:6333")
    ) == []


def test_multiple_workers_with_rag_disabled_is_fine():
    assert cfg.unsafe_production_settings(
        _cfg(web_concurrency=4, rag_enabled=False)
    ) == []


def test_the_problem_is_warned_about_outside_production():
    """The production gate is inert in development, but this misconfiguration
    produces wrong results rather than insecure ones, so it is still worth
    saying out loud."""
    warnings = cfg.misconfiguration_warnings(
        _cfg(environment="development", web_concurrency=4)
    )
    assert any("QDRANT_URL" in w for w in warnings)


def test_development_warnings_do_not_block_startup():
    # Must not raise, even with the misconfiguration present.
    cfg.enforce_production_safety(_cfg(environment="development", web_concurrency=4))
