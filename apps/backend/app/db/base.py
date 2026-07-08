"""Async SQLAlchemy engine + session.

Defaults to a local SQLite file so the whole app runs with no external service;
point `JALEBI_DATABASE_URL` at Postgres (`postgresql+asyncpg://...`) in production.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(settings.database_url, echo=False, future=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db() -> None:
    """Create tables if they don't exist (dev/small-scale). Use Alembic in prod."""
    from app.db import models  # noqa: F401 — register mappers

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    """FastAPI dependency yielding a session."""
    async with SessionLocal() as session:
        yield session
