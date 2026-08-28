"""Matching V1 M1 -- attempt lifecycle and immutability (Founder Review
test items #15-18)."""

import pytest
from sqlalchemy import select

from app.db.models_basic_assessment import AssessmentItem, AttemptStatus, BasicAssessmentAttempt
from app.db.models_identity import IdentityUser
from app.services.basic_assessment.attempts import (
    complete_attempt,
    get_or_create_active_attempt,
    latest_answers_by_item,
    submit_answer,
)
from app.services.basic_assessment.seed import seed_alpha_long_form
from app.services.exceptions import BasicAttemptClosedError


async def _make_user(session) -> IdentityUser:
    user = IdentityUser()
    session.add(user)
    await session.flush()
    return user


async def _first_item(session, item_key: str) -> AssessmentItem:
    return (await session.execute(select(AssessmentItem).where(AssessmentItem.item_key == item_key))).scalar_one()


async def test_retake_creates_new_attempt_after_completion(session):
    """#15."""
    definition = await seed_alpha_long_form(session)
    user = await _make_user(session)

    attempt1 = await get_or_create_active_attempt(session, user_id=user.id, definition=definition)
    item = await _first_item(session, "riasec_R_1")
    await submit_answer(session, attempt=attempt1, item=item, idempotency_key="a1", numeric_value=3)
    await complete_attempt(session, attempt1)
    await session.commit()

    attempt2 = await get_or_create_active_attempt(session, user_id=user.id, definition=definition)
    assert attempt2.id != attempt1.id
    assert attempt2.status == AttemptStatus.NOT_STARTED


async def test_old_answers_remain_immutable_across_retake(session):
    """#16 -- the first attempt's answer row is untouched by a later retake."""
    definition = await seed_alpha_long_form(session)
    user = await _make_user(session)

    attempt1 = await get_or_create_active_attempt(session, user_id=user.id, definition=definition)
    item = await _first_item(session, "riasec_R_1")
    old_answer = await submit_answer(session, attempt=attempt1, item=item, idempotency_key="a1", numeric_value=5)
    await complete_attempt(session, attempt1)
    await session.commit()

    attempt2 = await get_or_create_active_attempt(session, user_id=user.id, definition=definition)
    await submit_answer(session, attempt=attempt2, item=item, idempotency_key="a1", numeric_value=1)
    await session.commit()

    await session.refresh(old_answer)
    assert old_answer.numeric_value == 5  # never overwritten
    assert old_answer.attempt_id == attempt1.id


async def test_one_current_open_attempt_rule(session):
    """#17 -- DB-level partial unique index prevents a second open attempt."""
    definition = await seed_alpha_long_form(session)
    user = await _make_user(session)

    attempt1 = await get_or_create_active_attempt(session, user_id=user.id, definition=definition)
    await session.commit()

    # calling get_or_create again returns the SAME open attempt, never a second one
    attempt_again = await get_or_create_active_attempt(session, user_id=user.id, definition=definition)
    assert attempt_again.id == attempt1.id

    # a raw attempt to insert a second open attempt for the same user violates the DB constraint
    duplicate = BasicAssessmentAttempt(user_id=user.id, definition_id=definition.id, status=AttemptStatus.NOT_STARTED)
    session.add(duplicate)
    with pytest.raises(Exception):
        await session.flush()
    await session.rollback()


async def test_completed_attempt_cannot_be_silently_edited(session):
    """#18."""
    definition = await seed_alpha_long_form(session)
    user = await _make_user(session)

    attempt = await get_or_create_active_attempt(session, user_id=user.id, definition=definition)
    item = await _first_item(session, "riasec_R_1")
    await submit_answer(session, attempt=attempt, item=item, idempotency_key="a1", numeric_value=3)
    await complete_attempt(session, attempt)
    await session.commit()

    with pytest.raises(BasicAttemptClosedError):
        await submit_answer(session, attempt=attempt, item=item, idempotency_key="a2", numeric_value=4)

    with pytest.raises(BasicAttemptClosedError):
        await complete_attempt(session, attempt)


async def test_latest_answers_by_item_read_convention(session):
    """Sanity check on the "latest wins" read helper, exercised implicitly
    by test #16 above but verified directly here."""
    definition = await seed_alpha_long_form(session)
    user = await _make_user(session)
    attempt = await get_or_create_active_attempt(session, user_id=user.id, definition=definition)
    item = await _first_item(session, "riasec_R_1")

    await submit_answer(session, attempt=attempt, item=item, idempotency_key="v1", numeric_value=2)
    await submit_answer(session, attempt=attempt, item=item, idempotency_key="v2", numeric_value=5)
    await session.commit()

    latest = await latest_answers_by_item(session, attempt)
    assert latest[item.id].numeric_value == 5
