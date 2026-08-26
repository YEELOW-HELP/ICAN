"""Channel-agnostic Assessment application services (Stage 1). These are
the commands a Telegram adapter calls today and a future Web/API adapter
will call the same way -- nothing here knows about aiogram, Telegram
updates, or chat ids.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models_assessment import Answer, AssessmentStatus, InterviewMessage, InterviewSession
from app.services.assessment import state_machine
from app.services.assessment.completeness import compute_completeness, completeness_summary, minimum_data_satisfied
from app.services.assessment.extraction import AnswerExtractor
from app.services.assessment.next_question import NextQuestionResult, get_next_question, mark_question_answered
from app.services.assessment.question_bank import QUESTIONS_BY_ID
from app.services.events import emit_event
from app.services.exceptions import (
    AssessmentNotFoundError,
    AssessmentOwnershipError,
    InvalidStateTransitionError,
    ProductAccessRequiredError,
    UnfinishedAssessmentExistsError,
)
from app.services.product_access import can_user_start_assessment

_STATES_ACCEPTING_ANSWERS = {AssessmentStatus.DRAFT, AssessmentStatus.ACTIVE, AssessmentStatus.PAUSED}
_UNFINISHED_STATES = (AssessmentStatus.DRAFT, AssessmentStatus.ACTIVE, AssessmentStatus.PAUSED)


async def start_assessment(
    session: AsyncSession, *, user_id: uuid.UUID, plan_code: str, entitlement_id: uuid.UUID | None = None
) -> InterviewSession:
    """Requires an active entitlement for `plan_code` -- callers must have
    already checked `can_user_start_assessment` themselves if they want a
    friendlier pre-check, but this is the authoritative, server-side gate."""
    if not await can_user_start_assessment(session, user_id=user_id, plan_code=plan_code):
        raise ProductAccessRequiredError(f"user {user_id} has no active entitlement for {plan_code}")

    if await get_unfinished_session_for_user(session, user_id) is not None:
        raise UnfinishedAssessmentExistsError(
            f"user {user_id} already has an unfinished assessment session -- resume it instead of starting a new one"
        )

    interview_session = InterviewSession(
        user_id=user_id, entitlement_id=entitlement_id, status=AssessmentStatus.DRAFT, mode="hybrid"
    )
    session.add(interview_session)
    try:
        await session.commit()
    except IntegrityError:
        # Lost a race with a concurrent start_assessment call for the same
        # user (e.g. a double /start) -- the partial unique index
        # (uq_one_unfinished_session_per_user) is the authoritative guard;
        # this pre-check is just a friendlier error path.
        await session.rollback()
        raise UnfinishedAssessmentExistsError(
            f"user {user_id} already has an unfinished assessment session -- resume it instead of starting a new one"
        ) from None
    await session.refresh(interview_session)
    emit_event("assessment_started", user_id=str(user_id), session_id=str(interview_session.id))
    return interview_session


async def get_unfinished_session_for_user(session: AsyncSession, user_id: uuid.UUID) -> InterviewSession | None:
    result = await session.execute(
        select(InterviewSession).where(
            InterviewSession.user_id == user_id, InterviewSession.status.in_(_UNFINISHED_STATES)
        )
    )
    return result.scalar_one_or_none()


async def get_owned_session(session: AsyncSession, *, session_id: uuid.UUID, user_id: uuid.UUID) -> InterviewSession:
    interview_session = await session.get(InterviewSession, session_id)
    if interview_session is None:
        raise AssessmentNotFoundError(f"InterviewSession {session_id} does not exist")
    if interview_session.user_id != user_id:
        raise AssessmentOwnershipError(f"user {user_id} does not own InterviewSession {session_id}")
    return interview_session


async def get_next_question_for_session(
    session: AsyncSession, *, session_id: uuid.UUID, user_id: uuid.UUID
) -> NextQuestionResult:
    await get_owned_session(session, session_id=session_id, user_id=user_id)
    return await get_next_question(session, session_id)


async def submit_answer(
    session: AsyncSession,
    *,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    question_id: str,
    raw_text: str,
    idempotency_key: str,
    source: str,
    extractor: AnswerExtractor | None = None,
) -> Answer:
    """Idempotent regardless of channel: a repeated call with the same
    `idempotency_key` for the same session always returns the same Answer
    row and never re-runs extraction (no duplicate AI call, no duplicate
    event) -- see UNIQUE(session_id, idempotency_key) on the Answer table.
    A PAUSED session is automatically resumed to ACTIVE by a valid new
    answer (Founder decision, Stage 1); a DRAFT session transitions to
    ACTIVE on its first answer."""
    interview_session = await get_owned_session(session, session_id=session_id, user_id=user_id)

    existing = await find_answer_by_idempotency_key(session, session_id, idempotency_key)
    if existing is not None:
        return existing

    if interview_session.status not in _STATES_ACCEPTING_ANSWERS:
        raise InvalidStateTransitionError(
            f"InterviewSession {session_id} in status {interview_session.status.value} cannot accept answers"
        )
    if interview_session.status in (AssessmentStatus.DRAFT, AssessmentStatus.PAUSED):
        state_machine.transition(interview_session, AssessmentStatus.ACTIVE)
    await session.commit()

    # Durably preserve the raw transcript *before* attempting extraction --
    # if the AI Gateway call below fails, the candidate's actual words are
    # never lost, even though no structured Answer will exist for this
    # attempt (Section 14/24: a provider failure must not lose data or
    # move the session to FAILED; it stays ACTIVE for the next attempt).
    await record_message(session, session_id=session_id, role="user", content=raw_text)

    question = QUESTIONS_BY_ID.get(question_id)
    previous = await _latest_answer_for_question(session, session_id, question_id)
    previous_value = previous.extracted_value if previous is not None else None

    if question is not None and question.kind == "structured":
        extracted_value = raw_text
        confidence = 1.0
        contradicts_previous = previous_value is not None and previous_value != raw_text
    else:
        # Deliberately not wrapped in try/except: a provider failure must
        # propagate to the caller (the Telegram adapter shows a graceful
        # error) rather than being swallowed here. The session is already
        # ACTIVE (transitioned above) and stays ACTIVE either way -- no
        # automatic fail_session() call exists on this path, by design.
        result = await (extractor or AnswerExtractor()).extract(
            question_prompt=question_id if question is None else question.question_id,
            raw_answer_text=raw_text,
            previous_value=previous_value,
        )
        extracted_value = result.extracted_value
        confidence = result.confidence
        contradicts_previous = result.contradicts_previous

    answer = Answer(
        session_id=session_id,
        question_id=question_id,
        answer_text=raw_text,
        extracted_value=extracted_value,
        confidence=confidence,
        contradicts_previous=contradicts_previous,
        source=source,
        idempotency_key=idempotency_key,
    )
    session.add(answer)
    try:
        await session.commit()
    except IntegrityError:
        # Lost a race with a concurrent duplicate submission carrying the
        # same idempotency key -- the other request's row won, use it.
        await session.rollback()
        existing = await find_answer_by_idempotency_key(session, session_id, idempotency_key)
        assert existing is not None
        return existing

    await session.refresh(answer)
    await mark_question_answered(session, session_id=session_id, question_id=question_id, answer_id=answer.id)
    emit_event("answer_submitted", user_id=str(user_id), session_id=str(session_id), question_id=question_id)
    return answer


async def record_message(session: AsyncSession, *, session_id: uuid.UUID, role: str, content: str) -> InterviewMessage:
    """Raw transcript -- separate from Answer by design (Section 8).
    Sequence is assigned as max(sequence)+1 for this session; the
    UNIQUE(session_id, sequence) constraint makes a sequencing race
    detectable rather than silently accepted."""
    result = await session.execute(
        select(InterviewMessage.sequence).where(InterviewMessage.session_id == session_id).order_by(InterviewMessage.sequence.desc()).limit(1)
    )
    last_sequence = result.scalar_one_or_none() or 0
    message = InterviewMessage(session_id=session_id, role=role, content=content, sequence=last_sequence + 1)
    session.add(message)
    await session.commit()
    return message


async def pause_assessment(session: AsyncSession, *, session_id: uuid.UUID, user_id: uuid.UUID) -> InterviewSession:
    interview_session = await get_owned_session(session, session_id=session_id, user_id=user_id)
    state_machine.transition(interview_session, AssessmentStatus.PAUSED)
    await session.commit()
    emit_event("assessment_paused", user_id=str(user_id), session_id=str(session_id))
    return interview_session


async def resume_assessment(session: AsyncSession, *, session_id: uuid.UUID, user_id: uuid.UUID) -> InterviewSession:
    """Explicit resume (e.g. a /resume command or a bare "continue"
    message with no new answer content). Submitting a real answer to a
    PAUSED session resumes it automatically via submit_answer -- this
    function is for the case where the user just wants to come back
    without answering anything yet."""
    interview_session = await get_owned_session(session, session_id=session_id, user_id=user_id)
    state_machine.transition(interview_session, AssessmentStatus.ACTIVE)
    await session.commit()
    emit_event("assessment_resumed", user_id=str(user_id), session_id=str(session_id))
    return interview_session


async def fail_session(session: AsyncSession, *, session_id: uuid.UUID, reason: str) -> InterviewSession:
    """Administrative/unrecoverable-error escape hatch. NOT triggered by
    an ordinary AI provider failure (Section 14/Section 24 of the Stage 1
    brief) -- a single failed extraction call leaves the session ACTIVE so
    the candidate's next message gets a fresh attempt. FAILED is terminal
    in Stage 1: no failed -> active transition exists anywhere."""
    interview_session = await session.get(InterviewSession, session_id)
    if interview_session is None:
        raise AssessmentNotFoundError(f"InterviewSession {session_id} does not exist")
    state_machine.transition(interview_session, AssessmentStatus.FAILED, failure_reason=reason)
    await session.commit()
    emit_event("assessment_failed", session_id=str(session_id), reason=reason)
    return interview_session


async def complete_assessment(session: AsyncSession, *, session_id: uuid.UUID, user_id: uuid.UUID) -> InterviewSession:
    """Completion is blocked until the deterministic minimum-data rule
    passes -- never decided by the LLM (Section 13). Stage 1's
    complete -> processing -> ready transition is a synchronous,
    zero-AI-call pass-through: there is no profile to synthesize yet
    (that's Stage 2), so "processing" here only means "finalize the
    completeness snapshot," not a real job."""
    interview_session = await get_owned_session(session, session_id=session_id, user_id=user_id)

    statuses = await compute_completeness(session, session_id)
    if not minimum_data_satisfied(statuses):
        raise InvalidStateTransitionError(
            f"InterviewSession {session_id} does not yet satisfy the minimum-data rule"
        )

    interview_session.completeness = completeness_summary(statuses)
    state_machine.transition(interview_session, AssessmentStatus.COMPLETE)
    await session.commit()

    # Stage 1 placeholder: no real processing job exists yet (Stage 2 owns
    # Human Potential Profile synthesis). Transition through PROCESSING to
    # READY synchronously so the state machine's shape already matches the
    # target architecture from day one.
    state_machine.transition(interview_session, AssessmentStatus.PROCESSING)
    await session.commit()
    state_machine.transition(interview_session, AssessmentStatus.READY)
    await session.commit()

    emit_event("assessment_completed", user_id=str(user_id), session_id=str(session_id))
    return interview_session


async def find_answer_by_idempotency_key(session: AsyncSession, session_id: uuid.UUID, idempotency_key: str) -> Answer | None:
    result = await session.execute(
        select(Answer).where(Answer.session_id == session_id, Answer.idempotency_key == idempotency_key)
    )
    return result.scalar_one_or_none()


async def _latest_answer_for_question(session: AsyncSession, session_id: uuid.UUID, question_id: str) -> Answer | None:
    result = await session.execute(
        select(Answer)
        .where(Answer.session_id == session_id, Answer.question_id == question_id)
        .order_by(Answer.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()
