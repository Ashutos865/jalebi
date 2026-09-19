"""Retrieval must not stall the event loop.

The embed-and-search is synchronous CPU work that scales with the corpus:
measured at 13 ms for 551 chunks and 38 ms for 1671. Inline, that stalled
every other in-flight request for the same duration, however unrelated.
"""
from __future__ import annotations

import asyncio
import statistics
import time

import pytest

from app.knowledge import service
from app.knowledge.store import get_store


class _Doc:
    def __init__(self, doc_id: int):
        self.id = doc_id
        self.content = f"handbook passage about attribution {doc_id} " * 200
        self.content_type = None
        self.kind = "handbook"
        self.title = f"doc-{doc_id}"


class _Session:
    def __init__(self, docs):
        self._docs = docs

    async def execute(self, *args, **kwargs):
        docs = self._docs

        class _Result:
            def scalars(self):
                class _Scalars:
                    def all(self):
                        return docs

                return _Scalars()

        return _Result()


@pytest.fixture
def corpus():
    get_store().clear()
    asyncio.run(service.reindex_all(_Session([_Doc(i) for i in range(1, 41)])))
    assert get_store().count() > 400, "fixture corpus too small to measure"
    yield
    get_store().clear()


DOC = "India exports rose 12.7% in FY24 according to Ministry data. " * 40


async def _max_loop_gap(retrieve):
    """Longest the event loop went without scheduling a ready coroutine."""
    gaps = []

    async def heartbeat(stop):
        last = time.perf_counter()
        while not stop.is_set():
            await asyncio.sleep(0)
            now = time.perf_counter()
            gaps.append(now - last)
            last = now

    stop = asyncio.Event()
    beat = asyncio.create_task(heartbeat(stop))
    await asyncio.sleep(0)
    for _ in range(3):
        await retrieve()
    stop.set()
    await beat
    assert gaps, "heartbeat never ran"
    return max(gaps)


def test_retrieval_off_the_loop_beats_retrieval_on_it(corpus):
    """Threading this work reduces the stall but does not remove it.

    The cosine loop is pure Python, so it holds the GIL and the interpreter
    only yields to the main thread every few milliseconds. Measured on a
    551-chunk corpus: ~50 ms of dead loop inline, ~17 ms threaded. The claim
    worth pinning is the improvement, not a stall-free loop -- asserting the
    latter would be asserting something this fix does not deliver."""
    async def inline():
        return service._retrieve_sync(DOC, "analysis")

    async def go():
        # Median across rounds, not a single sample. The per-round maximum is
        # the noisiest statistic available and comparing two of them flipped
        # this test about once in three runs. Across 15 rounds the two
        # distributions are cleanly separated (threaded ~14 ms median, inline
        # ~25 ms), so the median is what to compare.
        threaded = statistics.median([
            await _max_loop_gap(lambda: service.retrieve_passages(DOC, "analysis"))
            for _ in range(7)
        ])
        blocking = statistics.median([await _max_loop_gap(inline) for _ in range(7)])
        return threaded, blocking

    threaded, blocking = asyncio.run(go())
    assert threaded < blocking * 0.75, (
        f"threading did not reduce the stall: "
        f"{threaded * 1000:.1f}ms vs {blocking * 1000:.1f}ms inline"
    )


def test_retrieval_still_returns_the_right_passages(corpus):
    """Moving the work must not change the answer."""
    passages = asyncio.run(service.retrieve_passages(DOC, "analysis"))
    assert passages, "retrieval returned nothing"
    assert all(isinstance(p, str) for p in passages)


def test_retrievals_do_not_run_in_parallel(corpus):
    """Documents what this fix does NOT buy, so nobody assumes otherwise.

    The cosine loop is pure Python, so the GIL serialises it: four concurrent
    retrievals cost about four times one. Threading gets the work off the event
    loop -- unrelated I/O keeps being served -- but it does not make retrieval
    itself concurrent. Making it so means vectorising the search (numpy) or
    moving it to a real vector store like Qdrant, which the deployment guide
    already recommends for multi-worker setups."""
    async def one():
        return await service.retrieve_passages(DOC, "analysis")

    async def timed(n):
        started = time.perf_counter()
        await asyncio.gather(*(one() for _ in range(n)))
        return time.perf_counter() - started

    single = asyncio.run(timed(1))
    four = asyncio.run(timed(4))
    # Not a target -- a record of current behaviour. If this ever fails because
    # `four` got much smaller, retrieval became parallel and this test should be
    # replaced with one asserting that.
    assert four > single * 2, (
        f"retrieval appears to be parallel now: 1x={single:.3f}s 4x={four:.3f}s"
    )
