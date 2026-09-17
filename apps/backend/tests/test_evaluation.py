"""Tests for the editorial pipeline and the API.

These assert the *contract* and the *content-awareness* of the mock: a weak draft
scores worse than a strong one, and improving the text moves the score up. Because
the mock seeds off a content hash, results are deterministic.
"""
from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from app.main import app
from app.pipeline.hybrid_evaluator import HybridEvaluator
from app.scoring import constitution as C
from app.schemas.content_labels import label_for
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
    # The mock provider is HybridEvaluator with no LLM client: rules-only, so
    # still fully deterministic. asyncio.run (not get_event_loop) — since 3.12
    # the latter no longer creates a loop implicitly and raises RuntimeError.
    return asyncio.run(
        HybridEvaluator(client=None, provider="mock", model="").evaluate(req)
    )


def test_every_content_type_has_a_label():
    """The sidebar dropdown and the classifier response both need one."""
    for ct in ContentType:
        assert label_for(ct), ct


def test_weights_sum_to_one_for_every_content_type():
    for ct in ContentType:
        total = round(sum(C.weights_for(ct.value).values()), 6)
        assert total == 1.0, f"{ct.value} weights sum to {total}"


def test_weights_cover_every_scoring_dimension():
    for ct in ContentType:
        assert set(C.weights_for(ct.value)) == set(C.DIMENSION_KEYS), ct.value


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
    assert len(res.categories) == len(C.DIMENSIONS)
    assert 0 <= res.overall_score <= 100
    assert isinstance(res.publication_readiness, PublicationReadiness)
    assert res.publication_ready == (
        res.publication_readiness == PublicationReadiness.ready
    )
    assert res.strengths, "should always surface at least one strength"
    assert res.next_steps, "should always give a next step"
    assert res.meta.word_count > 0


def test_sensational_text_fails_the_sourcing_checks():
    """Unsourced hype must not pass the sourcing and attribution checks, even
    though it makes no checkable claim to flag."""
    from app.scoring import rules

    report = rules.analyze(WEAK, None, "news_article")
    failed = {c.name for c in report.checklist if not c.passed}
    assert "At least one credible (Tier 1–3) source" in failed
    assert "Claims are attributed" in failed


def test_a_sourced_statistic_does_not_trip_the_unsupported_claim_cap():
    """The headline carries the figure and the body attributes it a line later —
    ordinary structure. Judging attribution one sentence at a time capped a
    fully-sourced article at 50, below unsourced hype."""
    from app.scoring import rules

    report = rules.analyze(STRONG, None, "news_article")
    assert "unsupported_claim" not in {c.code for c in report.caps}


def test_decimals_do_not_split_sentences():
    """A naive split turned '12.7%' into '12.' and '7%', and the orphaned '7%'
    then read as an unsourced statistic."""
    from app.scoring import rules

    sents = rules._sentences("Exports rose 12.7% in FY24. Electronics led.")
    assert sents[0] == "Exports rose 12.7% in FY24."
    assert len(sents) == 2


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
