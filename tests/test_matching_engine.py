"""Matching V1 M4 -- DB-wired engine behavior (Founder Review test items
#7-14, #26, #27)."""

import pytest
from sqlalchemy import select

from app.db.models_basic_assessment import MatchingUsage, ScaleFamily
from app.db.models_basic_profile import ProfileScaleResult
from app.db.models_matching import FitStatus, MatchFamilyResult, MatchingResult
from app.services.basic_assessment.attempts import complete_attempt
from app.services.basic_assessment.seed import seed_alpha_long_form
from app.services.basic_profile.calculation import calculate_basic_profile
from app.services.career_kb.seed import seed_alpha_career_matching_profiles
from app.services.knowledge.retrieval import get_career_by_code
from app.services.matching.engine import calculate_pair_match, match_profile_to_careers
from tests.helpers_basic_profile import answer_all_items


async def _build_profile(session, *, likert_bias=None):
    definition = await seed_alpha_long_form(session)
    attempt, user = await answer_all_items(session, definition, likert_bias=likert_bias or {}, default_likert=3)
    await complete_attempt(session, attempt)
    await session.commit()
    profile = await calculate_basic_profile(session, attempt)
    await session.commit()
    return profile, user


async def test_work_style_compares_only_match_enabled(session):
    """#7 -- the user-side values fed into the Work Style comparison
    contain ONLY the 5 MATCH_ENABLED scale keys, never the 5 PROXY/
    MNP_ONLY ones, even though M2's DeterministicProfile computed all 10."""
    profile, _user = await _build_profile(session)
    await seed_alpha_career_matching_profiles(session)
    await session.commit()

    from app.services.matching.engine import _load_user_family_values

    values = await _load_user_family_values(session, profile.id)
    work_style_keys = set(values[ScaleFamily.WORK_STYLE])
    assert work_style_keys <= {"leadership", "initiative", "ambiguity_tolerance", "structure_preference", "collaboration"}
    assert "autonomy" not in work_style_keys  # MNP_ONLY -- excluded
    assert "pace" not in work_style_keys  # PROXY -- excluded


async def test_profile_only_excluded(session):
    """#8 -- explicit assertion: every scale actually present in the
    match-eligible user values has matching_usage == MATCH_ENABLED."""
    profile, _user = await _build_profile(session)
    result = await session.execute(
        select(ProfileScaleResult).where(
            ProfileScaleResult.profile_id == profile.id, ProfileScaleResult.scale_family == "work_style"
        )
    )
    all_ws_results = {r.scale_key: r for r in result.scalars().all()}
    assert len(all_ws_results) == 10  # M2 computed all 10

    from app.services.matching.engine import _load_user_family_values

    values = await _load_user_family_values(session, profile.id)
    for key in values[ScaleFamily.WORK_STYLE]:
        assert all_ws_results[key].matching_usage == MatchingUsage.MATCH_ENABLED


async def test_missing_career_work_style_not_zero(session):
    """#9 -- registered_nurse has zero Work Style components; the career
    side dict is empty, never a dict of zeros."""
    await seed_alpha_career_matching_profiles(session)
    await session.commit()
    career = await get_career_by_code(session, "registered_nurse")

    from app.services.matching.engine import _load_career_family_values

    from app.db.models_career_kb import CareerMatchingProfile

    career_profile = (
        await session.execute(
            select(CareerMatchingProfile).where(
                CareerMatchingProfile.career_id == career.id, CareerMatchingProfile.is_current.is_(True)
            )
        )
    ).scalar_one()
    values, _provisional = await _load_career_family_values(session, career_profile.id)
    assert values[ScaleFamily.WORK_STYLE] == {}
    assert values[ScaleFamily.WORK_VALUES] == {}


async def test_insufficient_work_style_data_result(session):
    """#10 -- pairing against a career with zero Work Style components
    yields INSUFFICIENT_DATA for that family, never a fabricated score."""
    profile, _user = await _build_profile(session)
    await seed_alpha_career_matching_profiles(session)
    await session.commit()

    career = await get_career_by_code(session, "registered_nurse")
    from app.db.models_career_kb import CareerMatchingProfile

    career_profile = (
        await session.execute(
            select(CareerMatchingProfile).where(
                CareerMatchingProfile.career_id == career.id, CareerMatchingProfile.is_current.is_(True)
            )
        )
    ).scalar_one()

    matching_result = await calculate_pair_match(session, profile=profile, career_matching_profile=career_profile)
    await session.commit()

    family_row = (
        await session.execute(
            select(MatchFamilyResult).where(
                MatchFamilyResult.matching_result_id == matching_result.id,
                MatchFamilyResult.scale_family == "work_style",
            )
        )
    ).scalar_one()
    assert family_row.status == FitStatus.INSUFFICIENT_DATA
    assert family_row.raw_score is None


async def test_real_alpha_values_fit_insufficient_data(session):
    """#11 -- LOCKED regression: the real Alpha dataset has NO Work
    Values career-side components for ANY of the 24 careers (M3's honest
    limitation) -- Values Fit must be INSUFFICIENT_DATA for every one of
    them, unconditionally, until real sourced data is imported."""
    profile, _user = await _build_profile(session)
    await seed_alpha_career_matching_profiles(session)
    await session.commit()
    results = await match_profile_to_careers(session, profile_id=profile.id)
    await session.commit()

    assert len(results) == 24
    for matching_result in results:
        values_row = (
            await session.execute(
                select(MatchFamilyResult).where(
                    MatchFamilyResult.matching_result_id == matching_result.id,
                    MatchFamilyResult.scale_family == "work_values",
                )
            )
        ).scalar_one()
        assert values_row.status == FitStatus.INSUFFICIENT_DATA, (
            f"career {matching_result.career_id} unexpectedly has a Values Fit score -- "
            "this must only change once real O*NET Work Values data is imported (see doc 24 limitations)"
        )


