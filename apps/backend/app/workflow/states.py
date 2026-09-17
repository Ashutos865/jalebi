"""TIES production loop — states, transitions and SLA windows (SOP §3).

The SOP runs a 24-to-30-hour loop for standard short-form articles:

    Phase 1  Drafting                     12-18 hours
    Phase 2  Editing / revision / sign-off 10-12 hours

Modelled as an explicit state machine rather than a free-text status field so
that an article cannot jump from `assigned` straight to `approved`, and so the
clock for each phase has a defined start.

Deliberately *not* modelled: the group-chat ritual. The SOP's handoff is a chat
tag and a "GTG!" message, and those stay human. Jalebi records the same events
so the team has an auditable trail and overdue work becomes visible.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Dict, FrozenSet, List, Optional

# ── States ────────────────────────────────────────────────────────────────────
ASSIGNED = "assigned"          # brief issued, drafting clock running
DRAFTING = "drafting"          # author has started
SUBMITTED = "submitted"        # author handed off; editing clock running
UNDER_REVIEW = "under_review"  # editor has picked it up
REVISING = "revising"          # editor returned comments; author addressing them
APPROVED = "approved"          # editor signed off ("GTG!")
PUBLISHED = "published"        # live
REASSIGNED = "reassigned"      # editor escalated: another author takes it
SCRAPPED = "scrapped"          # editor escalated: dropped

# Legacy free-text statuses that predate this state machine. Kept so existing
# Document rows and the tracker UI keep working.
LEGACY_DRAFT = "draft"
LEGACY_FINALIZED = "finalized"

ALL_STATES: FrozenSet[str] = frozenset({
    ASSIGNED, DRAFTING, SUBMITTED, UNDER_REVIEW, REVISING, APPROVED,
    PUBLISHED, REASSIGNED, SCRAPPED, LEGACY_DRAFT, LEGACY_FINALIZED,
})

TERMINAL_STATES: FrozenSet[str] = frozenset({PUBLISHED, REASSIGNED, SCRAPPED})

# ── Transitions ───────────────────────────────────────────────────────────────
# state -> states reachable from it.
TRANSITIONS: Dict[str, FrozenSet[str]] = {
    ASSIGNED: frozenset({DRAFTING, SUBMITTED, REASSIGNED, SCRAPPED}),
    # Both entry points into review: the author submits, or the editor picks it
    # up directly (teams do not all adopt the same habit).
    DRAFTING: frozenset({SUBMITTED, UNDER_REVIEW, REASSIGNED, SCRAPPED}),
    SUBMITTED: frozenset({UNDER_REVIEW, REVISING, APPROVED, REASSIGNED, SCRAPPED}),
    UNDER_REVIEW: frozenset({REVISING, APPROVED, REASSIGNED, SCRAPPED}),
    # The loop: an editor can send a piece back more than once.
    REVISING: frozenset({SUBMITTED, UNDER_REVIEW, APPROVED, REASSIGNED, SCRAPPED}),
    APPROVED: frozenset({PUBLISHED, REVISING}),   # reopen if something is spotted
    PUBLISHED: frozenset(),
    REASSIGNED: frozenset({ASSIGNED}),            # picked up by a new author
    SCRAPPED: frozenset(),
    # Legacy rows can join the modelled flow.
    LEGACY_DRAFT: frozenset({ASSIGNED, DRAFTING, SUBMITTED, UNDER_REVIEW, SCRAPPED}),
    LEGACY_FINALIZED: frozenset({APPROVED, PUBLISHED, REVISING}),
}

# Transitions only an editor (or above) may make. Authors draft and submit;
# everything downstream is the editor's call, per SOP §4.
EDITOR_ONLY: FrozenSet[str] = frozenset({
    UNDER_REVIEW, REVISING, APPROVED, PUBLISHED, REASSIGNED, SCRAPPED,
})

# Escalation requires a written reason so the team lead can see why.
REASON_REQUIRED: FrozenSet[str] = frozenset({REASSIGNED, SCRAPPED})

# ── SLA windows (SOP §3) ──────────────────────────────────────────────────────
DRAFTING_HOURS_TARGET = 12
DRAFTING_HOURS_LIMIT = 18
EDITING_HOURS_TARGET = 10
EDITING_HOURS_LIMIT = 12

# Which clock each state is running against.
DRAFTING_STATES: FrozenSet[str] = frozenset({ASSIGNED, DRAFTING, REVISING})
EDITING_STATES: FrozenSet[str] = frozenset({SUBMITTED, UNDER_REVIEW})


class TransitionError(ValueError):
    """An illegal state change."""


@dataclass
class Transition:
    frm: str
    to: str
    reason: str = ""


def is_known(state: str) -> bool:
    return state in ALL_STATES


def can_transition(frm: str, to: str) -> bool:
    return to in TRANSITIONS.get(frm, frozenset())


def next_states(frm: str) -> List[str]:
    return sorted(TRANSITIONS.get(frm, frozenset()))


def requires_editor(to: str) -> bool:
    return to in EDITOR_ONLY


def requires_reason(to: str) -> bool:
    return to in REASON_REQUIRED


def validate(frm: str, to: str, *, reason: str = "") -> None:
    """Raise TransitionError unless `frm -> to` is legal and complete."""
    if not is_known(to):
        raise TransitionError(f"Unknown status {to!r}.")
    if frm == to:
        raise TransitionError(f"Document is already {to!r}.")
    if not can_transition(frm, to):
        allowed = ", ".join(next_states(frm)) or "nothing (terminal state)"
        raise TransitionError(
            f"Cannot move from {frm!r} to {to!r}. Allowed from {frm!r}: {allowed}."
        )
    if requires_reason(to) and not reason.strip():
        raise TransitionError(f"A reason is required to mark a document {to!r}.")


def deadline_for(state: str, since, *, limit: bool = True):
    """When the current phase is due, or None if this state has no clock.

    `since` is the timestamp the phase started. `limit=True` uses the SOP's
    outer bound (18h drafting / 12h editing); False uses the target.
    """
    if since is None:
        return None
    if state in DRAFTING_STATES:
        hours = DRAFTING_HOURS_LIMIT if limit else DRAFTING_HOURS_TARGET
    elif state in EDITING_STATES:
        hours = EDITING_HOURS_LIMIT if limit else EDITING_HOURS_TARGET
    else:
        return None
    return since + timedelta(hours=hours)


def phase_of(state: str) -> Optional[str]:
    if state in DRAFTING_STATES:
        return "drafting"
    if state in EDITING_STATES:
        return "editing"
    return None
