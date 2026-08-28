"""Matching V1 M2 -- minimum-dispersion differentiation gate (Founder
Review test items #20-21)."""

import pytest

from app.db.models_basic_assessment import ScaleFamily
from app.db.models_basic_profile import DifferentiationState
from app.services.basic_assessment.attempts import complete_attempt
from app.services.basic_assessment.seed import seed_alpha_long_form
from app.services.basic_profile.calculation import calculate_basic_profile
from tests.helpers_basic_profile import answer_all_items


async def test_flat_profile_produces_low_differentiation(session):
    """#20 -- every RIASEC item answered identically (raw=3 everywhere) ->
    normalized values all equal -> stdev == 0 < 0.10 threshold ->
    LOW_DIFFERENTIATION, never silently NORMAL."""
    definition = await seed_alpha_long_form(session)
    attempt, _user = await answer_all_items(session, definition, default_likert=3)
    await complete_attempt(session, attempt)
    await session.commit()

    profile = await calculate_basic_profile(session, attempt)
    await session.commit()

    from sqlalchemy import select
    from app.db.models_basic_profile import ProfileVectorDifferentiation

    result = await session.execute(
        select(ProfileVectorDifferentiation).where(
            ProfileVectorDifferentiation.profile_id == profile.id,
            ProfileVectorDifferentiation.scale_family == "riasec",
        )
    )
    riasec_diff = result.scalar_one()
    assert riasec_diff.stdev == pytest.approx(0.0, abs=1e-9)
    assert riasec_diff.state == DifferentiationState.LOW_DIFFERENTIATION
    assert profile.differentiation_state == DifferentiationState.LOW_DIFFERENTIATION


async def test_differentiated_profile_produces_normal(session):
    """#21 -- a clearly peaked RIASEC pattern yields real dispersion ->
    NORMAL."""
    definition = await seed_alpha_long_form(session)
    bias = {
        ("riasec", "R"): 5,
        ("riasec", "I"): 5,
        ("riasec", "A"): 1,
        ("riasec", "S"): 1,
        ("riasec", "E"): 3,
        ("riasec", "C"): 3,
    }
    attempt, _user = await answer_all_items(session, definition, likert_bias=bias, default_likert=3)
    await complete_attempt(session, attempt)
    await session.commit()

    profile = await calculate_basic_profile(session, attempt)
    await session.commit()

    from sqlalchemy import select
    from app.db.models_basic_profile import ProfileVectorDifferentiation

    result = await session.execute(
        select(ProfileVectorDifferentiation).where(
            ProfileVectorDifferentiation.profile_id == profile.id,
            ProfileVectorDifferentiation.scale_family == "riasec",
        )
    )
    riasec_diff = result.scalar_one()
    assert riasec_diff.stdev > 0.10
    assert riasec_diff.state == DifferentiationState.NORMAL


async def test_riasec_ordering_deterministic_tie_break(session):
    """Sanity check on `_order_riasec`'s documented tie-break (descending
    value, then ascending scale_key alphabetically)."""
    definition = await seed_alpha_long_form(session)
    bias = {("riasec", "R"): 5, ("riasec", "I"): 5}  # tie at the top between R and I
    attempt, _user = await answer_all_items(session, definition, likert_bias=bias, default_likert=1)
    await complete_attempt(session, attempt)
    await session.commit()

    profile = await calculate_basic_profile(session, attempt)
    await session.commit()

    assert profile.interest_ordering[0] == "I"  # alphabetically before R when tied
    assert profile.interest_ordering[1] == "R"
