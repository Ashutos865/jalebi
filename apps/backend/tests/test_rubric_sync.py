"""An admin's weight change must reach every worker, not just one.

The override cache is a per-process dict loaded at startup. The deployment
guide runs four workers, so a change reached only the worker that served the
write; the rest scored on stale weights until restart, and the same article
scored differently depending on which worker answered.
"""
from __future__ import annotations

import asyncio

import pytest

from app.scoring import constitution as C
from app.scoring import rubric_sync

_BALANCED = {
    "accuracy": 0.50, "insight": 0.20, "narrative": 0.10,
    "depth": 0.08, "sourcing": 0.06, "writing": 0.04, "headline": 0.02,
}


class _Row:
    def __init__(self, content_type, weights):
        self.content_type = content_type
        self.weights = weights


class _Session:
    """Stands in for the shared database the other worker wrote to."""

    def __init__(self, rows):
        self._rows = rows

    async def execute(self, *args, **kwargs):
        rows = self._rows

        class _Result:
            def scalars(self):
                class _Scalars:
                    def all(self):
                        return rows

                return _Scalars()

        return _Result()


@pytest.fixture(autouse=True)
def _clean():
    C.clear_override("analysis")
    rubric_sync.reset_for_tests()
    yield
    C.clear_override("analysis")
    rubric_sync.reset_for_tests()


def test_a_worker_picks_up_another_workers_change():
    """This worker never served the write, so its cache knows nothing."""
    baseline = C.weights_for("analysis")["accuracy"]

    session = _Session([_Row("analysis", _BALANCED)])
    assert asyncio.run(rubric_sync.refresh_if_stale(session)) is True

    assert C.weights_for("analysis")["accuracy"] != baseline


def test_a_removed_override_is_dropped_too():
    """Resetting a rubric on one worker must not leave others applying it."""
    C.set_override("analysis", _BALANCED)
    overridden = C.weights_for("analysis")["accuracy"]

    asyncio.run(rubric_sync.refresh_if_stale(_Session([])))
    assert C.weights_for("analysis")["accuracy"] != overridden
    assert C.get_override("analysis") is None


def test_the_refresh_is_rate_limited():
    """One small query per worker per TTL, not one per evaluation."""
    session = _Session([_Row("analysis", _BALANCED)])
    assert asyncio.run(rubric_sync.refresh_if_stale(session)) is True
    assert asyncio.run(rubric_sync.refresh_if_stale(session)) is False
    assert asyncio.run(rubric_sync.refresh_if_stale(session, force=True)) is True


def test_an_invalid_stored_override_is_skipped_not_applied():
    """A row written against an older dimension vocabulary must not zero a
    content type's scores -- the same rule startup follows."""
    baseline = C.weights_for("analysis")["accuracy"]

    asyncio.run(rubric_sync.refresh_if_stale(
        _Session([_Row("analysis", {"not_a_dimension": 1.0})])
    ))
    assert C.weights_for("analysis")["accuracy"] == baseline


def test_a_database_failure_leaves_the_existing_weights_alone():
    """Scoring with slightly stale weights beats not scoring at all."""
    C.set_override("analysis", _BALANCED)
    before = C.weights_for("analysis")["accuracy"]

    class _Broken:
        async def execute(self, *args, **kwargs):
            raise RuntimeError("database is down")

    assert asyncio.run(rubric_sync.refresh_if_stale(_Broken(), force=True)) is False
    assert C.weights_for("analysis")["accuracy"] == before
