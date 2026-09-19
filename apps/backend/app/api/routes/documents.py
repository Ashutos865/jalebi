"""Documents — the tracked-link database + per-article trajectory + SOP tracking fields."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import current_user, require_role
from app.db.base import get_session
from app.db.models import ROLE_EDITOR, Document, User
from app.integrations.notify import notify
from app.scoring.constitution import integrity_verdict
from app.services import documents
from app.services.audit import log_action
from app.util import utcnow
from app.workflow import service as workflow
from app.workflow import states

router = APIRouter(prefix="/documents", tags=["documents"])

# Legacy free-text statuses accepted by PATCH. The production loop uses the
# validated state machine in app/workflow/states.py instead.
_STATUSES = {"draft", "under_review", "finalized", "published"}


async def _get_doc(session: AsyncSession, google_doc_id: str) -> Document:
    doc = (
        await session.execute(
            select(Document).where(Document.google_doc_id == google_doc_id)
        )
    ).scalar_one_or_none()
    if doc is None:
        raise HTTPException(404, "Document not tracked yet.")
    return doc


def _workflow_out(doc: Document) -> dict:
    sla = workflow.sla_for(doc)
    return {
        "status": doc.status,
        "next_states": states.next_states(doc.status),
        "assigned_to": doc.assigned_to,
        "assigned_by": doc.assigned_by,
        "editor": doc.editor,
        "word_min": doc.word_min,
        "word_max": doc.word_max,
        "assigned_at": doc.assigned_at.isoformat() if doc.assigned_at else None,
        "submitted_at": doc.submitted_at.isoformat() if doc.submitted_at else None,
        "approved_at": doc.approved_at.isoformat() if doc.approved_at else None,
        "approved_by": doc.approved_by,
        "override_reason": doc.override_reason,
        "escalation_reason": doc.escalation_reason,
        "blocking_reasons": workflow.blocking_reasons(doc),
        "sla": {
            "phase": sla.phase,
            "due_at": sla.due_at.isoformat() if sla.due_at else None,
            "target_at": sla.target_at.isoformat() if sla.target_at else None,
            "hours_remaining": sla.hours_remaining,
            "overdue": sla.overdue,
            "at_risk": sla.at_risk,
        },
    }


async def _notify_transition(doc: Document, previous: str, actor: User) -> None:
    """Announce the handoffs the SOP announces in the group chat."""
    messages = {
        states.SUBMITTED: f"📝 *{doc.title}* submitted for review by {actor.email}.",
        states.APPROVED: f"✅ GTG — *{doc.title}* approved by {actor.email}.",
        states.REASSIGNED: f"🔄 *{doc.title}* reassigned: {doc.escalation_reason}",
        states.SCRAPPED: f"🚫 *{doc.title}* scrapped: {doc.escalation_reason}",
    }
    text = messages.get(doc.status)
    if not text:
        return
    if doc.status == states.APPROVED and doc.override_reason:
        text += f"\n⚠️ Approved with override: {doc.override_reason}"
    try:
        await notify(text)
    except Exception:
        # A webhook outage must never fail the transition.
        pass


@router.get("")
async def list_docs(
    _: User = Depends(require_role(ROLE_EDITOR)),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    return await documents.list_documents(session)


class DocPatch(BaseModel):
    """Tracker edits. `status` is validated by the state machine, so this is a
    convenience wrapper over PUT /status rather than a way around it."""

    status: Optional[str] = None
    reason: str = Field("", max_length=2000)   # required to reassign or scrap
    editor: Optional[str] = None
    published_for: Optional[str] = None
    co_authors: Optional[str] = None


@router.patch("/{google_doc_id}")
async def patch_doc(
    google_doc_id: str,
    body: DocPatch,
    user: User = Depends(require_role(ROLE_EDITOR)),
    session: AsyncSession = Depends(get_session),
) -> dict:
    doc = (
        await session.execute(
            select(Document).where(Document.google_doc_id == google_doc_id)
        )
    ).scalar_one_or_none()
    if doc is None:
        raise HTTPException(404, "Document not tracked yet.")
    if body.status is not None and body.status != doc.status:
        # Route through the state machine rather than writing doc.status
        # directly. A raw write here bypassed every invariant PUT /status
        # enforces: a document could jump straight to `published` with no
        # editor recorded, no integrity check, no notification and no legal
        # transition left out of it.
        try:
            workflow.transition(doc, body.status, actor=user, reason=body.reason)
        except states.TransitionError as exc:
            raise HTTPException(422, str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from exc
    if body.editor is not None:
        doc.editor = body.editor
    if body.published_for is not None:
        doc.published_for = body.published_for
    if body.co_authors is not None:
        doc.co_authors = body.co_authors
    await session.commit()
    await log_action(session, actor=user, action="document.update", target=doc.title,
                     meta={"status": doc.status})
    return {"ok": True, "status": doc.status, "editor": doc.editor,
            "published_for": doc.published_for, "co_authors": doc.co_authors}


class AssignmentBrief(BaseModel):
    """SOP §1 assignment brief. Topic and angle live in the doc; these are the
    fields the production loop needs to run."""

    assigned_to: str = Field(..., min_length=3, max_length=200)
    editor: str = Field("", max_length=200)
    word_min: Optional[int] = Field(None, ge=0)
    word_max: Optional[int] = Field(None, ge=0)


@router.put("/{google_doc_id}/assign")
async def assign_document(
    google_doc_id: str,
    body: AssignmentBrief,
    user: User = Depends(require_role(ROLE_EDITOR)),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Issue the brief and start the 12-18h drafting clock (SOP §3 Phase 1)."""
    if body.word_min is not None and body.word_max is not None:
        if body.word_min > body.word_max:
            raise HTTPException(422, "word_min cannot exceed word_max.")

    doc = await _get_doc(session, google_doc_id)
    workflow.assign(
        doc, assigned_to=body.assigned_to, assigned_by=user.email,
        editor=body.editor, word_min=body.word_min, word_max=body.word_max,
    )
    await session.commit()
    await log_action(session, actor=user, action="document.assign",
                     target=doc.title, meta={"assigned_to": body.assigned_to})
    return {"ok": True, **_workflow_out(doc)}


