"""Keep each worker's rubric-weight cache in step with the database.

`app.scoring.constitution._overrides` is a per-process dict, loaded once at
startup. The deployment guide runs four workers, so an admin's weight change
reached only the worker that served the write: every other worker went on
scoring with the old weights until the next restart, and the same article
scored differently depending on which worker answered. The guide already warns
that the vector store and the rate limiter are per-process; this was a third
instance, and the one that silently changes scores.

The weights are read on the evaluation path, which is synchronous and has no
session, so rather than thread one down into the engine each worker re-reads
the overrides table when its cache is older than `_TTL_SECONDS`. A worker is
then at most that far behind, instead of indefinitely stale.
"""
from __future__ import annotations

import logging
import time
from typing import Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.scoring import constitution as C

log = logging.getLogger("jalebi")

# Short enough that an admin sees their change take effect while they are still
# looking at the screen; long enough that it is one small query per worker
# rather than one per evaluation.
_TTL_SECONDS = 30.0

_last_refresh = 0.0


async def refresh_if_stale(session: AsyncSession, *, force: bool = False) -> bool:
    """Re-read rubric overrides if this worker's cache has gone stale.

    Returns True if a refresh happened. Best-effort: a failed read leaves the
    existing cache in place, since scoring with slightly stale weights is far
    better than not scoring at all.
    """
    global _last_refresh

    now = time.monotonic()
    if not force and (now - _last_refresh) < _TTL_SECONDS:
        return False

    # Claim the slot before awaiting, so concurrent requests on this worker do
    # not all issue the same query.
    _last_refresh = now

    try:
        from app.db.models import RubricOverride

        rows = (await session.execute(select(RubricOverride))).scalars().all()
        C.replace_all_overrides({r.content_type: r.weights for r in rows})
        return True
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("Could not refresh rubric overrides: %s", exc)
        return False


def mark_fresh() -> None:
    """Record that the cache is current, e.g. right after startup loaded it."""
    global _last_refresh
    _last_refresh = time.monotonic()


def reset_for_tests() -> None:
    global _last_refresh
    _last_refresh = 0.0