async def test_environment_missing_not_treated_as_mismatch(session):
    """#12 -- Work Environment has zero career-side components in Alpha
    (M3 limitation); this must contribute NOTHING (no fifth public Fit
    output, no penalty anywhere) -- verified by confirming no
    MatchFamilyResult row for work_environment exists at all (only the 3
    families explicitly in scope: RIASEC/Work Style/Work Values)."""
    profile, _user = await _build_profile(session)
    await seed_alpha_career_matching_profiles(session)
    await session.commit()
    results = await match_profile_to_careers(session, profile_id=profile.id)
    await session.commit()

    for matching_result in results:
        rows = (
            (await session.execute(select(MatchFamilyResult).where(MatchFamilyResult.matching_result_id == matching_result.id)))
            .scalars()
            .all()
        )
        families = {r.scale_family.value for r in rows}
        assert families == {"riasec", "work_style", "work_values"}  # never a 4th/5th family row


async def test_assessment_coverage_separate_from_match_coverage(session):
    """#13."""
    profile, _user = await _build_profile(session)
    await seed_alpha_career_matching_profiles(session)
    await session.commit()

    career = await get_career_by_code(session, "software_developer")
    from app.db.models_career_kb import CareerMatchingProfile

    career_profile = (
        await session.execute(
            select(CareerMatchingProfile).where(
                CareerMatchingProfile.career_id == career.id, CareerMatchingProfile.is_current.is_(True)
            )
        )
    ).scalar_one()
    matching_result = await calculate_pair_match(session, profile=profile, career_matching_profile=career_profile)
    await session.commit()

    riasec_row = (
        await session.execute(
            select(MatchFamilyResult).where(
                MatchFamilyResult.matching_result_id == matching_result.id, MatchFamilyResult.scale_family == "riasec"
            )
        )
    ).scalar_one()

    # profile.coverage (M2 Assessment Coverage) and riasec_row.coverage_ratio
    # (M4 Match Coverage) are DIFFERENT numbers measuring different things --
    # both fully populated (1.0) here since the fixture answers everything,
    # but they are distinct fields on distinct tables, never conflated.
    assert profile.coverage == pytest.approx(1.0)
    assert riasec_row.coverage_ratio == pytest.approx(1.0)
    assert not hasattr(matching_result, "coverage")  # MatchingResult itself has no such field


async def test_family_match_coverage_correct(session):
    """#14 -- sales_manager's Work Style Match Coverage = comparable / user
    component count = 2/5 (leadership+initiative comparable, out of the
    user's 5 MATCH_ENABLED Work Style scales)."""
    profile, _user = await _build_profile(session)
    await seed_alpha_career_matching_profiles(session)
    await session.commit()

    career = await get_career_by_code(session, "sales_manager")
    from app.db.models_career_kb import CareerMatchingProfile

    career_profile = (
        await session.execute(
            select(CareerMatchingProfile).where(
                CareerMatchingProfile.career_id == career.id, CareerMatchingProfile.is_current.is_(True)
            )
        )
    ).scalar_one()
    matching_result = await calculate_pair_match(session, profile=profile, career_matching_profile=career_profile)
    await session.commit()

    ws_row = (
        await session.execute(
            select(MatchFamilyResult).where(
                MatchFamilyResult.matching_result_id == matching_result.id, MatchFamilyResult.scale_family == "work_style"
            )
        )
    ).scalar_one()
    assert ws_row.comparable_component_count == 2
    assert ws_row.user_component_count == 5
    assert ws_row.coverage_ratio == pytest.approx(2 / 5)


async def test_versions_pinned(session):
    """#26."""
    profile, _user = await _build_profile(session)
    await seed_alpha_career_matching_profiles(session)
    await session.commit()
    results = await match_profile_to_careers(session, profile_id=profile.id, career_ids=None)
    await session.commit()

    result = results[0]
    assert result.assessment_version == profile.assessment_version
    assert result.profile_engine_version == profile.profile_engine_version
    assert result.matching_methodology_version == profile.methodology_version
    assert result.career_vector_version
    assert result.career_source_version
    assert result.matching_engine_version == "matching_engine_v0.1"
    assert result.metric_version == "guarded_cosine_v0.1"
    assert result.config_version == "matching_config_v0.1"


async def test_historical_result_immutable(session):
    """#27."""
    profile, _user = await _build_profile(session)
    await seed_alpha_career_matching_profiles(session)
    await session.commit()
    career = await get_career_by_code(session, "software_developer")
    from app.db.models_career_kb import CareerMatchingProfile

    career_profile = (
        await session.execute(
            select(CareerMatchingProfile).where(
                CareerMatchingProfile.career_id == career.id, CareerMatchingProfile.is_current.is_(True)
            )
        )
    ).scalar_one()

    result1 = await calculate_pair_match(session, profile=profile, career_matching_profile=career_profile)
    await session.commit()
    result2 = await calculate_pair_match(session, profile=profile, career_matching_profile=career_profile)
    await session.commit()

    assert result1.id == result2.id  # idempotent re-run, no duplicate row

    all_results = (
        (await session.execute(select(MatchingResult).where(
            MatchingResult.profile_id == profile.id, MatchingResult.career_matching_profile_id == career_profile.id
        )))
        .scalars()
        .all()
    )
    assert len(all_results) == 1
