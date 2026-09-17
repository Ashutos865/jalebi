"""LLMEvaluator + provider registry tests — no network, no API keys.

A fake LLM client exercises the parse / repair / weight-mapping logic that every
provider shares. Registry tests confirm availability and model resolution.
"""
from __future__ import annotations

import asyncio
import json

from app.llm import registry
from app.llm.client import LLMClient, LLMResponse
from app.pipeline.llm_evaluator import LLMEvaluator
from app.rubrics import get_rubric
from app.schemas.evaluation import ContentType, EvaluationRequest, PublicationReadiness

REQ = EvaluationRequest(
    text="India's exports rose 12.7% in FY24, per Ministry of Commerce data.",
    content_type=ContentType.news_article,
    title="Exports FY24",
)


def _payload(overall=88, readiness="Needs Minor Revision") -> str:
    rubric = get_rubric(ContentType.news_article)
    cats = [
        {"name": d.name, "key": d.key, "score": 88, "summary": "ok",
         "issues": [], "recommendations": []}
        for d in rubric.dimensions
    ]
    return json.dumps({
        "overall_score": overall, "publication_ready": False,
        "publication_readiness": readiness, "summary": "Close.",
        "categories": cats, "critical_issues": [],
        "strengths": ["Well sourced."], "next_steps": ["Add a source."],
    })


class _Fake(LLMClient):
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []
        self.systems = []

    async def complete(self, *, system, prompt, max_tokens=16000):
        self.calls.append(prompt)
        self.systems.append(system)
        return LLMResponse(text=self._responses.pop(0))


def _run(ev, req):
    # asyncio.run (not get_event_loop) — since 3.12 the latter no longer creates a
    # loop implicitly on the main thread and raises RuntimeError.
    return asyncio.run(ev.evaluate(req))


def test_maps_and_injects_weights_and_provider():
    ev = LLMEvaluator(client=_Fake([_payload()]), provider="openai", model="gpt-x")
    res = _run(ev, REQ)
    rubric = get_rubric(ContentType.news_article)
    assert res.overall_score == 88
    assert res.publication_readiness == PublicationReadiness.minor
    assert res.meta.evaluator == "openai"
    assert res.meta.model == "gpt-x"
    assert all(c.weight == rubric.weight_of(c.key) for c in res.categories)


def test_handles_fences_and_repair():
    ev = LLMEvaluator(client=_Fake(["garbage", _payload()]), provider="grok")
    res = _run(ev, REQ)
    assert res.overall_score == 88


def test_rag_passages_reach_system_prompt():
    fake = _Fake([_payload()])

    async def retriever(text, content_type):
        return ["Handbook: attribute every statistic."]

    ev = LLMEvaluator(client=fake, provider="anthropic", retriever=retriever)
    res = _run(ev, REQ)
    assert res.meta.knowledge_used == 1
    assert "Handbook: attribute every statistic." in fake.systems[0]


# --- registry ---------------------------------------------------------------

def test_mock_always_available_and_builds():
    ids = {p.id for p in registry.configured_providers()}
    assert "mock" in ids
    assert registry.build_evaluator("mock").name == "mock"


def test_unknown_provider_raises():
    try:
        registry.get_spec("does-not-exist")
        assert False
    except ValueError:
        pass


def test_openai_requires_model(monkeypatch=None):
    import os
    os.environ["OPENAI_API_KEY"] = "test"
    os.environ.pop("OPENAI_MODEL", None)
    spec = registry.get_spec("openai")
    assert spec.is_configured()
    try:
        registry.build_evaluator("openai")
        assert False, "should require a model"
    except ValueError as e:
        assert "model" in str(e).lower()
    finally:
        os.environ.pop("OPENAI_API_KEY", None)
