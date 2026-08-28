"""Shared test helpers for Matching V1 M2 (not collected as a test module
itself -- no test_ prefix)."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.db.models_basic_assessment import AssessmentDefinition, AssessmentItem, AssessmentItemOption, ResponseType
from app.db.models_identity import IdentityUser
from app.services.basic_assessment.attempts import get_or_create_active_attempt, submit_answer


async def make_user(session) -> IdentityUser:
    user = IdentityUser()
    session.add(user)
    await session.flush()
    return user


async def answer_all_items(
    session,
    definition: AssessmentDefinition,
    *,
    user: IdentityUser | None = None,
    likert_bias: dict[tuple[str, str], int] | None = None,
    default_likert: int = 3,
):
    """Answers every active item of `definition` for a fresh attempt and
    returns (attempt, user). `likert_bias` maps (scale_family.value,
    scale_key) -> raw 1-5 response to apply to every item of that scale
    (before any reverse-scoring correction, exactly what a respondent
    would literally select); scales not present in the map get
    `default_likert` on every item."""

    likert_bias = likert_bias or {}
    user = user or await make_user(session)

    items_result = await session.execute(
        select(AssessmentItem).where(AssessmentItem.definition_id == definition.id, AssessmentItem.active.is_(True))
    )
    items = list(items_result.scalars().all())

    attempt = await get_or_create_active_attempt(session, user_id=user.id, definition=definition)

    for idx, item in enumerate(items):
        key = (item.scale_family.value, item.scale_key)
        if item.response_type == ResponseType.LIKERT_5:
            value = likert_bias.get(key, default_likert)
            await submit_answer(session, attempt=attempt, item=item, idempotency_key=f"seed_{idx}", numeric_value=value)
        elif item.response_type == ResponseType.BOOLEAN:
            await submit_answer(session, attempt=attempt, item=item, idempotency_key=f"seed_{idx}", boolean_value=True)
        elif item.response_type in (ResponseType.SINGLE_CHOICE, ResponseType.MULTI_CHOICE):
            options = (
                (await session.execute(select(AssessmentItemOption).where(AssessmentItemOption.item_id == item.id)))
                .scalars()
                .all()
            )
            option_key = options[0].option_key
            await submit_answer(
                session, attempt=attempt, item=item, idempotency_key=f"seed_{idx}", selected_option_keys=[option_key]
            )
        elif item.response_type == ResponseType.NUMERIC:
            await submit_answer(session, attempt=attempt, item=item, idempotency_key=f"seed_{idx}", numeric_value=1)

    return attempt, user
