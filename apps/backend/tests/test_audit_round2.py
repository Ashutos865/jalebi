"""Second-round audit fixes: cache correctness, ownership, citation detection.

Each of these was reproduced before being fixed. The RAG one is the most
consequential: the feature reported itself as working while doing nothing.
"""
from __future__ import annotations

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from app.analysis.analyzers import _CITED_NEAR, analyze_integrity
from app.llm.client import LLMResponse
from app.pipeline.hybrid_evaluator import HybridEvaluator, _content_key
from app.schemas.evaluation import ContentType, EvaluationRequest
from app.scoring import constitution as C, rules


# --- the AI cache must account for retrieved knowledge ----------------------

class _RecordingClient:
    def __init__(self):
        self.systems = []

    async def complete(self, *, system, prompt, max_tokens=16000, temperature=0.0):
        self.systems.append(system)
        return LLMResponse(text=json.dumps({
            "dim_scores": {"accuracy": 80}, "issues": [],
            "summary": "s", "strengths": [], "weaknesses": [],
        }))


TEXT = "Exports rose 12% in FY24 according to Ministry data. " * 10


def test_cache_key_changes_when_knowledge_changes():
    a = _content_key(TEXT, "analysis", "m", None)
    b = _content_key(TEXT, "analysis", "m", ["Handbook: attribute every figure."])
    assert a != b


def test_cache_key_is_order_insensitive():
    """Retrieval may rank the same passages differently between calls; that
    should still be a cache hit."""
    passages = ["one", "two", "three"]
    assert _content_key(TEXT, "analysis", "m", passages) == _content_key(
        TEXT, "analysis", "m", list(reversed(passages))
    )


def test_knowledge_actually_reaches_the_model():
    """The bug: a knowledge-free evaluation poisoned the cache, so every later
    evaluation of that text reused the knowledge-free judgment — while
    reporting knowledge_used: 2."""
    client = _RecordingClient()

    async def go():
        ev1 = HybridEvaluator(client=client, provider="t", model="m", retriever=None)
        await ev1.evaluate(
            EvaluationRequest(text=TEXT, content_type=ContentType.analysis)
        )

        async def retriever(_t, _ct):
            return ["TIES handbook: attribute every statistic."]

        ev2 = HybridEvaluator(
            client=client, provider="t", model="m", retriever=retriever
        )
        return await ev2.evaluate(
            EvaluationRequest(text=TEXT, content_type=ContentType.analysis)
        )

    result = asyncio.run(go())
    assert len(client.systems) == 2, "the cached knowledge-free judgment was reused"
    assert "handbook" in client.systems[-1].lower()
    assert result.meta.knowledge_used == 1


def test_identical_requests_still_hit_the_cache():
    """The fix must not disable caching altogether."""
    client = _RecordingClient()

    async def retriever(_t, _ct):
        return ["Same passage every time."]

    async def go():
        ev = HybridEvaluator(
            client=client, provider="t", model="m2", retriever=retriever
        )
        for _ in range(3):
            await ev.evaluate(
                EvaluationRequest(text=TEXT, content_type=ContentType.analysis)
            )

    asyncio.run(go())
    assert len(client.systems) == 1, "caching stopped working"


# --- citation detection ------------------------------------------------------

@pytest.mark.parametrize("word", [
    "corruption", "adoption", "consumption", "exemption", "excited",
])
def test_substrings_are_not_citations(word):
    """Sixth occurrence of this bug class: "pti" inside "corruption"."""
    assert not _CITED_NEAR.search(word), word


def test_a_parenthesis_is_not_a_citation():
    """A bare "(" in the pattern meant any aside looked like a source, which
    erased a high-severity finding."""
    with_paren = analyze_integrity("Revenue rose 40% (a strong result).")
    without = analyze_integrity("Revenue rose 40%, a strong result.")
    assert [f.type for f in with_paren.findings] == [f.type for f in without.findings]


@pytest.mark.parametrize("text", [
    "According to the ministry, exports rose.",
    "Per RBI data, inflation eased.",
    "Reuters reported the figure.",
    "See https://commerce.gov.in for detail.",
    "The report said otherwise.",
])
def test_real_citations_are_still_detected(text):
    assert _CITED_NEAR.search(text), text


# --- opinion-as-fact must not depend on paragraph order ---------------------

