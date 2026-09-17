"""Admin rubric weights — the panel now changes what scoring does.

Previously PUT /api/admin/rubrics/{type} persisted to app/rubrics, which no
scoring path read: an admin could tune weights, see them saved and returned,
and change nothing about any score. It also validated only the dimension *keys*,
so an all-zero override normalised to every weight being 0.0 (every document
scoring 0) and negatives inverted the score.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.scoring import constitution as C


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


@pytest.fixture(autouse=True)
def _clean():
    yield
    for ct in ("analysis", "breaking_news", "opinion", "news_article"):
        C.clear_override(ct)


# --- validation (M5) --------------------------------------------------------

def test_valid_override_is_accepted():
    eff = C.set_override("analysis", {"accuracy": 0.5})
    assert round(sum(eff.values()), 6) == 1.0


@pytest.mark.parametrize("weights,why", [
    ({}, "empty"),
    ({"accuracy": 0.0}, "all zero"),
    ({"accuracy": -0.5}, "negative"),
    ({"accuracy": float("nan")}, "NaN"),
    ({"accuracy": float("inf")}, "infinite"),
    ({"not_a_dimension": 0.5}, "unknown key"),
    ({"accuracy": "high"}, "non-numeric"),
])
def test_bad_overrides_are_rejected(weights, why):
    with pytest.raises(C.WeightError):
        C.validate_weights(weights)


def test_all_zero_would_have_scored_every_document_zero():
    """The specific catastrophe the old `or 1.0` fallback created."""
    with pytest.raises(C.WeightError, match="more than zero"):
        C.validate_weights({k: 0.0 for k in C.DIMENSION_KEYS})


# --- the override actually reaches scoring ----------------------------------

def test_override_changes_the_effective_weights():
    C.clear_override("analysis")          # start from the base, not a leftover
    before = C.weights_for("analysis")
    C.set_override("analysis", {"accuracy": 0.9})
    after = C.weights_for("analysis")
    assert after["accuracy"] > before["accuracy"]
    assert round(sum(after.values()), 6) == 1.0


def test_override_changes_a_real_score(client, admin):
    """The whole point: tuning weights must move the number."""
    text = (
        "Exports rose 12.7% in FY24 according to Ministry of Commerce data "
        "(https://commerce.gov.in). Analysts note electronics led the gain. "
    ) * 6
    body = {"text": text, "content_type": "analysis"}

    base = client.post("/api/evaluate", json=body).json()["overall_score"]

    # Push everything onto the dimension this text scores worst on.
    client.put("/api/admin/rubrics/analysis",
               json={"weights": {"insight": 1.0}}, headers=_h(admin))
    tuned = client.post("/api/evaluate", json=body).json()["overall_score"]

    assert tuned != base, "admin weights must change the score"


def test_reset_restores_the_base_weights(client, admin):
    base = C.weights_for("opinion")
    client.put("/api/admin/rubrics/opinion",
               json={"weights": {"accuracy": 0.9}}, headers=_h(admin))
    assert C.weights_for("opinion") != base
    client.delete("/api/admin/rubrics/opinion", headers=_h(admin))
    assert C.weights_for("opinion") == base


# --- the endpoint -----------------------------------------------------------

def test_endpoint_lists_the_live_dimensions(client, admin):
    rows = client.get("/api/admin/rubrics", headers=_h(admin)).json()
    row = next(r for r in rows if r["content_type"] == "analysis")
    assert [d["key"] for d in row["dimensions"]] == C.DIMENSION_KEYS
    assert round(sum(d["weight"] for d in row["dimensions"]), 6) == 1.0


def test_endpoint_reports_normalisation_honestly(client, admin):
    """Asking for accuracy=0.5 alongside the other defaults yields less than
    0.5 after normalising. The response says so rather than echoing a number
    the admin never gets."""
    r = client.put("/api/admin/rubrics/breaking_news",
                   json={"weights": {"accuracy": 0.5}}, headers=_h(admin))
    body = r.json()
    assert body["requested"] == {"accuracy": 0.5}
    assert body["normalised"] is True
    effective = {d["key"]: d["weight"] for d in body["dimensions"]}
    assert effective["accuracy"] != 0.5
    assert round(sum(effective.values()), 6) == 1.0


def test_endpoint_rejects_bad_weights(client, admin):
    for weights in ({"accuracy": -1}, {"bogus": 0.5}, {"accuracy": 0}):
        r = client.put("/api/admin/rubrics/analysis",
                       json={"weights": weights}, headers=_h(admin))
        assert r.status_code == 422, weights


def test_endpoint_rejects_unknown_content_type(client, admin):
    r = client.put("/api/admin/rubrics/not_a_type",
                   json={"weights": {"accuracy": 1.0}}, headers=_h(admin))
    assert r.status_code == 422


def test_writer_cannot_tune_weights(client):
    token = client.post(
        "/api/auth/dev-login", json={"email": "rubric-writer@ties.org"}
    ).json()["access_token"]
    r = client.put("/api/admin/rubrics/analysis",
                   json={"weights": {"accuracy": 1.0}}, headers=_h(token))
    assert r.status_code == 403


def test_prompt_endpoint_shows_the_live_prompt(client, admin):
    """It previously rendered app/pipeline/prompt.py, which no evaluation used."""
    body = client.get("/api/admin/prompts/analysis", headers=_h(admin)).json()
    assert "Senior Managing Editor" in body["system_prompt"]
