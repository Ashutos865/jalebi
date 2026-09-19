"""Database models — users, documents, evaluations, knowledge base, rubric
overrides, audit log. Portable across SQLite (dev) and Postgres (prod)."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.util import utcnow

# Roles: writer < editor < admin. Stored as plain strings for portability.
ROLE_WRITER = "writer"
ROLE_EDITOR = "editor"
ROLE_ADMIN = "admin"
ROLE_RANK = {ROLE_WRITER: 0, ROLE_EDITOR: 1, ROLE_ADMIN: 2}


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    role: Mapped[str] = mapped_column(String(20), default=ROLE_WRITER)
    google_sub: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    department: Mapped[str] = mapped_column(String(100), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_login: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    evaluations: Mapped[list["Evaluation"]] = relationship(back_populates="owner")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Optimistic locking (see __mapper_args__ at the end of this class).
    version_id: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    google_doc_id: Mapped[Optional[str]] = mapped_column(String(128), index=True, nullable=True)
    url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    title: Mapped[str] = mapped_column(String(500), default="Untitled")
    owner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    content_type: Mapped[str] = mapped_column(String(50), default="news_article")
    # TIES SOP tracking-sheet fields
    # Production-loop state — see app/workflow/states.py. Indexed: the tracker
    # filters and sorts on it on every dashboard load.
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    editor: Mapped[str] = mapped_column(String(200), default="")
    published_for: Mapped[str] = mapped_column(String(200), default="")
    co_authors: Mapped[str] = mapped_column(String(500), default="")
    # SOP §4: the editor runs the article through real AI/plagiarism checkers
    # (Quillbot, CopyLeaks, SmallSEOTools, DupliChecker) and records the result
    # here. Deliberately recorded, never estimated — a guessed score would be
    # unreliable, and a false accusation affects an intern's certificate and LOR.
    ai_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    plagiarism_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    integrity_checked_by: Mapped[str] = mapped_column(String(200), default="")
    integrity_checked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # --- Production loop (SOP §3) --------------------------------------------
    # The assignment brief: topic and angle live in the doc itself; these are the
    # fields the loop needs to run and to know when something is overdue.
    assigned_to: Mapped[str] = mapped_column(String(200), default="")
    assigned_by: Mapped[str] = mapped_column(String(200), default="")
    word_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    word_max: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Phase clocks. `phase_started_at` is reset on every transition that starts a
    # new SOP window, so "overdue" always means the *current* phase.
    assigned_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    submitted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    phase_started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    approved_by: Mapped[str] = mapped_column(String(200), default="")
    # Set when an editor signs off despite failing SOP checks. The SOP gives the
    # editor final say, so this records the exception rather than blocking it.
    override_reason: Mapped[str] = mapped_column(Text, default="")
    # Why a piece was reassigned or scrapped (SOP §4 veto authority).
    escalation_reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    # Two editors acting on the same submitted article -- one approving, one
    # scrapping -- each validated against the status they had read, each wrote,
    # and each was told "ok". The scrap silently vanished and the piece went on
    # to publication. Every UPDATE now carries the version it read, so a
    # concurrent write matches no row and raises StaleDataError, which the
    # routes surface as 409.
    __mapper_args__ = {"version_id_col": version_id}


class Evaluation(Base):
    __tablename__ = "evaluations"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    document_id: Mapped[Optional[int]] = mapped_column(ForeignKey("documents.id"), nullable=True)
    google_doc_id: Mapped[Optional[str]] = mapped_column(String(128), index=True, nullable=True)
    title: Mapped[str] = mapped_column(String(500), default="Untitled")
    content_type: Mapped[str] = mapped_column(String(50), index=True)
    provider: Mapped[str] = mapped_column(String(40), default="mock")
    model: Mapped[str] = mapped_column(String(120), default="")
    overall_score: Mapped[int] = mapped_column(Integer, index=True)
    publication_ready: Mapped[bool] = mapped_column(Boolean, default=False)
    publication_readiness: Mapped[str] = mapped_column(String(40))
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    result: Mapped[dict] = mapped_column(JSON)  # full EvaluationResult
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )

    owner: Mapped[Optional["User"]] = relationship(back_populates="evaluations")


class KnowledgeDoc(Base):
    """Editorial knowledge base source (handbook, exemplars, notes). Embedded into
    the vector store separately (P4)."""

    __tablename__ = "knowledge_docs"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(40), index=True)  # handbook|approved|rejected|note|example|style|methodology
    title: Mapped[str] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(Text)
    content_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RubricOverride(Base):
    """Admin-tunable weights per content type (P5). Empty table = use code defaults."""

    __tablename__ = "rubric_overrides"

    id: Mapped[int] = mapped_column(primary_key=True)
    content_type: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    weights: Mapped[dict] = mapped_column(JSON)  # {dimension_key: weight}
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    actor_email: Mapped[str] = mapped_column(String(320), default="")
    action: Mapped[str] = mapped_column(String(80), index=True)
    target: Mapped[str] = mapped_column(String(200), default="")
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
