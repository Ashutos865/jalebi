"""The production loop end to end (SOP §3, §4): assign → draft → review → sign-off."""
from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.util import utcnow
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


@pytest.fixture(scope="module")
def writer(client):
    return client.post(
        "/api/auth/dev-login", json={"email": "wf-writer@ties.org"}
    ).json()["access_token"]


def _h(token):
    return {"Authorization": f"Bearer {token}"}


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


def _move(client, token, doc_id, status, **extra):
    return client.put(
        f"/api/documents/{doc_id}/status",
        json={"status": status, **extra},
        headers=_h(token),
    )


# --- assignment --------------------------------------------------------------

def test_assignment_starts_the_drafting_clock(client, editor):
    _track(client, editor, "wf-1")
    r = client.put(
        "/api/documents/wf-1/assign",
        json={"assigned_to": "writer@ties.org", "editor": "ed@ties.org",
              "word_min": 300, "word_max": 350},
        headers=_h(editor),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == S.ASSIGNED
    assert body["assigned_to"] == "writer@ties.org"
    assert body["sla"]["phase"] == "drafting"
    assert body["sla"]["due_at"] and not body["sla"]["overdue"]
    # SOP: 18h outer bound on drafting.
    assert 17 < body["sla"]["hours_remaining"] <= 18


def test_word_window_is_validated(client, editor):
    _track(client, editor, "wf-bad-window")
    r = client.put(
        "/api/documents/wf-bad-window/assign",
        json={"assigned_to": "w@ties.org", "word_min": 500, "word_max": 100},
        headers=_h(editor),
    )
    assert r.status_code == 422


def test_writer_cannot_assign(client, writer):
    r = client.put(
        "/api/documents/wf-1/assign",
        json={"assigned_to": "x@ties.org"}, headers=_h(writer),
    )
    assert r.status_code == 403


# --- the loop ----------------------------------------------------------------

def test_full_loop(client, editor):
    _track(client, editor, "wf-2")
    client.put("/api/documents/wf-2/assign",
               json={"assigned_to": "w@ties.org"}, headers=_h(editor))

    for status in (S.DRAFTING, S.SUBMITTED, S.UNDER_REVIEW, S.REVISING,
                   S.SUBMITTED, S.APPROVED, S.PUBLISHED):
        r = _move(client, editor, "wf-2", status)
        assert r.status_code == 200, (status, r.text)
    assert _move(client, editor, "wf-2", S.DRAFTING).status_code == 422  # terminal


def test_submitting_starts_the_editing_clock(client, editor):
    _track(client, editor, "wf-3")
    client.put("/api/documents/wf-3/assign",
               json={"assigned_to": "w@ties.org"}, headers=_h(editor))
    body = _move(client, editor, "wf-3", S.SUBMITTED).json()
    assert body["sla"]["phase"] == "editing"
    # SOP: 12h outer bound on editing.
    assert 11 < body["sla"]["hours_remaining"] <= 12
    assert body["submitted_at"]


def test_author_can_submit_and_editor_can_pull(client, editor, writer):
    """Both entry points into review are supported."""
    _track(client, editor, "wf-4a")
    client.put("/api/documents/wf-4a/assign",
               json={"assigned_to": "w@ties.org"}, headers=_h(editor))
    assert _move(client, writer, "wf-4a", S.SUBMITTED).status_code == 200

    _track(client, editor, "wf-4b")
    client.put("/api/documents/wf-4b/assign",
               json={"assigned_to": "w@ties.org"}, headers=_h(editor))
    _move(client, editor, "wf-4b", S.DRAFTING)
    assert _move(client, editor, "wf-4b", S.UNDER_REVIEW).status_code == 200


def test_illegal_transition_is_rejected_with_guidance(client, editor):
    _track(client, editor, "wf-5")
    client.put("/api/documents/wf-5/assign",
               json={"assigned_to": "w@ties.org"}, headers=_h(editor))
    r = _move(client, editor, "wf-5", S.PUBLISHED)
    assert r.status_code == 422
    assert "Cannot move" in r.json()["detail"]
    assert "drafting" in r.json()["detail"]


def test_writer_cannot_approve_their_own_work(client, editor, writer):
    _track(client, editor, "wf-6")
    client.put("/api/documents/wf-6/assign",
               json={"assigned_to": "w@ties.org"}, headers=_h(editor))
    _move(client, writer, "wf-6", S.SUBMITTED)
    r = _move(client, writer, "wf-6", S.APPROVED)
    assert r.status_code == 403
    assert "editor" in r.json()["detail"].lower()


# --- sign-off ----------------------------------------------------------------

def test_approval_records_who_and_when(client, editor):
    _track(client, editor, "wf-7")
    client.put("/api/documents/wf-7/assign",
               json={"assigned_to": "w@ties.org"}, headers=_h(editor))
    _move(client, editor, "wf-7", S.SUBMITTED)
    body = _move(client, editor, "wf-7", S.APPROVED).json()
    assert body["approved_by"] == "founder@ties.org"
    assert body["approved_at"]
    assert body["sla"]["phase"] is None      # the clock stops


def test_approval_is_never_blocked_but_records_an_override(client, editor):
    """SOP §4 gives the editor final say, so Jalebi records the exception
    rather than refusing the approval."""
    _track(client, editor, "wf-8")
    client.put("/api/documents/wf-8/assign",
               json={"assigned_to": "w@ties.org"}, headers=_h(editor))
    _move(client, editor, "wf-8", S.SUBMITTED)

    pre = client.get("/api/documents/wf-8/workflow", headers=_h(editor)).json()
    assert pre["blocking_reasons"], "unchecked AI/plagiarism should be surfaced"

    body = _move(client, editor, "wf-8", S.APPROVED,
                 override_reason="Time-critical; checks run manually.").json()
    assert body["override_reason"].startswith("Time-critical")


def test_approved_work_can_be_reopened(client, editor):
    _track(client, editor, "wf-9")
    client.put("/api/documents/wf-9/assign",
               json={"assigned_to": "w@ties.org"}, headers=_h(editor))
    _move(client, editor, "wf-9", S.SUBMITTED)
    _move(client, editor, "wf-9", S.APPROVED)
    assert _move(client, editor, "wf-9", S.REVISING).status_code == 200


# --- escalation (SOP §4 veto authority) --------------------------------------

def test_scrapping_requires_a_reason(client, editor):
    _track(client, editor, "wf-10")
    client.put("/api/documents/wf-10/assign",
               json={"assigned_to": "w@ties.org"}, headers=_h(editor))
    r = _move(client, editor, "wf-10", S.SCRAPPED)
    assert r.status_code == 422 and "reason" in r.json()["detail"].lower()

    r = _move(client, editor, "wf-10", S.SCRAPPED,
              reason="Fails factual standards after two revisions.")
    assert r.status_code == 200
    assert r.json()["escalation_reason"].startswith("Fails factual")


def test_reassignment_can_restart_the_loop(client, editor):
    _track(client, editor, "wf-11")
    client.put("/api/documents/wf-11/assign",
               json={"assigned_to": "w@ties.org"}, headers=_h(editor))
    _move(client, editor, "wf-11", S.REASSIGNED, reason="Author unavailable.")
    r = client.put("/api/documents/wf-11/assign",
                   json={"assigned_to": "other@ties.org"}, headers=_h(editor))
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == S.ASSIGNED and body["assigned_to"] == "other@ties.org"
    assert body["escalation_reason"] == ""     # fresh loop


def test_writer_cannot_scrap(client, writer, editor):
    _track(client, editor, "wf-12")
    client.put("/api/documents/wf-12/assign",
               json={"assigned_to": "w@ties.org"}, headers=_h(editor))
    r = _move(client, writer, "wf-12", S.SCRAPPED, reason="nope")
    assert r.status_code == 403


# --- overdue detection -------------------------------------------------------

def test_overdue_is_detected(client, editor):
    from app.db.base import SessionLocal
    from app.db.models import Document
    from sqlalchemy import select
    import asyncio

    _track(client, editor, "wf-13")
    client.put("/api/documents/wf-13/assign",
               json={"assigned_to": "w@ties.org"}, headers=_h(editor))

    async def backdate():
        async with SessionLocal() as s:
            doc = (await s.execute(
                select(Document).where(Document.google_doc_id == "wf-13")
            )).scalar_one()
            doc.phase_started_at = utcnow() - timedelta(hours=20)
            await s.commit()

    asyncio.run(backdate())
    sla = client.get("/api/documents/wf-13/workflow", headers=_h(editor)).json()["sla"]
    assert sla["overdue"] is True
    assert sla["hours_remaining"] < 0


def test_workflow_view_lists_next_states(client, editor):
    _track(client, editor, "wf-14")
    client.put("/api/documents/wf-14/assign",
               json={"assigned_to": "w@ties.org"}, headers=_h(editor))
    body = client.get("/api/documents/wf-14/workflow", headers=_h(editor)).json()
    assert S.DRAFTING in body["next_states"]
    assert S.PUBLISHED not in body["next_states"]


def test_untracked_document_is_404(client, editor):
    assert client.get(
        "/api/documents/nope/workflow", headers=_h(editor)
    ).status_code == 404
