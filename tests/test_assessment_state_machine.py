import pytest

from app.db.models_assessment import AssessmentStatus, InterviewSession
from app.db.models_identity import IdentityUser
from app.services.assessment import state_machine
from app.services.exceptions import InvalidStateTransitionError


async def _make_session(session, status=AssessmentStatus.DRAFT) -> InterviewSession:
    user = IdentityUser()
    session.add(user)
    await session.flush()
    interview_session = InterviewSession(user_id=user.id, status=status)
    session.add(interview_session)
    await session.commit()
    await session.refresh(interview_session)
    return interview_session


@pytest.mark.parametrize(
    "current,to",
    [
        (AssessmentStatus.DRAFT, AssessmentStatus.ACTIVE),
        (AssessmentStatus.DRAFT, AssessmentStatus.FAILED),
        (AssessmentStatus.ACTIVE, AssessmentStatus.PAUSED),
        (AssessmentStatus.ACTIVE, AssessmentStatus.COMPLETE),
        (AssessmentStatus.ACTIVE, AssessmentStatus.FAILED),
        (AssessmentStatus.PAUSED, AssessmentStatus.ACTIVE),
        (AssessmentStatus.PAUSED, AssessmentStatus.FAILED),
        (AssessmentStatus.COMPLETE, AssessmentStatus.PROCESSING),
        (AssessmentStatus.PROCESSING, AssessmentStatus.READY),
        (AssessmentStatus.PROCESSING, AssessmentStatus.FAILED),
    ],
)
async def test_valid_transitions_succeed(session, current, to):
    interview_session = await _make_session(session, status=current)
    state_machine.transition(interview_session, to)
    assert interview_session.status == to


@pytest.mark.parametrize(
    "current,to",
    [
        (AssessmentStatus.DRAFT, AssessmentStatus.PAUSED),
        (AssessmentStatus.DRAFT, AssessmentStatus.COMPLETE),
        (AssessmentStatus.DRAFT, AssessmentStatus.READY),
        (AssessmentStatus.ACTIVE, AssessmentStatus.DRAFT),
        (AssessmentStatus.ACTIVE, AssessmentStatus.READY),
        (AssessmentStatus.ACTIVE, AssessmentStatus.PROCESSING),
        (AssessmentStatus.PAUSED, AssessmentStatus.COMPLETE),
        (AssessmentStatus.PAUSED, AssessmentStatus.PROCESSING),
        (AssessmentStatus.COMPLETE, AssessmentStatus.ACTIVE),
        (AssessmentStatus.COMPLETE, AssessmentStatus.READY),
        (AssessmentStatus.PROCESSING, AssessmentStatus.ACTIVE),
        (AssessmentStatus.PROCESSING, AssessmentStatus.COMPLETE),
        (AssessmentStatus.READY, AssessmentStatus.ACTIVE),
        (AssessmentStatus.READY, AssessmentStatus.PROCESSING),
        (AssessmentStatus.FAILED, AssessmentStatus.ACTIVE),
        (AssessmentStatus.FAILED, AssessmentStatus.DRAFT),
        (AssessmentStatus.FAILED, AssessmentStatus.READY),
    ],
)
async def test_invalid_transitions_are_rejected(session, current, to):
    interview_session = await _make_session(session, status=current)
    with pytest.raises(InvalidStateTransitionError):
        state_machine.transition(interview_session, to)
    assert interview_session.status == current  # rejected transition never mutates state


async def test_failed_is_terminal_no_outgoing_transition_exists():
    for candidate in AssessmentStatus:
        assert not state_machine.can_transition(AssessmentStatus.FAILED, candidate)


async def test_ready_is_terminal_within_stage_1_scope():
    for candidate in AssessmentStatus:
        assert not state_machine.can_transition(AssessmentStatus.READY, candidate)


async def test_complete_sets_completed_at_timestamp(session):
    interview_session = await _make_session(session, status=AssessmentStatus.ACTIVE)
    assert interview_session.completed_at is None
    state_machine.transition(interview_session, AssessmentStatus.COMPLETE)
    assert interview_session.completed_at is not None


async def test_failed_sets_failed_at_and_failure_reason(session):
    interview_session = await _make_session(session, status=AssessmentStatus.ACTIVE)
    state_machine.transition(interview_session, AssessmentStatus.FAILED, failure_reason="unrecoverable data error")
    assert interview_session.failed_at is not None
    assert interview_session.failure_reason == "unrecoverable data error"
