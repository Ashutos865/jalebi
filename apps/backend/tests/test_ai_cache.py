"""One model call per distinct question, however many ask it at once.

Concurrent evaluations of the same document all missed the cache and all
called the model: eight requests, eight identical paid calls, eight times the
rate-limit consumption for one answer. That is the ordinary case -- a writer
re-running, or several editors opening the same piece.
"""
from __future__ import annotations

import asyncio
import json

import pytest

from app.llm.client import LLMResponse
from app.pipeline import hybrid_evaluator as H
from app.pipeline.hybrid_evaluator import HybridEvaluator
from app.schemas.evaluation import ContentType, EvaluationRequest

TEXT = "Exports rose 12% in FY24 according to Ministry data. " * 12
OTHER = "Imports fell 3% in FY24 according to Ministry data. " * 12


class _SlowClient:
    """A model that takes long enough for requests to pile up behind it."""

    def __init__(self, delay: float = 0.2, fail: bool = False):
        self.calls = 0
        self._delay = delay
        self._fail = fail

    async def complete(self, *, system, prompt, max_tokens=16000, temperature=0.0):
        self.calls += 1
        await asyncio.sleep(self._delay)
        if self._fail:
            raise RuntimeError("provider is down")
        return LLMResponse(text=json.dumps({
            "dim_scores": {"accuracy": 80}, "issues": [],
            "summary": "s", "strengths": [], "weaknesses": [],
        }))


@pytest.fixture(autouse=True)
def _clean_cache():
    H._AI_CACHE.clear()
    H._AI_INFLIGHT.clear()
    yield
    H._AI_CACHE.clear()
    H._AI_INFLIGHT.clear()


def _request(text=TEXT):
    return EvaluationRequest(text=text, content_type=ContentType.analysis)


def test_concurrent_evaluations_share_one_model_call():
    client = _SlowClient()

    async def go():
        ev = HybridEvaluator(client=client, provider="t", model="m", retriever=None)
        return await asyncio.gather(*(ev.evaluate(_request()) for _ in range(8)))

    results = asyncio.run(go())
    assert client.calls == 1, f"{client.calls} calls for one document"
    assert len({r.overall_score for r in results}) == 1, "waiters got different answers"


def test_different_documents_still_get_their_own_call():
    """Single-flight must key on the question, not collapse everything."""
    client = _SlowClient()

    async def go():
        ev = HybridEvaluator(client=client, provider="t", model="m", retriever=None)
        await asyncio.gather(ev.evaluate(_request(TEXT)), ev.evaluate(_request(OTHER)))

    asyncio.run(go())
    assert client.calls == 2, client.calls


def test_the_answer_is_still_cached_for_later_requests():
    client = _SlowClient(delay=0.0)

    async def go():
        ev = HybridEvaluator(client=client, provider="t", model="m", retriever=None)
        await ev.evaluate(_request())
        await ev.evaluate(_request())

    asyncio.run(go())
    assert client.calls == 1, "the in-flight slot broke ordinary caching"


def test_a_failure_does_not_leave_waiters_hanging():
    """Everyone asked the same question, so a failure is their answer too --
    and the slot must be released so the next request can retry."""
    client = _SlowClient(fail=True)

    async def go():
        ev = HybridEvaluator(client=client, provider="t", model="m", retriever=None)
        return await asyncio.gather(
            *(ev.evaluate(_request()) for _ in range(4)),
            return_exceptions=True,
        )

    results = asyncio.run(asyncio.wait_for(go(), timeout=5))
    assert len(results) == 4
    assert not H._AI_INFLIGHT, "a failed call left its slot behind"


def test_a_later_request_can_retry_after_a_failure():
    client = _SlowClient(delay=0.0, fail=True)

    async def go():
        ev = HybridEvaluator(client=client, provider="t", model="m", retriever=None)
        try:
            await ev.evaluate(_request())
        except Exception:
            pass
        client._fail = False
        return await ev.evaluate(_request())

    result = asyncio.run(go())
    assert result is not None
    assert client.calls == 2, "the failure was cached instead of retried"
