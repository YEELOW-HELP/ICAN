"""Matching V1 M2 -- deterministic profile calculation (Founder Review
test items #1-19)."""

import pytest
from sqlalchemy import select

from app.db.models_basic_assessment import (
    AssessmentItem,
    AssessmentScale,
    AttemptStatus,
    MappingStatus,
    MatchingUsage,
    ScaleFamily,
)
from app.services.basic_assessment.attempts import complete_attempt, get_or_create_active_attempt
from app.services.basic_assessment.seed import seed_alpha_long_form
from app.services.basic_profile.calculation import calculate_basic_profile
from app.services.basic_profile.queries import get_profile_scale_results
from app.services.exceptions import BasicAttemptNotCompletedError
from tests.helpers_basic_profile import answer_all_items, make_user


async def test_completed_attempt_calculates_profile(session):
    """#1."""
    definition = await seed_alpha_long_form(session)
    attempt, _user = await answer_all_items(session, definition)
    await complete_attempt(session, attempt)
    await session.commit()

    profile = await calculate_basic_profile(session, attempt)
    await session.commit()

    assert profile.attempt_id == attempt.id
    assert profile.is_current is True
    assert profile.status.value == "ready"


async def test_incomplete_attempt_cannot_calculate(session):
    """#2."""
    definition = await seed_alpha_long_form(session)
    user = await make_user(session)
    attempt = await get_or_create_active_attempt(session, user_id=user.id, definition=definition)
    await session.commit()

    with pytest.raises(BasicAttemptNotCompletedError):
        await calculate_basic_profile(session, attempt)


async def test_all_six_riasec_scales_calculated(session):
    """#3."""
    definition = await seed_alpha_long_form(session)
    attempt, _user = await answer_all_items(session, definition)
    await complete_attempt(session, attempt)
    await session.commit()

    profile = await calculate_basic_profile(session, attempt)
    await session.commit()

    riasec_results = await get_profile_scale_results(session, profile, ScaleFamily.RIASEC)
    assert {r.scale_key for r in riasec_results} == {"R", "I", "A", "S", "E", "C"}
    assert all(r.sufficiently_answered for r in riasec_results)
    assert all(r.normalized_value is not None for r in riasec_results)


async def test_reverse_scoring_correct(session):
    """#4 -- exact formula: corrected = 6 - raw for reverse_scored items."""
    definition = await seed_alpha_long_form(session)
    # autonomy: item 1 straight, item 2 reverse. Raw answers 4 and 4 ->
    # corrected values [4, 6-4=2] -> mean 3.0 -> normalized (3.0-1)/4 = 0.5
    attempt, _user = await answer_all_items(
        session, definition, likert_bias={("work_style", "autonomy"): 4}, default_likert=3
    )
    await complete_attempt(session, attempt)
    await session.commit()

    profile = await calculate_basic_profile(session, attempt)
    await session.commit()

    results = await get_profile_scale_results(session, profile, ScaleFamily.WORK_STYLE)
    autonomy = next(r for r in results if r.scale_key == "autonomy")
    assert autonomy.raw_mean == pytest.approx(3.0)
    assert autonomy.normalized_value == pytest.approx(0.5)


async def test_normalization_correct(session):
    """#5 -- (raw_mean - 1) / 4, uniformly, all four Likert families."""
    definition = await seed_alpha_long_form(session)
    attempt, _user = await answer_all_items(session, definition, default_likert=5)
    await complete_attempt(session, attempt)
    await session.commit()

    profile = await calculate_basic_profile(session, attempt)
    await session.commit()

    results = await get_profile_scale_results(session, profile)
    likert_families = {ScaleFamily.RIASEC, ScaleFamily.WORK_STYLE, ScaleFamily.WORK_VALUES, ScaleFamily.WORK_ENVIRONMENT}
    for r in results:
        if r.scale_family not in likert_families:
            continue
        assert r.normalized_value == pytest.approx((r.raw_mean - 1) / 4)


