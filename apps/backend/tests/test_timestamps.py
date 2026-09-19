"""Every timestamp the API emits must carry a UTC offset.

A single response carried both "2026-09-19T21:47:13" (read back from SQLite,
which does not store the offset) and "2026-09-20T15:47:13+00:00" (computed in
Python and never round-tripped). A browser reads the first as *local* time, so
for a reader in IST an evaluation timestamp moved five and a half hours and
could appear to be in the future, while sorting mixed the two meanings.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.util import as_utc, iso


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


# --- the helper --------------------------------------------------------------

def test_a_naive_timestamp_is_labelled_utc():
    """Rows are always written with utcnow(), so a naive value read back is
    UTC that lost its label -- not local time."""
    naive = datetime(2026, 9, 19, 21, 47, 13)
    assert iso(naive) == "2026-09-19T21:47:13+00:00"


def test_an_aware_timestamp_is_left_alone():
    aware = datetime(2026, 9, 19, 21, 47, 13, tzinfo=timezone.utc)
    assert iso(aware) == aware.isoformat()
    assert as_utc(aware) is aware


def test_none_stays_none():
    assert iso(None) is None
    assert as_utc(None) is None


# --- the API -----------------------------------------------------------------

def _timestamps(value, path="root"):
    """Every ISO-8601-looking string in a response, with where it came from."""
    found = []
    if isinstance(value, dict):
        for key, item in value.items():
            found += _timestamps(item, f"{path}.{key}")
    elif isinstance(value, list):
        for i, item in enumerate(value):
            found += _timestamps(item, f"{path}[{i}]")
    elif isinstance(value, str) and len(value) >= 19:
        # "2026-09-19T21:47:13..." -- a date and a time, not a plain date.
        if value[4] == "-" and value[7] == "-" and value[10] == "T":
            found.append((path, value))
    return found


def test_every_document_timestamp_carries_an_offset(client, editor):
    client.post("/api/evaluate", json={
        "text": "Exports rose 12% in FY24 according to Ministry data. " * 12,
        "content_type": "analysis", "doc_id": "tz-doc", "title": "Timestamps",
    }, headers=_h(editor))
    client.put("/api/documents/tz-doc/status",
               json={"status": "assigned", "reason": "setup"}, headers=_h(editor))
    client.put("/api/documents/tz-doc/integrity",
               json={"ai_percent": 5, "plagiarism_percent": 2}, headers=_h(editor))

    rows = client.get("/api/documents", headers=_h(editor)).json()
    row = next(r for r in rows if r["google_doc_id"] == "tz-doc")

    stamps = _timestamps(row)
    assert stamps, "no timestamps in the response to check"
    naive = [(where, value) for where, value in stamps
             if not (value.endswith("Z") or "+" in value[19:])]
    assert not naive, f"naive timestamps: {naive}"


def test_the_workflow_view_agrees_with_the_tracker(client, editor):
    """The two views read the same columns through different serialisers, so
    they must not disagree about what a timestamp means."""
    response = client.get("/api/documents/tz-doc/workflow", headers=_h(editor))
    assert response.status_code == 200, response.text

    naive = [(where, value) for where, value in _timestamps(response.json())
             if not (value.endswith("Z") or "+" in value[19:])]
    assert not naive, f"naive timestamps: {naive}"


def test_evaluation_history_timestamps_carry_an_offset(client, editor):
    """app/services/history.py serialises created_at for this listing."""
    response = client.get("/api/evaluations", headers=_h(editor))
    assert response.status_code == 200, response.text

    naive = [(where, value) for where, value in _timestamps(response.json())
             if not (value.endswith("Z") or "+" in value[19:])]
    assert not naive, f"naive timestamps: {naive}"
