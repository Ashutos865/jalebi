"""Small shared helpers."""
from __future__ import annotations

import time
from datetime import datetime, timezone


def now() -> float:
    """Monotonic start marker for timing."""
    return time.perf_counter()


def elapsed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def utcnow() -> datetime:
    """Timezone-aware UTC timestamp for DB rows."""
    return datetime.now(timezone.utc)