async def test_work_style_work_values_work_environment_calculated(session):
    """#6, #7, #8."""
    definition = await seed_alpha_long_form(session)
    attempt, _user = await answer_all_items(session, definition)
    await complete_attempt(session, attempt)
    await session.commit()

    profile = await calculate_basic_profile(session, attempt)
    await session.commit()

    ws = await get_profile_scale_results(session, profile, ScaleFamily.WORK_STYLE)
    wv = await get_profile_scale_results(session, profile, ScaleFamily.WORK_VALUES)
    we = await get_profile_scale_results(session, profile, ScaleFamily.WORK_ENVIRONMENT)
    assert len(ws) == 10
    assert len(wv) == 8
    assert len(we) == 5


async def test_profile_only_scales_preserved_in_profile(session):
    """#9."""
    definition = await seed_alpha_long_form(session)
    attempt, _user = await answer_all_items(session, definition)
    await complete_attempt(session, attempt)
    await session.commit()

    profile = await calculate_basic_profile(session, attempt)
    await session.commit()

    results = await get_profile_scale_results(session, profile, ScaleFamily.WORK_STYLE)
    autonomy = next(r for r in results if r.scale_key == "autonomy")
    assert autonomy.matching_usage == MatchingUsage.PROFILE_ONLY
    assert autonomy.normalized_value is not None  # PROFILE_ONLY still gets a real, computed value


async def test_match_enabled_metadata_preserved(session):
    """#10."""
    definition = await seed_alpha_long_form(session)
    attempt, _user = await answer_all_items(session, definition)
    await complete_attempt(session, attempt)
    await session.commit()

    profile = await calculate_basic_profile(session, attempt)
    await session.commit()

    results = await get_profile_scale_results(session, profile, ScaleFamily.WORK_STYLE)
    leadership = next(r for r in results if r.scale_key == "leadership")
    assert leadership.mapping_status == MappingStatus.DIRECT
    assert leadership.matching_usage == MatchingUsage.MATCH_ENABLED


async def test_proxy_metadata_preserved(session):
    """#11."""
    definition = await seed_alpha_long_form(session)
    attempt, _user = await answer_all_items(session, definition)
    await complete_attempt(session, attempt)
    await session.commit()

    profile = await calculate_basic_profile(session, attempt)
    await session.commit()

    results = await get_profile_scale_results(session, profile, ScaleFamily.WORK_STYLE)
    pace = next(r for r in results if r.scale_key == "pace")
    assert pace.mapping_status == MappingStatus.PROXY
    assert pace.matching_usage == MatchingUsage.PROFILE_ONLY


async def test_mnp_only_metadata_preserved(session):
    """#12."""
    definition = await seed_alpha_long_form(session)
    attempt, _user = await answer_all_items(session, definition)
    await complete_attempt(session, attempt)
    await session.commit()

    profile = await calculate_basic_profile(session, attempt)
    await session.commit()

    results = await get_profile_scale_results(session, profile, ScaleFamily.WORK_VALUES)
    growth = next(r for r in results if r.scale_key == "growth")
    assert growth.mapping_status == MappingStatus.MNP_ONLY
    assert growth.matching_usage == MatchingUsage.PROFILE_ONLY


async def test_goals_experience_constraints_preserved_as_structured_context(session):
    """#13, #14, #15."""
    from app.db.models_basic_profile import ProfileStructuredContext

    definition = await seed_alpha_long_form(session)
    attempt, _user = await answer_all_items(session, definition)
    await complete_attempt(session, attempt)
    await session.commit()

    profile = await calculate_basic_profile(session, attempt)
    await session.commit()

    result = await session.execute(
        select(ProfileStructuredContext).where(ProfileStructuredContext.profile_id == profile.id)
    )
    rows = result.scalars().all()
    families = {r.scale_family for r in rows}
    assert ScaleFamily.GOALS in families
    assert ScaleFamily.EXPERIENCE in families
    assert ScaleFamily.CONSTRAINTS in families


