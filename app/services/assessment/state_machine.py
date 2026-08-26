"""The Assessment state machine (Stage 1 -- Issue #1). This module is the
*only* code allowed to change `InterviewSession.status` -- Telegram
handlers, a future API layer, and every other service function all go
through `transition()` rather than assigning `.status` directly. Business
guards (e.g. "minimum-data rule must pass before complete") live in the
caller (app/services/assessment/sessions.py), not here -- this module only
knows the shape of the state graph, nothing about assessment content.

Canonical states and transitions (Founder-approved):

    draft -> active | failed
    active -> paused | complete | failed
    paused -> active | failed
    complete -> processing                  (automatic, system-triggered)
    processing -> ready | failed
    ready -> (terminal)
    failed -> (terminal; recovery creates a new session, never failed -> active)
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.db.models_assessment import AssessmentStatus, InterviewSession
from app.services.exceptions import InvalidStateTransitionError

ALLOWED_TRANSITIONS: dict[AssessmentStatus, frozenset[AssessmentStatus]] = {
    AssessmentStatus.DRAFT: frozenset({AssessmentStatus.ACTIVE, AssessmentStatus.FAILED}),
    AssessmentStatus.ACTIVE: frozenset({AssessmentStatus.PAUSED, AssessmentStatus.COMPLETE, AssessmentStatus.FAILED}),
    AssessmentStatus.PAUSED: frozenset({AssessmentStatus.ACTIVE, AssessmentStatus.FAILED}),
    AssessmentStatus.COMPLETE: frozenset({AssessmentStatus.PROCESSING}),
    AssessmentStatus.PROCESSING: frozenset({AssessmentStatus.READY, AssessmentStatus.FAILED}),
    AssessmentStatus.READY: frozenset(),
    AssessmentStatus.FAILED: frozenset(),
}


def can_transition(current: AssessmentStatus, to: AssessmentStatus) -> bool:
    return to in ALLOWED_TRANSITIONS[current]


def transition(session_row: InterviewSession, to: AssessmentStatus, *, failure_reason: str | None = None) -> None:
    """Mutates `session_row` in place. Does not commit -- callers control
    the transaction boundary (usually alongside writing the Answer/event
    that triggered the transition)."""
    current = session_row.status
    if not can_transition(current, to):
        raise InvalidStateTransitionError(f"cannot transition InterviewSession from {current.value} to {to.value}")

    session_row.status = to
    now = datetime.now(timezone.utc)
    if to == AssessmentStatus.COMPLETE:
        session_row.completed_at = now
    if to == AssessmentStatus.FAILED:
        session_row.failed_at = now
        session_row.failure_reason = failure_reason
