"""Production-loop operations: assign, transition, sign off, escalate.

Holds the rules that need the database or the clock. The pure state graph lives
in `states.py`; this module applies it to a Document and keeps the phase clocks
honest.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

from app.auth.service import has_role
from app.db.models import ROLE_EDITOR, Document, User
from app.scoring.constitution import integrity_verdict
from app.util import utcnow
from app.workflow import states as S


@dataclass
class SlaStatus:
    """Where the current phase stands against the SOP window."""

    phase: Optional[str] = None            # drafting | editing | None
    started_at: Optional[datetime] = None
    target_at: Optional[datetime] = None   # 12h drafting / 10h editing
    due_at: Optional[datetime] = None      # 18h drafting / 12h editing
    hours_remaining: Optional[float] = None
    overdue: bool = False
    at_risk: bool = False                  # past target, inside the limit


def _aware(value: Optional[datetime]) -> Optional[datetime]:
    """SQLite hands back naive datetimes; compare in UTC either way."""
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def sla_for(doc: Document, *, now: Optional[datetime] = None) -> SlaStatus:
    now = now or utcnow()
    phase = S.phase_of(doc.status)
    if phase is None:
        return SlaStatus()

    started = _aware(doc.phase_started_at) or _aware(doc.updated_at)
    if started is None:
        return SlaStatus(phase=phase)

    due = S.deadline_for(doc.status, started)
    target = S.deadline_for(doc.status, started, limit=False)
    remaining = (due - now).total_seconds() / 3600 if due else None
    return SlaStatus(
        phase=phase, started_at=started, target_at=target, due_at=due,
        hours_remaining=round(remaining, 1) if remaining is not None else None,
        overdue=bool(due and now > due),
        at_risk=bool(target and due and target < now <= due),
    )


def blocking_reasons(doc: Document, sop_failures: Optional[List[str]] = None) -> List[str]:
    """Why this document is not cleanly approvable.

    Advisory only: the SOP gives the editor final say, so approval is never
    blocked outright — but an editor who signs off anyway must record why.
    """
    reasons: List[str] = []
    verdict = integrity_verdict(doc.ai_percent, doc.plagiarism_percent)
    if not verdict["checked"]:
        reasons.append(
            "AI and plagiarism checks have not been recorded (SOP §4)."
        )
    else:
        reasons.extend(verdict["breaches"])
    reasons.extend(sop_failures or [])
    return reasons


def assign(
    doc: Document,
    *,
    assigned_to: str,
    assigned_by: str,
    editor: str = "",
    word_min: Optional[int] = None,
    word_max: Optional[int] = None,
    now: Optional[datetime] = None,
) -> None:
    """Issue the assignment brief and start the drafting clock."""
    now = now or utcnow()
    doc.assigned_to = assigned_to
    doc.assigned_by = assigned_by
    if editor:
        doc.editor = editor
    doc.word_min = word_min
    doc.word_max = word_max
    doc.status = S.ASSIGNED
    doc.assigned_at = now
    doc.phase_started_at = now
    # A re-assignment starts a fresh loop.
    doc.submitted_at = None
    doc.approved_at = None
    doc.approved_by = ""
    doc.override_reason = ""
    doc.escalation_reason = ""


def transition(
    doc: Document,
    to: str,
    *,
    actor: User,
    reason: str = "",
    override_reason: str = "",
    now: Optional[datetime] = None,
) -> str:
    """Move `doc` to `to`, enforcing the state graph and role rules.

    Returns the previous status. Raises TransitionError / PermissionError.
    """
    now = now or utcnow()
    frm = doc.status or S.LEGACY_DRAFT

    S.validate(frm, to, reason=reason)
    if S.requires_editor(to) and not has_role(actor, ROLE_EDITOR):
        raise PermissionError(
            f"Only an editor can move a document to {to!r}."
        )

    doc.status = to

    # Phase clocks reset when the PHASE changes, not on every transition.
    #
    # `submitted` and `under_review` are both editing states, and `assigned`,
    # `drafting` and `revising` are all drafting states. Resetting on any
    # transition meant an editor merely opening a document for review silently
    # granted a fresh 12 hours — so a piece could sit for days and never report
    # overdue, and the SOP's 24-30 hour loop was not actually being tracked.
    if S.phase_of(to) is not None and S.phase_of(to) != S.phase_of(frm):
        doc.phase_started_at = now
    if to == S.SUBMITTED:
        doc.submitted_at = now
    if to == S.APPROVED:
        doc.approved_at = now
        doc.approved_by = actor.email
        # Recorded, not blocked: the editor keeps final say, and the exception
        # is visible to the team lead afterwards.
        doc.override_reason = override_reason.strip()
    if to in S.REASON_REQUIRED:
        doc.escalation_reason = reason.strip()
    return frm
