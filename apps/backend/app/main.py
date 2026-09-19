"""Jalebi backend — FastAPI application factory."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import enforce_production_safety, settings
from app.middleware import (
    RateLimitMiddleware,
    RequestLogMiddleware,
    SecurityHeadersMiddleware,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fail closed before serving a single request: a production deployment must not
    # run with the public default signing key, an open dev-login, or CORS=*.
    enforce_production_safety()
    # Optional error monitoring.
    if settings.sentry_dsn:
        try:
            import sentry_sdk

            sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.environment)
        except Exception:
            pass
    # Create tables (dev/small-scale; use Alembic migrations in production).
    try:
        # Dev convenience: create tables directly. In production set
        # JALEBI_AUTO_CREATE=false and run `alembic upgrade head` instead.
        if settings.auto_create_tables:
            from app.db.base import init_db

            await init_db()
        from app.db.base import SessionLocal
        from sqlalchemy import select

        async with SessionLocal() as s:
            if settings.rag_enabled:
                # Seed the TIES SOP (idempotent), then rebuild the vector index.
                from app.knowledge.seed import seed_default_knowledge
                from app.knowledge.service import reindex_all

                try:
                    await seed_default_knowledge(s)
                except Exception:
                    await s.rollback()
                await reindex_all(s)
            # Load admin rubric-weight overrides into the scoring engine.
            from app.db.models import RubricOverride
            from app.scoring import constitution as C

            for row in (await s.execute(select(RubricOverride))).scalars().all():
                try:
                    C.set_override(row.content_type, row.weights)
                except C.WeightError as exc:
                    # A stored override that no longer validates (e.g. written
                    # against the old 15-dimension vocabulary) is skipped loudly
                    # rather than silently zeroing a content type's scores.
                    logging.getLogger("jalebi").warning(
                        "Ignoring invalid rubric override for %s: %s",
                        row.content_type, exc,
                    )
    except Exception:  # keep the API up even if the DB is unreachable
        # Logged with a traceback, not printed: a failed reindex leaves the
        # vector store silently empty and RAG quietly stops working, which is
        # very hard to notice from the outside.
        logging.getLogger("jalebi").exception(
            "Startup database initialisation failed — continuing without it. "
            "RAG retrieval and admin rubric overrides may be unavailable."
        )
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Jalebi API",
        description="Editorial quality-assurance backend for TIES.",
        version="0.4.0",
        lifespan=lifespan,
    )

    # Order matters: last-added runs first. Request-ID/logging outermost, then
    # security headers, then rate limit, then CORS.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    app.add_middleware(RateLimitMiddleware, limit_per_min=settings.rate_limit_per_min)
    if settings.security_headers:
        app.add_middleware(SecurityHeadersMiddleware)
    if settings.request_logging:
        app.add_middleware(RequestLogMiddleware)

    from app.api.routes import (
        admin,
        analytics,
        auth,
        check,
        classify,
        documents,
        evaluate,
        evaluations,
        health,
        integrity,
        knowledge,
        providers,
        rewrite,
    )

    for module in (health, providers, evaluate, classify, check, rewrite, integrity, auth,
                   evaluations, documents, knowledge, analytics, admin):
        app.include_router(module.router, prefix="/api")

    # Founder/editor dashboard + admin panel (server-rendered, no build step).
    from app.dashboard.views import router as dashboard_router

    app.include_router(dashboard_router)

    @app.get("/")
    async def root() -> dict:
        return {
            "app": settings.app_name,
            "docs": "/docs",
            "health": "/api/health",
            "dashboard": "/dashboard",
        }

    return app


app = create_app()
