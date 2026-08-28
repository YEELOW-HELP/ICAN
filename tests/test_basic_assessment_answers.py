"""Matching V1 M1 -- structured answer persistence and validation (Founder
Review test items #11-14)."""

import pytest

from app.db.models_basic_assessment import AssessmentItem, ResponseType
from app.db.models_identity import IdentityUser
from app.services.basic_assessment.attempts import get_or_create_active_attempt, submit_answer
from app.services.basic_assessment.seed import seed_alpha_long_form
from app.services.exceptions import InvalidResponseError


async def _make_user(session) -> IdentityUser:
    user = IdentityUser()
    session.add(user)
    await session.flush()
    return user


async def test_valid_likert_answer_persists(session):
    """#11."""
    definition = await seed_alpha_long_form(session)
    user = await _make_user(session)
    attempt = await get_or_create_active_attempt(session, user_id=user.id, definition=definition)

    from sqlalchemy import select

    item = (
        await session.execute(select(AssessmentItem).where(AssessmentItem.item_key == "riasec_R_1"))
    ).scalar_one()

    answer = await submit_answer(session, attempt=attempt, item=item, idempotency_key="k1", numeric_value=4)
    await session.commit()

    assert answer.numeric_value == 4
    assert answer.response_type == ResponseType.LIKERT_5


async def test_invalid_likert_answer_rejected(session):
    """#12."""
    definition = await seed_alpha_long_form(session)
    user = await _make_user(session)
    attempt = await get_or_create_active_attempt(session, user_id=user.id, definition=definition)

    from sqlalchemy import select

    item = (
        await session.execute(select(AssessmentItem).where(AssessmentItem.item_key == "riasec_R_1"))
    ).scalar_one()

    with pytest.raises(InvalidResponseError):
        await submit_answer(session, attempt=attempt, item=item, idempotency_key="k2", numeric_value=7)

    with pytest.raises(InvalidResponseError):
        await submit_answer(session, attempt=attempt, item=item, idempotency_key="k3", numeric_value=None)


async def test_single_choice_validation(session):
    """#13."""
    definition = await seed_alpha_long_form(session)
    user = await _make_user(session)
    attempt = await get_or_create_active_attempt(session, user_id=user.id, definition=definition)

    from sqlalchemy import select

    item = (
        await session.execute(select(AssessmentItem).where(AssessmentItem.item_key == "goals_horizon_horizon"))
    ).scalar_one()
    assert item.response_type == ResponseType.SINGLE_CHOICE

    answer = await submit_answer(
        session, attempt=attempt, item=item, idempotency_key="k4", selected_option_keys=["now"]
    )
    await session.commit()
    assert answer.selected_option_keys == ["now"]

    with pytest.raises(InvalidResponseError):
        await submit_answer(
            session, attempt=attempt, item=item, idempotency_key="k5", selected_option_keys=["not_a_real_option"]
        )

    with pytest.raises(InvalidResponseError):
        await submit_answer(
            session, attempt=attempt, item=item, idempotency_key="k6", selected_option_keys=["now", "exploring"]
        )


async def test_multi_choice_validation(session):
    """#14."""
    definition = await seed_alpha_long_form(session)
    user = await _make_user(session)
    attempt = await get_or_create_active_attempt(session, user_id=user.id, definition=definition)

    from sqlalchemy import select

    item = (
        await session.execute(
            select(AssessmentItem).where(AssessmentItem.item_key == "goals_desired_domains_domains")
        )
    ).scalar_one()
    assert item.response_type == ResponseType.MULTI_CHOICE

    answer = await submit_answer(
        session,
        attempt=attempt,
        item=item,
        idempotency_key="k7",
        selected_option_keys=["technology", "healthcare"],
    )
    await session.commit()
    assert set(answer.selected_option_keys) == {"technology", "healthcare"}

    with pytest.raises(InvalidResponseError):
        await submit_answer(session, attempt=attempt, item=item, idempotency_key="k8", selected_option_keys=[])

    with pytest.raises(InvalidResponseError):
        await submit_answer(
            session, attempt=attempt, item=item, idempotency_key="k9", selected_option_keys=["not_a_real_domain"]
        )
