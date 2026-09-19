"""Workflow invariants that must hold however a document is moved.

A bug hunt found that the state machine could be bypassed entirely and that the
SLA clocks reset on transitions *within* a phase. Both are pinned here: the
first because it lets a document reach `published` with no sign-off recorded,
the second because it means the SOP's 24-30 hour loop is not actually tracked.
"""
from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.util import utcnow
from app.workflow import service as wf
from app.workflow import states as S


@pytest.fixture(scope="module")
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def editor(client):
    return client.post(
        "/api/auth/dev-login", json={"email": "founder@ties.org"}
    ).json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _track(client, token, doc_id):
    client.post(
        "/api/evaluate",
        json={
            "text": "Exports rose 12% in FY24 according to Ministry data. " * 12,
            "content_type": "analysis",
            "doc_id": doc_id,
        },
        headers=_h(token),
    )


# --- the state machine cannot be bypassed -----------------------------------

def test_patch_cannot_skip_the_state_machine(client, editor):
    """PATCH wrote doc.status directly against a free-text allow-list, so a
    document could jump straight to `published` — no editor recorded, no
    integrity check, no notification, and no legal way back out."""
    _track(client, editor, "wf-integrity-1")

    rejected = client.put(
        "/api/documents/wf-integrity-1/status",
        json={"status": "published"}, headers=_h(editor),
    )
    assert rejected.status_code == 422, "PUT should reject an illegal jump"

    patched = client.patch(
        "/api/documents/wf-integrity-1",
        json={"status": "published"}, headers=_h(editor),
    )
    assert patched.status_code == 422, (
        "PATCH must not accept a transition PUT rejects"
    )

    state = client.get(
        "/api/documents/wf-integrity-1/workflow", headers=_h(editor)
    ).json()
    assert state["status"] != "published"


def test_patch_still_edits_non_workflow_fields(client, editor):
    """Closing the bypass must not break the tracker's ordinary editing."""
    _track(client, editor, "wf-integrity-2")
    r = client.patch(
        "/api/documents/wf-integrity-2",
        json={"editor": "ed@ties.org", "published_for": "Substack"},
        headers=_h(editor),
    )
    assert r.status_code == 200
    assert r.json()["editor"] == "ed@ties.org"


def test_a_legal_status_change_through_patch_is_still_honoured(client, editor):
    """`draft -> submitted` is legal, so PATCH may perform it — via the state
    machine, which means the clocks and stamps are set properly."""
    _track(client, editor, "wf-integrity-3")
    r = client.patch(
        "/api/documents/wf-integrity-3",
        json={"status": "submitted"}, headers=_h(editor),
    )
    assert r.status_code == 200
    state = client.get(
        "/api/documents/wf-integrity-3/workflow", headers=_h(editor)
    ).json()
    assert state["status"] == "submitted"
    assert state["submitted_at"], "the submission clock must have been stamped"


# --- phase clocks --------------------------------------------------------

def _doc(status: str, started_hours_ago: float):
    return SimpleNamespace(
        status=status,
        phase_started_at=utcnow() - timedelta(hours=started_hours_ago),
        submitted_at=None, approved_at=None, approved_by="",
        override_reason="", escalation_reason="", updated_at=utcnow(),
        ai_percent=None, plagiarism_percent=None,
    )


def test_moving_within_a_phase_does_not_restart_its_clock():
    """`submitted` and `under_review` are both editing states. Resetting on
    every transition meant an editor simply opening a document granted it a
    fresh 12 hours, so nothing ever became overdue."""
    doc = _doc(S.SUBMITTED, started_hours_ago=11)
    before = wf.sla_for(doc)

    actor = SimpleNamespace(role="editor", email="e@ties.org")
    wf.transition(doc, S.UNDER_REVIEW, actor=actor)
    after = wf.sla_for(doc)

    assert after.hours_remaining == pytest.approx(before.hours_remaining, abs=0.1), (
        "the editing clock restarted on an intra-phase move"
    )


def test_changing_phase_does_restart_the_clock():
    doc = _doc(S.DRAFTING, started_hours_ago=17)
    actor = SimpleNamespace(role="editor", email="e@ties.org")
    wf.transition(doc, S.SUBMITTED, actor=actor)

    sla = wf.sla_for(doc)
    assert sla.phase == "editing"
    assert sla.hours_remaining > 11, "a new phase should start with a full window"


def test_an_overdue_document_stays_overdue_across_an_intra_phase_move():
    doc = _doc(S.SUBMITTED, started_hours_ago=20)
    assert wf.sla_for(doc).overdue

    actor = SimpleNamespace(role="editor", email="e@ties.org")
    wf.transition(doc, S.UNDER_REVIEW, actor=actor)
    assert wf.sla_for(doc).overdue, "moving to review cleared an overdue flag"


def test_revision_ping_pong_cannot_reset_the_clock_forever():
    """revising -> submitted -> revising are all real transitions, but the pair
    spans two phases, so each leg legitimately gets its own window. What must
    not happen is a within-phase hop buying more time."""
    doc = _doc(S.REVISING, started_hours_ago=17)
    actor = SimpleNamespace(role="editor", email="e@ties.org")

    # Still in the drafting phase after assigned -> drafting.
    doc.status = S.ASSIGNED
    remaining_before = wf.sla_for(doc).hours_remaining
    wf.transition(doc, S.DRAFTING, actor=actor)
    assert wf.sla_for(doc).hours_remaining == pytest.approx(
        remaining_before, abs=0.1
    )
