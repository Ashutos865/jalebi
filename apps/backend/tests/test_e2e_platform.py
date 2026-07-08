"""End-to-end platform test (P3–P6) on an isolated SQLite DB with full app lifespan.

Exercises: dev-login (admin), evaluate + persistence, history, analytics, knowledge
ingest + RAG retrieval, admin rubric override + audit log, integrity analysis, and
role-based access control.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

# Env (isolated DB, admin email, dev login) is configured in tests/conftest.py,
# which pytest loads before any test module — see that file.
from app.main import app

STRONG = (
    "India's merchandise exports rose 12.7% in FY24\n\n"
    "According to Ministry of Commerce data (https://commerce.gov.in), exports reached "
    "$437 billion, led by electronics. Historically, such growth coincides with rupee "
    'stability. "The trend is encouraging but fragile," said one economist.'
)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:  # `with` runs lifespan → tables created, index built
        yield c


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_full_flow(client):
    # 1. Admin dev-login (founder is auto-promoted to admin).
    r = client.post("/api/auth/dev-login", json={"email": "founder@ties.org", "name": "Founder"})
    assert r.status_code == 200
    admin_tok = r.json()["access_token"]
    assert r.json()["user"]["role"] == "admin"

    # A writer logs in too.
    w = client.post("/api/auth/dev-login", json={"email": "writer@ties.org"}).json()
    writer_tok = w["access_token"]
    assert w["user"]["role"] == "writer"

    # 2. Seed the knowledge base (RAG) as admin.
    r = client.post("/api/knowledge", headers=_auth(admin_tok), json={
        "kind": "handbook", "title": "Attribution rule",
        "content": "Every statistic must be attributed to a primary source with a date.",
        "content_type": "news_article",
    })
    assert r.status_code == 200

    # 3. Writer evaluates a document (persisted, owned by writer).
    r = client.post("/api/evaluate", headers=_auth(writer_tok), json={
        "text": STRONG, "content_type": "news_article",
        "title": "Exports FY24", "doc_id": "doc-abc",
    })
    assert r.status_code == 200
    body = r.json()
    assert 0 <= body["overall_score"] <= 100
    assert body["meta"]["evaluator"] == "mock"

    # 4. History: writer sees their own evaluation.
    hist = client.get("/api/evaluations", headers=_auth(writer_tok)).json()
    assert len(hist) >= 1 and hist[0]["title"] == "Exports FY24"

    # 5. Analytics requires editor+ — writer forbidden, admin allowed.
    assert client.get("/api/analytics/overview", headers=_auth(writer_tok)).status_code == 403
    ov = client.get("/api/analytics/overview", headers=_auth(admin_tok)).json()
    assert ov["total_evaluations"] >= 1
    assert "by_content_type" in ov

    # 6. Admin rubric override + renormalization.
    r = client.put("/api/admin/rubrics/news_article", headers=_auth(admin_tok),
                   json={"weights": {"accuracy": 0.5}})
    assert r.status_code == 200
    total = round(sum(d["weight"] for d in r.json()["dimensions"]), 2)
    assert total == 1.0  # renormalized

    # 7. Audit log recorded the knowledge add + rubric update.
    logs = client.get("/api/admin/logs", headers=_auth(admin_tok)).json()
    actions = {l["action"] for l in logs}
    assert {"knowledge.add", "rubric.update"} <= actions

    # 8. Integrity analysis (P6).
    r = client.post("/api/integrity", json={
        "text": "Exports clearly rose 40% last year. Everyone knows this is a triumph."
    })
    assert r.status_code == 200
    rep = r.json()
    assert rep["integrity_score"] < 100
    kinds = {f["type"] for f in rep["findings"]}
    assert "bias" in kinds or "unattributed_claim" in kinds

    # 9. Providers endpoint lists mock as available/active.
    prov = client.get("/api/providers").json()
    assert prov["active"] == "mock"
    assert any(p["id"] == "mock" and p["available"] for p in prov["providers"])


def test_writer_cannot_admin(client):
    tok = client.post("/api/auth/dev-login", json={"email": "w2@ties.org"}).json()["access_token"]
    assert client.get("/api/admin/users", headers=_auth(tok)).status_code == 403
    assert client.get("/api/admin/logs", headers=_auth(tok)).status_code == 403


def test_dashboard_served(client):
    r = client.get("/dashboard")
    assert r.status_code == 200 and "Jalebi" in r.text
