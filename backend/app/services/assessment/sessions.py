"""Channel-agnostic Assessment application services (Stage 1). These are
the commands a Telegram adapter calls today and a future Web/API adapter
will call the same way -- nothing here knows about aiogram, Telegram
updates, or chat ids.
"""

from __future__ import annotations

import asyncio
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
from app.services.product_access import get_any_active_entitlement, get_entitlement_by_id

_STATES_ACCEPTING_ANSWERS = {AssessmentStatus.DRAFT, AssessmentStatus.ACTIVE, AssessmentStatus.PAUSED}
_UNFINISHED_STATES = (AssessmentStatus.DRAFT, AssessmentStatus.ACTIVE, AssessmentStatus.PAUSED)

# Bounds how long a concurrent duplicate submission waits for the request
# that won the idempotency reservation (see submit_answer) to finish
# extraction -- not a business value, an internal engineering timeout.
_PENDING_ANSWER_POLL_INTERVAL_SECONDS = 0.05
_PENDING_ANSWER_POLL_MAX_ATTEMPTS = 40


async def start_assessment(
    session: AsyncSession, *, user_id: uuid.UUID, plan_code: str, entitlement_id: uuid.UUID | None = None
) -> InterviewSession:
    """Resolves and persists the *concrete* entitlement backing this
    assessment -- `InterviewSession.entitlement_id` is never left NULL
    when a real entitlement exists (Founder hardening review, item 2).

    If the caller already knows which entitlement to use (`entitlement_id`
    given), it is validated server-side rather than trusted: it must
    belong to `user_id`, be unrevoked, and match `plan_code`. Otherwise
    the most recently granted active entitlement for `plan_code` is
    resolved here -- this function, not the caller, is the single source
    of truth for "which entitlement did this assessment actually run
    under.\""""
    if entitlement_id is not None:
        entitlement = await get_entitlement_by_id(session, entitlement_id)
        if entitlement is None or entitlement.user_id != user_id:
            raise ProductAccessRequiredError(f"entitlement {entitlement_id} does not belong to user {user_id}")
        if entitlement.revoked_at is not None:
            raise ProductAccessRequiredError(f"entitlement {entitlement_id} has been revoked")
        if entitlement.plan_code != plan_code:
            raise ProductAccessRequiredError(
                f"entitlement {entitlement_id} is for plan {entitlement.plan_code}, not {plan_code}"
            )
    else:
        entitlement = await get_any_active_entitlement(session, user_id=user_id, plan_code=plan_code)
        if entitlement is None:
            raise ProductAccessRequiredError(f"user {user_id} has no active entitlement for {plan_code}")

    if await get_unfinished_session_for_user(session, user_id) is not None:
        raise UnfinishedAssessmentExistsError(
            f"user {user_id} already has an unfinished assessment session -- resume it instead of starting a new one"
        )

    interview_session = InterviewSession(
        user_id=user_id, entitlement_id=entitlement.id, status=AssessmentStatus.DRAFT, mode="hybrid"
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
    event). A PAUSED session is automatically resumed to ACTIVE by a
    valid new answer (Founder decision, Stage 1); a DRAFT session
    transitions to ACTIVE on its first answer.

    Concurrency (Founder hardening review, item 1): two concurrent calls
    with the same idempotency_key must result in exactly one AI Gateway
    call, not one-per-caller-that-loses-later. This is enforced by
    inserting a *reservation* -- an Answer row with extracted_value=None --
    under UNIQUE(session_id, idempotency_key) BEFORE calling the AI
    Gateway, not by catching the unique-constraint conflict after the
    call already happened. The loser of that insert never reaches the AI
    Gateway at all; it waits for the winner's row to resolve and returns
    that (see _await_pending_answer)."""
    interview_session = await get_owned_session(session, session_id=session_id, user_id=user_id)

    existing = await find_answer_by_idempotency_key(session, session_id, idempotency_key)
    if existing is not None:
        if existing.extracted_value is not None:
            return existing
        return await _await_pending_answer(session, session_id, idempotency_key)

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
    # Resolved *before* the reservation below is inserted -- otherwise the
    # reservation (extracted_value=None) could be picked up as its own
    # "previous answer" and corrupt contradiction detection.
    previous = await _latest_answer_for_question(session, session_id, question_id)
    previous_value = previous.extracted_value if previous is not None else None

    reservation = Answer(
        session_id=session_id,
        question_id=question_id,
        answer_text=raw_text,
        extracted_value=None,
        confidence=None,
        contradicts_previous=False,
        source=source,
        idempotency_key=idempotency_key,
    )
    session.add(reservation)
    try:
        await session.commit()
    except IntegrityError:
        # Lost the reservation race to a concurrent duplicate submission
        # carrying the same idempotency key -- crucially, *before* any AI
        # Gateway call was made on this path. Wait for the winner instead.
        await session.rollback()
        return await _await_pending_answer(session, session_id, idempotency_key)
    await session.refresh(reservation)

    if question is not None and question.kind == "structured":
        extracted_value = raw_text
        confidence = 1.0
        contradicts_previous = previous_value is not None and previous_value != raw_text
    else:
        try:
            # Deliberately not wrapped to swallow the error: a provider
            # failure must propagate to the caller (the Telegram adapter
            # shows a graceful error) rather than being hidden here. The
            # session is already ACTIVE (transitioned above) and stays
            # ACTIVE either way -- no automatic fail_session() call exists
            # on this path, by design. The reservation itself IS deleted
            # on failure so a genuine retry (new attempt, possibly the
            # same idempotency_key) is not permanently blocked by a
            # half-written row with no value.
            result = await (extractor or AnswerExtractor()).extract(
                question_prompt=question_id if question is None else question.question_id,
                raw_answer_text=raw_text,
                previous_value=previous_value,
            )
        except Exception:
            await session.delete(reservation)
            await session.commit()
            raise
        extracted_value = result.extracted_value
        confidence = result.confidence
        contradicts_previous = result.contradicts_previous

    reservation.extracted_value = extracted_value
    reservation.confidence = confidence
    reservation.contradicts_previous = contradicts_previous
    await session.commit()
    await session.refresh(reservation)

    await mark_question_answered(session, session_id=session_id, question_id=question_id, answer_id=reservation.id)
    emit_event("answer_submitted", user_id=str(user_id), session_id=str(session_id), question_id=question_id)
    return reservation


async def _await_pending_answer(session: AsyncSession, session_id: uuid.UUID, idempotency_key: str) -> Answer:
    """Waits for a concurrent submit_answer call that won the idempotency
    reservation to finish extraction, without ever calling the AI Gateway
    itself. Bounded: if the winner never resolves it (e.g. it crashed
    between reserving and either finishing or cleaning up -- an
    out-of-process failure this deterministic single-process design
    cannot observe), the still-pending row is returned rather than
    hanging forever; a subsequent genuine retry with the same
    idempotency_key from the caller is expected to make progress."""
    for _ in range(_PENDING_ANSWER_POLL_MAX_ATTEMPTS):
        existing = await find_answer_by_idempotency_key(session, session_id, idempotency_key)
        if existing is not None and existing.extracted_value is not None:
            return existing
        await _poll_delay()
    existing = await find_answer_by_idempotency_key(session, session_id, idempotency_key)
    assert existing is not None, "reservation row disappeared without resolving"
    return existing


async def _poll_delay() -> None:
    """Isolated seam for _await_pending_answer's wait -- tests patch this
    instead of the global asyncio.sleep, so a deterministic race
    simulation never risks affecting unrelated concurrent timers."""
    await asyncio.sleep(_PENDING_ANSWER_POLL_INTERVAL_SECONDS)


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
    passes -- never decided by the LLM (Section 13).

    Stage 1 owns data collection only and stops at COMPLETE (Founder
    hardening review, item 5). COMPLETE -> PROCESSING -> READY belongs to
    Stage 2, which will actually synthesize the Human Potential
    Profile/Evidence Graph before advancing past COMPLETE -- Stage 1 must
    not synchronously fast-forward through states whose real work doesn't
    exist yet, since that would misrepresent "ready" as meaning something
    it doesn't."""
    interview_session = await get_owned_session(session, session_id=session_id, user_id=user_id)

    statuses = await compute_completeness(session, session_id)
    if not minimum_data_satisfied(statuses):
        raise InvalidStateTransitionError(
            f"InterviewSession {session_id} does not yet satisfy the minimum-data rule"
        )

    interview_session.completeness = completeness_summary(statuses)
    state_machine.transition(interview_session, AssessmentStatus.COMPLETE)
    await session.commit()

    emit_event("assessment_completed", user_id=str(user_id), session_id=str(session_id))
    return interview_session