def test_opinion_cap_is_order_independent():
    """low.find() checked only the first occurrence, so if that one was
    attributed the marker was treated as clean — and swapping two paragraphs
    changed the score."""
    attributed = "Critics say the policy is the best option available to anyone."
    bare = "Regardless, the policy is the best option available to anyone."

    first = {c.code for c in rules.analyze(attributed + " " + bare, "T", "analysis").caps}
    second = {c.code for c in rules.analyze(bare + " " + attributed, "T", "analysis").caps}
    assert first == second
    assert "opinion_as_fact" in first


def test_a_fully_attributed_opinion_is_not_capped():
    text = "Critics say the policy is the best option available to anyone."
    fired = {c.code for c in rules.analyze(text, "T", "analysis").caps}
    assert "opinion_as_fact" not in fired


# --- document ownership ------------------------------------------------------

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


def test_an_anonymous_evaluation_cannot_rename_a_tracked_document(client, editor):
    """/api/evaluate is unauthenticated by default, so anyone who knew a Google
    Doc id could repoint the tracker link and rename the article."""
    head = {"Authorization": f"Bearer {editor}"}
    body = {
        "text": "Exports rose 12% in FY24 according to Ministry data. " * 12,
        "content_type": "analysis",
        "doc_id": "own-1",
        "title": "Real Title",
        "doc_url": "https://docs.google.com/document/d/own-1/edit",
    }
    client.post("/api/evaluate", json=body, headers=head)

    client.post(
        "/api/evaluate",
        json={**body, "title": "PWNED", "doc_url": "https://evil.example/x"},
    )

    rows = client.get("/api/documents", headers=head).json()
    doc = next(d for d in rows if d["google_doc_id"] == "own-1")
    assert doc["title"] == "Real Title"
    assert "evil.example" not in (doc["url"] or "")


def test_the_original_author_keeps_the_credit(client, editor):
    """The tracker took `owner` from the latest evaluation, so one anonymous
    re-run blanked the writer's name."""
    head = {"Authorization": f"Bearer {editor}"}
    body = {
        "text": "Imports fell 3% in FY24 according to Ministry data. " * 12,
        "content_type": "analysis",
        "doc_id": "own-2",
        "title": "Credited",
    }
    client.post("/api/evaluate", json=body, headers=head)
    client.post("/api/evaluate", json=body)          # anonymous re-run

    rows = client.get("/api/documents", headers=head).json()
    doc = next(d for d in rows if d["google_doc_id"] == "own-2")
    assert doc["owner"] == "founder@ties.org"


# --- anonymous hearsay is not attribution -----------------------------------

@pytest.mark.parametrize("text", [
    "Many people say so.",
    "Many people are saying this is a big deal.",
    "Sources say the corruption goes right to the top.",
    "Sources said the deal collapsed overnight.",
    "Experts believe this is basically insane.",
    "Some say the policy failed.",
    "It is reportedly true.",
])
def test_unnamed_hearsay_does_not_count_as_attribution(text):
    """Adding "say" to ATTRIBUTION_MARKERS (so "Critics say ..." registered)
    made the unsourced phrasing these rules exist to catch look like sourcing.
    "sources said" had the same problem from the start."""
    stripped = C.strip_terms(text, "vague_attribution")
    assert C.count_matches(stripped, "attribution") == 0, text


@pytest.mark.parametrize("text", [
    "According to the Ministry of Commerce, exports rose.",
    "Reuters reported the figure.",
    "Critics say the policy is the best option.",
    "Dr. Rao told Parliament the scheme was sound.",
    "A study by the RBI found that inflation eased.",
    # Whose sources they are is the whole difference: an unqualified "sources
    # said" names nobody, "Ministry sources said" names an institution.
    "Ministry sources said the deal collapsed.",
    "Government sources say the scheme is under review.",
])
def test_named_attribution_still_counts(text):
    stripped = C.strip_terms(text, "vague_attribution")
    assert C.count_matches(stripped, "attribution") > 0, text


def test_the_attribution_checklist_item_fails_on_pure_hearsay():
    """The checklist read a raw document-wide count that skipped the hearsay
    strip, so a piece sourced entirely to "many people" passed the check."""
    report = rules.analyze(
        "Shocking news!!! Experts believe this changes everything. "
        "Many people say so. Sources say officials hid the figures.",
        None, "news_article",
    )
    failed = {c.name for c in report.checklist if not c.passed}
    assert "Claims are attributed" in failed
