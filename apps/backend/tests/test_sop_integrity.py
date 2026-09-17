"""SOP §4 research integrity: recorded AI/plagiarism percentages and their caps.

Jalebi records what a real checker (Quillbot / CopyLeaks / SmallSEOTools /
DupliChecker) reported. It never estimates these itself: a wrong number here
would accuse a writer in a process that affects their certificate and LOR.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.scoring.constitution import (
    MAX_AI_PERCENT, MAX_PLAGIARISM_PERCENT, integrity_verdict,
)


@pytest.fixture(scope="module")
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def admin_token(client):
    r = client.post("/api/auth/dev-login", json={"email": "founder@ties.org"})
    return r.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# --- the caps themselves -----------------------------------------------------

def test_sop_caps_match_the_document():
    assert MAX_AI_PERCENT == 20.0
    assert MAX_PLAGIARISM_PERCENT == 15.0


def test_within_caps_passes():
    v = integrity_verdict(18.0, 12.0)
    assert v["checked"] and v["passed"] and v["breaches"] == []


def test_at_the_cap_passes():
    """The SOP says 'must not exceed 20%', so exactly 20 is allowed."""
    assert integrity_verdict(20.0, 15.0)["passed"]


def test_ai_over_cap_fails_with_an_explanation():
    v = integrity_verdict(35.0, 5.0)
    assert not v["passed"]
    assert len(v["breaches"]) == 1
    assert "35%" in v["breaches"][0] and "20%" in v["breaches"][0]


def test_plagiarism_over_cap_fails():
    v = integrity_verdict(5.0, 22.0)
    assert not v["passed"] and "22%" in v["breaches"][0]


def test_both_breaches_are_reported():
    assert len(integrity_verdict(40.0, 30.0)["breaches"]) == 2


def test_unchecked_is_not_a_pass():
    """No result yet is a distinct state from a clean result."""
    v = integrity_verdict(None, None)
    assert v["checked"] is False and v["passed"] is False
    assert integrity_verdict(10.0, None)["checked"] is False


# --- the endpoint ------------------------------------------------------------

def _track(client, token, doc_id: str):
    """Evaluating a document creates its Document row."""
    client.post(
        "/api/evaluate",
        json={
            "text": "Exports rose 12% in FY24 according to Ministry data. " * 12,
            "content_type": "analysis",
            "doc_id": doc_id,
        },
        headers=_auth(token),
    )


def test_editor_can_record_integrity_results(client, admin_token):
    _track(client, admin_token, "doc-integrity-1")
    r = client.put(
        "/api/documents/doc-integrity-1/integrity",
        json={"ai_percent": 12.0, "plagiarism_percent": 8.0},
        headers=_auth(admin_token),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] and body["passed"] and body["checked"]


def test_recorded_breach_is_reported(client, admin_token):
    _track(client, admin_token, "doc-integrity-2")
    r = client.put(
        "/api/documents/doc-integrity-2/integrity",
        json={"ai_percent": 55.0, "plagiarism_percent": 40.0},
        headers=_auth(admin_token),
    )
    assert r.status_code == 200 and not r.json()["passed"]
    assert len(r.json()["breaches"]) == 2


def test_results_appear_in_the_document_list(client, admin_token):
    _track(client, admin_token, "doc-integrity-3")
    client.put(
        "/api/documents/doc-integrity-3/integrity",
        json={"ai_percent": 9.0, "plagiarism_percent": 4.0},
        headers=_auth(admin_token),
    )
    docs = client.get("/api/documents", headers=_auth(admin_token)).json()
    row = next(d for d in docs if d["google_doc_id"] == "doc-integrity-3")
    assert row["integrity"]["passed"] is True
    assert row["integrity"]["ai_percent"] == 9.0
    assert row["integrity_checked_by"] == "founder@ties.org"
    assert row["integrity_checked_at"]


def test_untracked_document_is_404(client, admin_token):
    r = client.put(
        "/api/documents/no-such-doc/integrity",
        json={"ai_percent": 1.0, "plagiarism_percent": 1.0},
        headers=_auth(admin_token),
    )
    assert r.status_code == 404


def test_percentages_must_be_in_range(client, admin_token):
    _track(client, admin_token, "doc-integrity-4")
    for payload in [
        {"ai_percent": -1.0, "plagiarism_percent": 5.0},
        {"ai_percent": 101.0, "plagiarism_percent": 5.0},
        {"ai_percent": 5.0, "plagiarism_percent": 150.0},
    ]:
        r = client.put(
            "/api/documents/doc-integrity-4/integrity",
            json=payload, headers=_auth(admin_token),
        )
        assert r.status_code == 422, payload


def test_requires_editor_role(client):
    """A writer must not be able to certify their own article."""
    token = client.post(
        "/api/auth/dev-login", json={"email": "writer-int@ties.org"}
    ).json()["access_token"]
    r = client.put(
        "/api/documents/doc-integrity-1/integrity",
        json={"ai_percent": 1.0, "plagiarism_percent": 1.0},
        headers=_auth(token),
    )
    assert r.status_code == 403


def test_endpoint_requires_authentication(client):
    r = client.put(
        "/api/documents/doc-integrity-1/integrity",
        json={"ai_percent": 1.0, "plagiarism_percent": 1.0},
    )
    assert r.status_code in (401, 403)