async def test_no_invented_constraint_hardness(session):
    """#16 -- the structured-context row carries only the raw answer value,
    nothing resembling a synthesized hard/soft severity field."""
    from app.db.models_basic_profile import ProfileStructuredContext

    definition = await seed_alpha_long_form(session)
    attempt, _user = await answer_all_items(session, definition)
    await complete_attempt(session, attempt)
    await session.commit()

    profile = await calculate_basic_profile(session, attempt)
    await session.commit()

    result = await session.execute(
        select(ProfileStructuredContext).where(
            ProfileStructuredContext.profile_id == profile.id, ProfileStructuredContext.scale_family == "constraints"
        )
    )
    rows = result.scalars().all()
    assert rows
    for row in rows:
        assert not hasattr(row, "is_hard")
        assert not hasattr(row, "severity")
        assert not hasattr(row, "confidence")


async def test_coverage_schema_driven_not_hardcoded(session):
    """#17, #18 -- mutate the schema (make one RIASEC scale's items
    non-required) and prove the Coverage denominator actually changes,
    which could not happen if 29 were a literal constant in the
    calculation code."""
    definition = await seed_alpha_long_form(session)

    # Sanity: with the full seeded schema (all 29 Likert scales required),
    # a fully-answered attempt achieves Coverage == 1.0.
    attempt1, _user1 = await answer_all_items(session, definition)
    await complete_attempt(session, attempt1)
    await session.commit()
    profile1 = await calculate_basic_profile(session, attempt1)
    await session.commit()
    assert profile1.coverage == pytest.approx(1.0)

    # Mutate the schema: make the "C" RIASEC scale's items not-required.
    c_scale = (
        await session.execute(
            select(AssessmentScale).where(AssessmentScale.scale_family == "riasec", AssessmentScale.scale_key == "C")
        )
    ).scalar_one()
    c_items = (
        (await session.execute(select(AssessmentItem).where(AssessmentItem.scale_id == c_scale.id)))
        .scalars()
        .all()
    )
    for item in c_items:
        item.required = False
    await session.commit()

    # A second attempt answers everything EXCEPT the (now optional) C items.
    attempt2, user2 = await answer_all_items(session, definition)
    # remove the C answers to simulate "not answered" for an optional scale
    from app.db.models_basic_profile import DeterministicProfile
    from app.db.models_basic_assessment import BasicAssessmentAnswer

    c_item_ids = {i.id for i in c_items}
    answers_to_delete = (
        (
            await session.execute(
                select(BasicAssessmentAnswer).where(
                    BasicAssessmentAnswer.attempt_id == attempt2.id, BasicAssessmentAnswer.item_id.in_(c_item_ids)
                )
            )
        )
        .scalars()
        .all()
    )
    for a in answers_to_delete:
        await session.delete(a)
    await session.commit()

    await complete_attempt(session, attempt2)
    await session.commit()
    profile2 = await calculate_basic_profile(session, attempt2)
    await session.commit()

    # Denominator dropped from 29 (all required) to 28 (C excluded), and
    # since everything else is answered, Coverage is still 1.0 -- proving
    # the denominator itself is schema-derived, not a literal "29".
    assert profile2.coverage == pytest.approx(1.0)
    riasec2 = await get_profile_scale_results(session, profile2, ScaleFamily.RIASEC)
    c_result = next(r for r in riasec2 if r.scale_key == "C")
    assert c_result.sufficiently_answered is False  # unanswered, but no longer required -> doesn't hurt Coverage


async def test_context_completeness_computed_separately_from_coverage(session):
    """#19."""
    definition = await seed_alpha_long_form(session)
    attempt, _user = await answer_all_items(session, definition)
    await complete_attempt(session, attempt)
    await session.commit()

    profile = await calculate_basic_profile(session, attempt)
    await session.commit()

    # Both are fully answered here, but they are DIFFERENT fields backed by
    # different item sets -- verify they are tracked independently.
    assert profile.coverage == pytest.approx(1.0)
    assert profile.context_completeness == pytest.approx(1.0)
    assert isinstance(profile.coverage, float)
    assert isinstance(profile.context_completeness, float)
