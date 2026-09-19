"""Small shared helpers."""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Optional


def now() -> float:
    """Monotonic start marker for timing."""
    return time.perf_counter()


def elapsed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def utcnow() -> datetime:
    """Timezone-aware UTC timestamp for DB rows."""
    return datetime.now(timezone.utc)


def as_utc(value: Optional[datetime]) -> Optional[datetime]:
    """Interpret a stored timestamp as UTC.

    Rows are always written with `utcnow()`, but SQLite does not store the
    offset, so they come back naive. Anything naive is therefore UTC that has
    lost its label, not local time.
    """
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def iso(value: Optional[datetime]) -> Optional[str]:
    """Serialise a timestamp for the API, always with an offset.

    A single response carried both "2026-09-19T21:47:13" (read back from
    SQLite, naive) and "2026-09-20T15:47:13+00:00" (computed in Python, never
    round-tripped). A browser reads the first as *local* time, so for a reader
    in IST an evaluation timestamp moved five and a half hours and could appear
    to be in the future, while sorting mixed the two meanings.
    """
    value = as_utc(value)
    return value.isoformat() if value else None
