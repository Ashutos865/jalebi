"""Concurrent writes to one document must not silently lose a decision.

Reproduced before being fixed: two editors acting on the same submitted
article -- one approving, one scrapping -- both got "ok", and the scrap
vanished.
"""
from __future__ import annotations

import threading

import pytest
from fastapi.testclient import TestClient


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


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _submitted_doc(client, editor, doc_id):
    """Track a document and walk it up to `submitted`."""
    client.post("/api/evaluate", json={
        "text": "Exports rose 12% in FY24 according to Ministry data. " * 12,
        "content_type": "analysis", "doc_id": doc_id, "title": "Concurrent",
    }, headers=_h(editor))
    for target in ("assigned", "drafting", "submitted"):
        r = client.put(f"/api/documents/{doc_id}/status",
                       json={"status": target, "reason": "setup"},
                       headers=_h(editor))
        assert r.status_code == 200, r.text
    return doc_id


def _race(client, editor, doc_id, targets):
    """Fire both transitions at the same instant; return their responses."""
    results = []
    barrier = threading.Barrier(len(targets))

    def act(target):
        barrier.wait()
        results.append(client.put(
            f"/api/documents/{doc_id}/status",
            json={"status": target, "reason": "concurrent"},
            headers=_h(editor),
        ))

    threads = [threading.Thread(target=act, args=(t,)) for t in targets]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results


def test_only_one_of_two_concurrent_transitions_succeeds(client, editor):
    """Both wrote and both were told "ok", so an editor's scrap was lost to a
    concurrent approval. The loser must now be told, not ignored.

    Which rejection it gets depends on how the two requests interleave, and
    both are correct. If they truly overlap, the stale write is caught at
    commit (409). If the second happens to read after the first commits, it
    sees the new status and the state machine rejects the transition (422).
    What must never happen is two successes."""
    doc_id = _submitted_doc(client, editor, "race-both")
    responses = _race(client, editor, doc_id, ("approved", "scrapped"))

    codes = sorted(r.status_code for r in responses)
    assert codes[0] == 200, codes
    assert codes[1] in (409, 422), codes


def test_the_loser_is_told_what_happened(client, editor):
    doc_id = _submitted_doc(client, editor, "race-message")
    responses = _race(client, editor, doc_id, ("approved", "scrapped"))

    loser = next(r for r in responses if r.status_code != 200)
    detail = loser.json()["detail"]
    assert loser.status_code in (409, 422), loser.status_code
    if loser.status_code == 409:
        assert "changed by someone else" in detail
    else:
        # The state machine's own rejection: it names the transition it refused.
        assert detail, "a rejected transition must say why"


def test_the_stored_state_matches_the_winning_response(client, editor):
    """The document must end up in the state the successful caller was told it
    was in -- not the other one."""
    doc_id = _submitted_doc(client, editor, "race-consistent")
    responses = _race(client, editor, doc_id, ("approved", "scrapped"))

    winner = next(r for r in responses if r.status_code == 200)
    rows = client.get("/api/documents", headers=_h(editor)).json()
    row = next(d for d in rows if d["google_doc_id"] == doc_id)
    assert row["status"] == winner.json()["status"]


def test_a_lost_approval_leaves_no_phantom_sign_off(client, editor):
    """transition() stamps approved_by before the commit, so a rolled-back
    approval must not leave the article looking signed off."""
    doc_id = _submitted_doc(client, editor, "race-signoff")
    responses = _race(client, editor, doc_id, ("approved", "scrapped"))

    rows = client.get("/api/documents", headers=_h(editor)).json()
    row = next(d for d in rows if d["google_doc_id"] == doc_id)
    if row["status"] != "approved":
        assert not row["approved_by"], "a rejected approval left a sign-off"


def test_sequential_transitions_are_unaffected(client, editor):
    """Optimistic locking must not break the ordinary one-at-a-time path."""
    doc_id = _submitted_doc(client, editor, "race-sequential")
    r = client.put(f"/api/documents/{doc_id}/status",
                   json={"status": "approved", "reason": "ok"}, headers=_h(editor))
    assert r.status_code == 200, r.text
    r2 = client.put(f"/api/documents/{doc_id}/status",
                    json={"status": "published", "reason": "ok"}, headers=_h(editor))
    assert r2.status_code == 200, r2.text