async def find_answer_by_idempotency_key(session: AsyncSession, session_id: uuid.UUID, idempotency_key: str) -> Answer | None:
    result = await session.execute(
        select(Answer).where(Answer.session_id == session_id, Answer.idempotency_key == idempotency_key)
    )
    return result.scalar_one_or_none()


async def recover_stale_pending_answers(session: AsyncSession, session_id: uuid.UUID) -> int:
    """Stage 2 hardening (Founder review item 25): a process crash between
    submit_answer's reservation insert and either its success-update or
    its failure-cleanup can theoretically leave a permanently pending
    Answer row (extracted_value IS NULL) if the crash happens in that
    narrow window. Such a row is never lost data -- the candidate's raw
    text survives independently in InterviewMessage -- so it is always
    safe to discard once it is older than
    settings.pending_answer_stale_after_seconds; a genuine in-flight
    reservation is never anywhere near that old (see
    _PENDING_ANSWER_POLL_MAX_ATTEMPTS x _PENDING_ANSWER_POLL_INTERVAL_SECONDS
    for how briefly a real concurrent submission actually waits).

    Callers (Stage 2's profile generation, in particular) MUST call this
    before reading a session's Answer rows as evidence -- a stale pending
    row must never be silently treated as "no answer" forever, nor ever
    be treated as a real answer. Returns the number of rows removed."""
    cutoff = datetime.now(timezone.utc).timestamp() - settings.pending_answer_stale_after_seconds
    cutoff_dt = datetime.fromtimestamp(cutoff, tz=timezone.utc)
    result = await session.execute(
        select(Answer).where(
            Answer.session_id == session_id, Answer.extracted_value.is_(None), Answer.created_at < cutoff_dt
        )
    )
    stale = result.scalars().all()
    for row in stale:
        await session.delete(row)
    if stale:
        await session.commit()
    return len(stale)


async def _latest_answer_for_question(session: AsyncSession, session_id: uuid.UUID, question_id: str) -> Answer | None:
    """Excludes still-pending reservations (extracted_value IS NULL) --
    a concurrent in-flight submission to the same question must not be
    mistaken for the "previous value" used in contradiction detection."""
    result = await session.execute(
        select(Answer)
        .where(
            Answer.session_id == session_id,
            Answer.question_id == question_id,
            Answer.extracted_value.isnot(None),
        )
        .order_by(Answer.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()
