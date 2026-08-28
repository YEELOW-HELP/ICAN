"""BASIC assessment attempt lifecycle (Matching V1 M1): NOT_STARTED ->
IN_PROGRESS -> COMPLETED. `CALCULATED` is a reserved future state (M2's
deterministic profile engine) -- no function here can reach it.

Zero-AI: this module does not import `app.ai_gateway` or any PRO Hybrid
extraction/synthesis service. See `tests/test_basic_assessment_zero_ai.py`.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_basic_assessment import (
    AssessmentDefinition,
    AssessmentItem,
    AssessmentItemOption,
    AttemptStatus,
    BasicAssessmentAnswer,
    BasicAssessmentAttempt,
)
from app.services.basic_assessment.validation import validate_response
from app.services.exceptions import BasicAttemptClosedError

OPEN_STATUSES = (AttemptStatus.NOT_STARTED, AttemptStatus.IN_PROGRESS)
CLOSED_STATUSES = (AttemptStatus.COMPLETED, AttemptStatus.CALCULATED)


async def get_or_create_active_attempt(
    session: AsyncSession, *, user_id: uuid.UUID, definition: AssessmentDefinition
) -> BasicAssessmentAttempt:
    """Idempotent: returns the user's existing NOT_STARTED/IN_PROGRESS
    attempt for this definition if one exists (resume), otherwise creates
    a fresh NOT_STARTED attempt. A genuinely new attempt ("Пройти тест
    заново") is only possible once the current one reaches COMPLETED/
    CALCULATED -- enforced by the DB partial-unique index
    `uq_one_open_basic_attempt_per_user`, not just this function."""

    existing = await session.execute(
        select(BasicAssessmentAttempt).where(
            BasicAssessmentAttempt.user_id == user_id,
            BasicAssessmentAttempt.definition_id == definition.id,
            BasicAssessmentAttempt.status.in_(OPEN_STATUSES),
        )
    )
    attempt = existing.scalar_one_or_none()
    if attempt is not None:
        return attempt

    attempt = BasicAssessmentAttempt(user_id=user_id, definition_id=definition.id, status=AttemptStatus.NOT_STARTED)
    session.add(attempt)
    await session.flush()
    return attempt


async def submit_answer(
    session: AsyncSession,
    *,
    attempt: BasicAssessmentAttempt,
    item: AssessmentItem,
    idempotency_key: str,
    numeric_value: int | None = None,
    boolean_value: bool | None = None,
    selected_option_keys: list[str] | None = None,
) -> BasicAssessmentAnswer:
    """Validates the payload against `item`, persists a new (never
    updated) `BasicAssessmentAnswer` row, and transitions
    NOT_STARTED -> IN_PROGRESS on the attempt's first answer. Rejects any
    submission against a COMPLETED/CALCULATED attempt outright -- a
    completed attempt is never silently editable."""

    if attempt.status in CLOSED_STATUSES:
        raise BasicAttemptClosedError(f"attempt {attempt.id} is {attempt.status.value}, cannot accept new answers")

    options: list[AssessmentItemOption] = []
    if selected_option_keys is not None:
        result = await session.execute(select(AssessmentItemOption).where(AssessmentItemOption.item_id == item.id))
        options = list(result.scalars().all())

    validate_response(
        item,
        numeric_value=numeric_value,
        boolean_value=boolean_value,
        selected_option_keys=selected_option_keys,
        options=options,
    )

    answer = BasicAssessmentAnswer(
        attempt_id=attempt.id,
        item_id=item.id,
        response_type=item.response_type,
        numeric_value=numeric_value,
        boolean_value=boolean_value,
        selected_option_keys=selected_option_keys,
        idempotency_key=idempotency_key,
    )
    session.add(answer)

    if attempt.status == AttemptStatus.NOT_STARTED:
        attempt.status = AttemptStatus.IN_PROGRESS
        attempt.started_at = datetime.now(timezone.utc)

    await session.flush()
    return answer


async def complete_attempt(session: AsyncSession, attempt: BasicAssessmentAttempt) -> BasicAssessmentAttempt:
    """IN_PROGRESS -> COMPLETED. Once COMPLETED, `submit_answer` will
    always reject further answers for this attempt (see above) -- there is
    no separate "lock" step, completion itself is the lock."""

    if attempt.status != AttemptStatus.IN_PROGRESS:
        raise BasicAttemptClosedError(
            f"attempt {attempt.id} is {attempt.status.value}, only an in-progress attempt can be completed"
        )
    attempt.status = AttemptStatus.COMPLETED
    attempt.completed_at = datetime.now(timezone.utc)
    await session.flush()
    return attempt


async def latest_answers_by_item(
    session: AsyncSession, attempt: BasicAssessmentAttempt
) -> dict[uuid.UUID, BasicAssessmentAnswer]:
    """"Latest answer per item wins" read convention -- mirrors the
    existing PRO Hybrid `Answer` convention exactly. Answers are ordered by
    `created_at` ascending on the relationship, so a simple last-write-wins
    fold over the loaded list is correct and needs no extra query."""

    result = await session.execute(
        select(BasicAssessmentAnswer)
        .where(BasicAssessmentAnswer.attempt_id == attempt.id)
        .order_by(BasicAssessmentAnswer.created_at)
    )
    latest: dict[uuid.UUID, BasicAssessmentAnswer] = {}
    for answer in result.scalars().all():
        latest[answer.item_id] = answer
    return latest
