"""Production-loop state machine (SOP §3)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.workflow import states as S


def _now():
    return datetime(2026, 9, 17, 9, 0, tzinfo=timezone.utc)


# --- the happy path ----------------------------------------------------------

def test_full_loop_is_walkable():
    path = [
        S.ASSIGNED, S.DRAFTING, S.SUBMITTED, S.UNDER_REVIEW,
        S.REVISING, S.APPROVED, S.PUBLISHED,
    ]
    for frm, to in zip(path, path[1:]):
        S.validate(frm, to)   # must not raise


def test_both_submission_entry_points_are_legal():
    """The author submits, or the editor picks the draft up directly."""
    S.validate(S.DRAFTING, S.SUBMITTED)
    S.validate(S.DRAFTING, S.UNDER_REVIEW)


def test_revision_loop_can_repeat():
    """An editor may send a piece back more than once."""
    S.validate(S.UNDER_REVIEW, S.REVISING)
    S.validate(S.REVISING, S.SUBMITTED)
    S.validate(S.SUBMITTED, S.UNDER_REVIEW)
    S.validate(S.UNDER_REVIEW, S.REVISING)


def test_approved_can_be_reopened():
    """Something spotted after sign-off must be fixable."""
    S.validate(S.APPROVED, S.REVISING)


# --- illegal moves -----------------------------------------------------------

def test_cannot_skip_review():
    with pytest.raises(S.TransitionError, match="Cannot move"):
        S.validate(S.ASSIGNED, S.APPROVED)


def test_cannot_leave_a_terminal_state():
    for terminal in (S.PUBLISHED, S.SCRAPPED):
        with pytest.raises(S.TransitionError):
            S.validate(terminal, S.DRAFTING)


def test_cannot_transition_to_itself():
    with pytest.raises(S.TransitionError, match="already"):
        S.validate(S.DRAFTING, S.DRAFTING)


def test_unknown_state_rejected():
    with pytest.raises(S.TransitionError, match="Unknown status"):
        S.validate(S.DRAFTING, "banana")


def test_error_message_lists_what_is_allowed():
    with pytest.raises(S.TransitionError) as exc:
        S.validate(S.ASSIGNED, S.PUBLISHED)
    assert "drafting" in str(exc.value)


# --- escalation --------------------------------------------------------------

def test_escalation_requires_a_reason():
    for target in (S.REASSIGNED, S.SCRAPPED):
        with pytest.raises(S.TransitionError, match="reason is required"):
            S.validate(S.UNDER_REVIEW, target)
        S.validate(S.UNDER_REVIEW, target, reason="Fails factual standards.")


def test_blank_reason_is_not_a_reason():
    with pytest.raises(S.TransitionError):
        S.validate(S.UNDER_REVIEW, S.SCRAPPED, reason="   ")


def test_escalation_is_possible_from_every_active_state():
    for frm in (S.ASSIGNED, S.DRAFTING, S.SUBMITTED, S.UNDER_REVIEW, S.REVISING):
        S.validate(frm, S.SCRAPPED, reason="x")
        S.validate(frm, S.REASSIGNED, reason="x")


def test_reassigned_work_can_restart():
    S.validate(S.REASSIGNED, S.ASSIGNED)


# --- permissions -------------------------------------------------------------

def test_author_states_are_not_editor_only():
    for state in (S.DRAFTING, S.SUBMITTED):
        assert not S.requires_editor(state), state


def test_editor_gated_states():
    for state in (S.UNDER_REVIEW, S.REVISING, S.APPROVED, S.PUBLISHED,
                  S.REASSIGNED, S.SCRAPPED):
        assert S.requires_editor(state), state


# --- SLA windows -------------------------------------------------------------

def test_drafting_deadline_uses_the_sop_window():
    start = _now()
    assert S.deadline_for(S.DRAFTING, start) == start + timedelta(hours=18)
    assert S.deadline_for(S.DRAFTING, start, limit=False) == start + timedelta(hours=12)


def test_editing_deadline_uses_the_sop_window():
    start = _now()
    assert S.deadline_for(S.UNDER_REVIEW, start) == start + timedelta(hours=12)
    assert S.deadline_for(S.UNDER_REVIEW, start, limit=False) == start + timedelta(hours=10)


def test_revising_runs_on_the_drafting_clock():
    """The ball is back with the author, so it is author time."""
    assert S.phase_of(S.REVISING) == "drafting"


def test_terminal_states_have_no_clock():
    for state in (S.APPROVED, S.PUBLISHED, S.SCRAPPED, S.REASSIGNED):
        assert S.deadline_for(state, _now()) is None
        assert S.phase_of(state) is None


def test_deadline_without_a_start_is_none():
    assert S.deadline_for(S.DRAFTING, None) is None


def test_sop_windows_match_the_document():
    assert (S.DRAFTING_HOURS_TARGET, S.DRAFTING_HOURS_LIMIT) == (12, 18)
    assert (S.EDITING_HOURS_TARGET, S.EDITING_HOURS_LIMIT) == (10, 12)


# --- legacy rows -------------------------------------------------------------

def test_legacy_statuses_can_join_the_flow():
    """Documents predating the state machine must not be stranded."""
    S.validate(S.LEGACY_DRAFT, S.SUBMITTED)
    S.validate(S.LEGACY_FINALIZED, S.APPROVED)
