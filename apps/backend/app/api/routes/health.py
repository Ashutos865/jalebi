"""Health checks: liveness (`/health`) + readiness (`/health/ready`)."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Response
from sqlalchemy import text

from app.config import settings
from app.schemas.evaluation import SCHEMA_VERSION

logger = logging.getLogger("jalebi.health")
router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    """Liveness — process is up. Always 200 (used by rate-limit exclusion + probes)."""
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.environment,
        "provider": settings.provider,
        "evaluator": "hybrid",   # rules + constrained AI judgment
        "rag_enabled": settings.rag_enabled,
        "schema_version": SCHEMA_VERSION,
    }


@router.get("/health/ready")
async def ready(response: Response) -> dict:
    """Readiness — checks the database. 503 if the DB is unreachable."""
    db_ok = True
    detail = "ok"
    try:
        from app.db.base import engine

        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        db_ok = False
        # Logged, not returned: SQLAlchemy connection errors commonly include
        # the full DSN — with credentials — and this probe is unauthenticated.
        logger.exception("Readiness probe: database connection failed")
        detail = "unavailable"
    if not db_ok:
        response.status_code = 503
    return {"status": "ready" if db_ok else "degraded", "database": detail}
