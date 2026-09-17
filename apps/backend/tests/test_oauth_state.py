"""OAuth callback hardening: CSRF state, output escaping, postMessage targeting.

The callback previously issued a `state` and never checked it, emitted a Python
repr into a JavaScript string context, and broadcast the bearer token with
postMessage(..., '*').
"""
from __future__ import annotations

import pytest

import app.api.routes.auth as auth_routes


# --- state lifecycle (pure) --------------------------------------------------

def test_state_is_single_use():
    state = auth_routes._issue_state()
    assert auth_routes._consume_state(state) is True
    # A replayed code+state pair must not work a second time.
    assert auth_routes._consume_state(state) is False


def test_unknown_state_rejected():
    assert auth_routes._consume_state("never-issued") is False


def test_expired_state_rejected(monkeypatch):
    state = auth_routes._issue_state()
    # Fast-forward past the TTL.
    real_time = auth_routes.time.time
    monkeypatch.setattr(
        auth_routes.time, "time",
        lambda: real_time() + auth_routes._STATE_TTL_SECONDS + 1,
    )
    assert auth_routes._consume_state(state) is False


def test_states_are_unpredictable():
    states = {auth_routes._issue_state() for _ in range(50)}
    assert len(states) == 50
    assert all(len(s) >= 32 for s in states)


# --- postMessage target ------------------------------------------------------

def _with_settings(monkeypatch, **over):
    """settings is a frozen dataclass, so swap the object rather than its fields."""
    from types import SimpleNamespace

    base = dict(oauth_post_message_origin="", google_redirect_uri="")
    base.update(over)
    monkeypatch.setattr(auth_routes, "settings", SimpleNamespace(**base))


def test_post_message_origin_is_never_wildcard(monkeypatch):
    """A wildcard here hands the token to any page that opened the popup."""
    _with_settings(
        monkeypatch,
        google_redirect_uri="https://jalebi.ties.org/api/auth/google/callback",
    )
    assert auth_routes._post_message_origin() == "https://jalebi.ties.org"


def test_explicit_origin_setting_wins(monkeypatch):
    _with_settings(
        monkeypatch,
        oauth_post_message_origin="https://app.ties.org",
        google_redirect_uri="https://jalebi.ties.org/api/auth/google/callback",
    )
    assert auth_routes._post_message_origin() == "https://app.ties.org"


def test_post_message_origin_falls_back_closed(monkeypatch):
    """A malformed redirect URI must degrade to an unmatchable origin, not '*'."""
    _with_settings(monkeypatch, google_redirect_uri="not-a-url")
    assert auth_routes._post_message_origin() == "null"


# --- JS string escaping ------------------------------------------------------

def test_js_string_neutralises_script_close():
    """json.dumps alone leaves '</script>' intact, which ends the block early."""
    hostile = "abc</script><script>alert(1)</script>"
    out = auth_routes._js_string(hostile)
    assert "</script>" not in out
    assert "<\\/script>" in out


def test_js_string_escapes_quotes_and_js_line_terminators():
    out = auth_routes._js_string("a'b\"c d e")
    assert " " not in out and " " not in out
    # Valid JSON in, valid JS literal out — round-trips to the original value.
    import json as _json

    assert _json.loads(out.replace("<\\/", "</")) == "a'b\"c d e"


# --- callback wiring ---------------------------------------------------------

def test_callback_requires_state_param():
    """`state` must be a required query parameter, not optional."""
    import inspect

    from pydantic_core import PydanticUndefined

    sig = inspect.signature(auth_routes.google_callback)
    assert "state" in sig.parameters
    # Query(...) normalises the Ellipsis default to PydanticUndefined = required.
    assert sig.parameters["state"].default.default is PydanticUndefined


def test_callback_rejects_bad_state(monkeypatch):
    """Forged state → 400, and the authorization code is never exchanged."""
    from fastapi import HTTPException

    monkeypatch.setattr(auth_routes.oauth, "is_configured", lambda: True)

    async def _boom(code):  # pragma: no cover - must never run
        raise AssertionError("exchange_code called despite invalid state")

    monkeypatch.setattr(auth_routes.oauth, "exchange_code", _boom)

    import asyncio

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            auth_routes.google_callback(code="stolen", state="forged", session=None)
        )
    assert exc.value.status_code == 400
