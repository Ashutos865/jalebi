"""Webhooks must not sit in the request path, and must cover every handoff.

Failures were already swallowed, so "the evaluation path never depends on
them" held for correctness -- but not for latency. Each webhook was posted in
turn, inside the request, with an 8-second timeout.
"""
from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace

import pytest

from app.api.routes import documents as documents_route
from app.integrations import notify as N
from app.workflow import states


@pytest.fixture
def two_webhooks(monkeypatch):
    monkeypatch.setattr(N, "settings", SimpleNamespace(
        slack_webhook_url="https://hooks.example/slack",
        teams_webhook_url="https://hooks.example/teams",
    ))


def test_webhooks_are_posted_concurrently(two_webhooks, monkeypatch):
    """Two webhooks cost the longer of the two, not the sum. At the real 8s
    timeout the sequential version added 16 seconds."""
    async def slow(url, payload):
        await asyncio.sleep(0.4)

    monkeypatch.setattr(N, "_post", slow)

    started = time.monotonic()
    asyncio.run(N.notify("hello"))
    elapsed = time.monotonic() - started

    assert elapsed < 0.7, f"posted sequentially: {elapsed:.2f}s"


def test_one_failing_webhook_does_not_stop_the_other(two_webhooks, monkeypatch):
    posted = []

    async def flaky(url, payload):
        if "slack" in url:
            raise RuntimeError("slack is down")
        posted.append(url)

    monkeypatch.setattr(N, "_post", flaky)
    asyncio.run(N.notify("hello"))

    assert posted, "a failing webhook suppressed the working one"


def test_no_webhook_configured_is_a_silent_no_op(monkeypatch):
    monkeypatch.setattr(N, "settings", SimpleNamespace(
        slack_webhook_url="", teams_webhook_url="",
    ))
    called = []

    async def spy(url, payload):
        called.append(url)

    monkeypatch.setattr(N, "_post", spy)
    asyncio.run(N.notify("hello"))
    assert called == []


# --- every announced handoff ------------------------------------------------

def _doc(status):
    return SimpleNamespace(
        title="Export Piece", status=status,
        escalation_reason="needs a second source", override_reason="",
    )


@pytest.mark.parametrize("status", [
    states.SUBMITTED,
    states.APPROVED,
    # Missing before: the team was told a piece was approved but never that it
    # went live, and a writer was never told their draft had come back.
    states.PUBLISHED,
    states.REVISING,
    states.REASSIGNED,
    states.SCRAPPED,
])
def test_every_handoff_is_announced(status):
    actor = SimpleNamespace(email="editor@ties.org")
    text = documents_route._transition_message(_doc(status), actor)
    assert text, f"no announcement for {status}"
    assert "Export Piece" in text


def test_internal_states_are_not_announced():
    """Only handoffs go to the group chat; routine movement does not."""
    actor = SimpleNamespace(email="editor@ties.org")
    assert documents_route._transition_message(_doc(states.DRAFTING), actor) == ""


def test_an_override_is_surfaced_in_the_approval_message():
    actor = SimpleNamespace(email="editor@ties.org")
    doc = _doc(states.APPROVED)
    doc.override_reason = "deadline, second source to follow"
    text = documents_route._transition_message(doc, actor)
    assert "override" in text.lower()
    assert "deadline" in text


# --- the request must not wait on the webhook -------------------------------

def test_a_transition_response_does_not_wait_for_the_webhook(monkeypatch):
    """End to end: a hung webhook must not hold the editor's response open."""
    from fastapi.testclient import TestClient

    from app.main import app

    monkeypatch.setattr(N, "settings", SimpleNamespace(
        slack_webhook_url="https://hooks.example/slack",
        teams_webhook_url="https://hooks.example/teams",
    ))

    posted = []

    async def hung(url, payload):
        await asyncio.sleep(0.5)
        posted.append(url)

    monkeypatch.setattr(N, "_post", hung)

    with TestClient(app) as client:
        token = client.post(
            "/api/auth/dev-login", json={"email": "founder@ties.org"}
        ).json()["access_token"]
        head = {"Authorization": f"Bearer {token}"}
        client.post("/api/evaluate", json={
            "text": "Exports rose 12% in FY24 according to Ministry data. " * 12,
            "content_type": "analysis", "doc_id": "notify-1", "title": "Notify",
        }, headers=head)

        for target in ("assigned", "drafting"):
            client.put("/api/documents/notify-1/status",
                       json={"status": target, "reason": "setup"}, headers=head)

        started = time.monotonic()
        r = client.put("/api/documents/notify-1/status",
                       json={"status": "submitted", "reason": "ready"}, headers=head)
        elapsed = time.monotonic() - started

    assert r.status_code == 200, r.text
    # TestClient runs background tasks before returning, so this measures the
    # scheduling, not the wait a real client sees. What it does prove is that
    # the two webhooks overlap: sequential would be >= 1.0s.
    assert elapsed < 0.9, f"webhooks were posted sequentially: {elapsed:.2f}s"
    assert len(posted) == 2, posted