class TransitionRequest(BaseModel):
    status: str
    # Required when reassigning or scrapping (SOP §4 veto authority).
    reason: str = Field("", max_length=2000)
    # Recorded when an editor signs off despite failing SOP checks.
    override_reason: str = Field("", max_length=2000)


@router.put("/{google_doc_id}/status")
async def transition_document(
    google_doc_id: str,
    body: TransitionRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Move a document through the production loop (SOP §3)."""
    doc = await _get_doc(session, google_doc_id)
    try:
        previous = workflow.transition(
            doc, body.status, actor=user, reason=body.reason,
            override_reason=body.override_reason,
        )
    except states.TransitionError as exc:
        raise HTTPException(422, str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc

    await session.commit()
    await log_action(
        session, actor=user, action=f"document.{body.status}", target=doc.title,
        meta={"from": previous, "to": body.status,
              "reason": body.reason or None,
              "override_reason": body.override_reason or None},
    )
    await _notify_transition(doc, previous, user)
    return {"ok": True, **_workflow_out(doc)}


@router.get("/{google_doc_id}/workflow")
async def document_workflow(
    google_doc_id: str,
    _: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Current loop state, SLA standing, and what can happen next."""
    doc = await _get_doc(session, google_doc_id)
    return _workflow_out(doc)


class IntegrityPatch(BaseModel):
    """AI/plagiarism percentages from the editor's checker (SOP §4).

    Recorded, never estimated: the SOP names Quillbot, CopyLeaks, SmallSEOTools
    and DupliChecker for this, and a guessed number could wrongly accuse a
    writer in a process that affects their certificate and LOR.
    """

    ai_percent: float = Field(..., ge=0, le=100)
    plagiarism_percent: float = Field(..., ge=0, le=100)


@router.put("/{google_doc_id}/integrity")
async def set_integrity(
    google_doc_id: str,
    body: IntegrityPatch,
    user: User = Depends(require_role(ROLE_EDITOR)),
    session: AsyncSession = Depends(get_session),
) -> dict:
    doc = (
        await session.execute(
            select(Document).where(Document.google_doc_id == google_doc_id)
        )
    ).scalar_one_or_none()
    if doc is None:
        raise HTTPException(404, "Document not tracked yet.")

    doc.ai_percent = body.ai_percent
    doc.plagiarism_percent = body.plagiarism_percent
    doc.integrity_checked_by = user.email
    doc.integrity_checked_at = utcnow()
    await session.commit()

    verdict = integrity_verdict(doc.ai_percent, doc.plagiarism_percent)
    await log_action(
        session, actor=user, action="document.integrity", target=doc.title,
        meta={"ai_percent": doc.ai_percent,
              "plagiarism_percent": doc.plagiarism_percent,
              "passed": verdict["passed"]},
    )
    return {"ok": True, **verdict}
