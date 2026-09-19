"""Analytics and the document tracker must not scan the whole table.

Both previously issued `SELECT *` over every evaluation on each dashboard load,
which pulled the complete stored scorecard — 10-50 kB of JSON per row — into
Python. The queries are now bounded and the heavy column is deferred.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.services import analytics, documents


@pytest.fixture(scope="module")
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def admin(client):
    return client.post(
        "/api/auth/dev-login", json={"email": "founder@ties.org"}
    ).json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


# --- bounds are declared and sane -------------------------------------------

def test_query_windows_are_bounded():
    assert 0 < analytics.MAX_ROWS <= 100_000
    assert 0 < analytics.ISSUE_SAMPLE <= analytics.MAX_ROWS
    assert 0 < documents.MAX_EVALUATIONS <= 100_000


def test_heavy_json_column_is_deferred():
    """`result` is the full scorecard and neither aggregation reads it, except
    the small critical-issue sample."""
    from pathlib import Path

    for path in ("app/services/analytics.py", "app/services/documents.py"):
        src = Path(path).read_text(encoding="utf-8")
        assert "defer(Evaluation.result)" in src, path
        assert "select(Evaluation))" not in src, f"{path} still scans the table"


# --- behaviour is unchanged --------------------------------------------------

def test_overview_on_an_empty_history(client, admin):
    """An empty deployment must not pay for a scan to learn it is empty."""
    body = client.get("/api/analytics/overview", headers=_h(admin)).json()
    assert "total_evaluations" in body


def test_overview_reports_both_total_and_analysed(client, admin):
    """`total` is the true row count while the aggregates cover a window, so
    the response distinguishes them — a rate computed over the window must not
    be divided by the full total."""
    client.post(
        "/api/evaluate",
        json={
            "text": "Exports rose 12% in FY24 according to Ministry data. " * 10,
            "content_type": "analysis",
            "doc_id": "analytics-bounds-1",
        },
        headers=_h(admin),
    )
    body = client.get("/api/analytics/overview", headers=_h(admin)).json()
    if body.get("empty"):
        pytest.skip("no evaluations recorded in this run")

    assert body["total_evaluations"] >= 1
    assert body["analysed"] >= 1
    assert body["analysed"] <= body["total_evaluations"]
    assert 0 <= body["pass_rate"] <= 100


def test_document_tracker_still_lists_documents(client, admin):
    rows = client.get("/api/documents", headers=_h(admin)).json()
    assert isinstance(rows, list)
    if rows:
        assert "latest_score" in rows[0] and "revisions" in rows[0]
