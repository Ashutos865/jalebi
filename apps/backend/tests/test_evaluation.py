"""Tests for the editorial pipeline and the API.

These assert the *contract* and the *content-awareness* of the mock: a weak draft
scores worse than a strong one, and improving the text moves the score up. Because
the mock seeds off a content hash, results are deterministic.
"""
from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from app.main import app
from app.pipeline.orchestrator import MockEvaluator
from app.rubrics import RUBRICS
from app.schemas.evaluation import (
    ContentType,
    EvaluationRequest,
    PublicationReadiness,
)

client = TestClient(app)

WEAK = (
    "Shocking news!!! You won't believe what happened. Experts believe this is "
    "basically insane and it will change everything. Many people say so."
)

STRONG = (
    "India's merchandise exports rose 12.7% year-on-year in FY24\n\n"
    "According to Ministry of Commerce data released this week, India's merchandise "
    "exports reached $437 billion in FY24, a 12.7% increase over the previous year "
    "(https://commerce.gov.in). The rise was led by electronics and pharmaceuticals.\n\n"
    "Historically, export growth of this scale has coincided with rupee stability. "
    "Analysts at the RBI note that the strategic shift toward electronics manufacturing, "
    "supported by the PLI scheme, contributed roughly 3 percentage points to the gain.\n\n"
    "Economists caution that global demand remains uncertain. \"The trend is encouraging "
    "but fragile,\" said one trade economist, pointing to slowing orders from Europe."
)


def _run(req: EvaluationRequest):
    # asyncio.run (not get_event_loop) — since 3.12 the latter no longer creates a
    # loop implicitly on the main thread and raises RuntimeError.
    return asyncio.run(MockEvaluator().evaluate(req))


def test_all_rubrics_have_reviewers():
    from app.pipeline.mock_reviewer import REVIEWERS

    for rubric in RUBRICS.values():
        for dim in rubric.dimensions:
            assert dim.key in REVIEWERS, f"missing reviewer for {dim.key}"


def test_rubric_weights_sum_to_one():
    for ct, rubric in RUBRICS.items():
        total = round(sum(d.weight for d in rubric.dimensions), 6)
        assert total == 1.0, f"{ct} weights sum to {total}"


def test_strong_beats_weak():
    weak = _run(EvaluationRequest(text=WEAK, content_type=ContentType.news_article))
    strong = _run(EvaluationRequest(text=STRONG, content_type=ContentType.news_article))
    assert strong.overall_score > weak.overall_score


def test_deterministic():
    a = _run(EvaluationRequest(text=STRONG, content_type=ContentType.news_article))
    b = _run(EvaluationRequest(text=STRONG, content_type=ContentType.news_article))
    assert a.overall_score == b.overall_score


def test_result_shape():
    res = _run(EvaluationRequest(text=STRONG, content_type=ContentType.news_article))
    rubric = RUBRICS[ContentType.news_article]
    assert len(res.categories) == len(rubric.dimensions)
    assert 0 <= res.overall_score <= 100
    assert isinstance(res.publication_readiness, PublicationReadiness)
    assert res.publication_ready == (
        res.publication_readiness == PublicationReadiness.ready
    )
    assert res.strengths, "should always surface at least one strength"
    assert res.next_steps, "should always give a next step"
    assert res.meta.word_count > 0


def test_sensational_flagged_in_neutrality():
    res = _run(EvaluationRequest(text=WEAK, content_type=ContentType.news_article))
    neutrality = next(c for c in res.categories if c.key == "neutrality")
    assert neutrality.issues, "weak sensational text should raise a neutrality issue"


# --- API surface ------------------------------------------------------------

def test_health_endpoint():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_content_types_endpoint():
    r = client.get("/api/content-types")
    assert r.status_code == 200
    assert any(item["value"] == "news_article" for item in r.json())


def test_evaluate_endpoint():
    r = client.post(
        "/api/evaluate",
        json={"text": STRONG, "content_type": "news_article", "title": "Exports"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "overall_score" in body
    assert body["content_type"] == "news_article"
    assert len(body["categories"]) > 0


def test_evaluate_rejects_empty():
    r = client.post("/api/evaluate", json={"text": "   ", "content_type": "opinion"})
    assert r.status_code in (413, 422)
