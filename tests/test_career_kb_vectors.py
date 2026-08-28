"""Matching V1 M3 -- career vector normalization and the PROFILE_ONLY
gate (Founder Review test items #8-18, #25)."""

import pytest

from app.db.models_basic_assessment import MappingStatus, ScaleFamily
from app.services.basic_assessment.seed import seed_alpha_long_form
from app.services.career_kb.queries import get_career_matching_profile
from app.services.career_kb.seed import seed_alpha_career_matching_profiles
from app.services.career_kb.vectors import (
    add_career_matching_component,
    create_career_matching_profile,
    holland_code_to_riasec_vector,
)
from app.services.exceptions import MatchDisabledScaleError
from app.services.knowledge.retrieval import get_career_by_code


async def test_riasec_six_vector_persists(session):
    """#8 -- the complete six-dimensional vector, not a Top-3 reduction."""
    await seed_alpha_career_matching_profiles(session)
    await session.commit()

    career = await get_career_by_code(session, "software_developer")
    view = await get_career_matching_profile(session, career.id)
    assert {c.scale_key for c in view.interests.components} == {"R", "I", "A", "S", "E", "C"}
    assert all(c.normalized_value is not None for c in view.interests.components)


def test_riasec_normalization_deterministic():
    """#9 -- same source (Holland code) always produces the same vector."""
    v1 = holland_code_to_riasec_vector("IC")
    v2 = holland_code_to_riasec_vector("IC")
    assert v1 == v2
    assert v1["I"] == pytest.approx(0.90)
    assert v1["C"] == pytest.approx(0.70)
    assert v1["R"] == pytest.approx(0.20)
    assert v1["A"] == pytest.approx(0.20)
    assert v1["S"] == pytest.approx(0.20)
    assert v1["E"] == pytest.approx(0.20)
    assert sum(v1.values()) == sum(v2.values())


async def test_current_onet_work_style_mapping_used(session):
    """#10 -- sales_manager's Work Style components use scale keys from
    the CURRENT (post-2024-redesign) O*NET taxonomy (leadership,
    initiative), reusing M1's own AssessmentScale mapping_status, not a
    reinvented/outdated one."""
    await seed_alpha_career_matching_profiles(session)
    await session.commit()

    career = await get_career_by_code(session, "sales_manager")
    view = await get_career_matching_profile(session, career.id)
    keys = {c.scale_key for c in view.work_styles.components}
    assert keys == {"leadership", "initiative"}
    for c in view.work_styles.components:
        assert c.mapping_status == MappingStatus.DIRECT.value


async def test_direct_creates_match_enabled_component(session):
    """#11."""
    await seed_alpha_long_form(session)
    await session.commit()
    from app.services.knowledge.seed import ensure_seed_knowledge_base

    await ensure_seed_knowledge_base(session)
    career = await get_career_by_code(session, "sales_manager")
    profile = await create_career_matching_profile(
        session, career_id=career.id, career_vector_version="v_test", matching_methodology_version="golden_test_v0.1",
        source_version="onet_test", mapping_version="mnp_test",
    )
    component = await add_career_matching_component(
        session, profile=profile, scale_family=ScaleFamily.WORK_STYLE, scale_key="leadership",
        normalized_value=0.9, transformation_version="test_v0.1",
    )
    assert component.mapping_status == MappingStatus.DIRECT
    from app.db.models_basic_assessment import MatchingUsage

    assert component.matching_usage == MatchingUsage.MATCH_ENABLED
    assert component.provisional is False  # DIRECT -> not provisional


async def test_derived_creates_provisional_match_enabled_component(session):
    """#12."""
    from app.services.knowledge.seed import ensure_seed_knowledge_base

    await seed_alpha_long_form(session)
    await ensure_seed_knowledge_base(session)
    await session.commit()
    career = await get_career_by_code(session, "sales_manager")
    profile = await create_career_matching_profile(
        session, career_id=career.id, career_vector_version="v_test", matching_methodology_version="golden_test_v0.1",
        source_version="onet_test", mapping_version="mnp_test",
    )
    component = await add_career_matching_component(
        session, profile=profile, scale_family=ScaleFamily.WORK_STYLE, scale_key="collaboration",
        normalized_value=0.6, transformation_version="test_v0.1",
    )
    assert component.mapping_status == MappingStatus.DERIVED
    from app.db.models_basic_assessment import MatchingUsage

    assert component.matching_usage == MatchingUsage.MATCH_ENABLED
    assert component.provisional is True


async def test_proxy_does_not_create_match_component(session):
    """#13 -- the hard Founder Review invariant, enforced, not just documented."""
    from app.services.knowledge.seed import ensure_seed_knowledge_base

    await seed_alpha_long_form(session)
    await ensure_seed_knowledge_base(session)
    await session.commit()
    career = await get_career_by_code(session, "sales_manager")
    profile = await create_career_matching_profile(
        session, career_id=career.id, career_vector_version="v_test", matching_methodology_version="golden_test_v0.1",
        source_version="onet_test", mapping_version="mnp_test",
    )
    with pytest.raises(MatchDisabledScaleError):
        await add_career_matching_component(
            session, profile=profile, scale_family=ScaleFamily.WORK_STYLE, scale_key="pace",  # PROXY
            normalized_value=0.5, transformation_version="test_v0.1",
        )


async def test_mnp_only_does_not_create_match_component(session):
    """#14."""
    from app.services.knowledge.seed import ensure_seed_knowledge_base

    await seed_alpha_long_form(session)
    await ensure_seed_knowledge_base(session)
    await session.commit()
    career = await get_career_by_code(session, "sales_manager")
    profile = await create_career_matching_profile(
        session, career_id=career.id, career_vector_version="v_test", matching_methodology_version="golden_test_v0.1",
        source_version="onet_test", mapping_version="mnp_test",
    )
    with pytest.raises(MatchDisabledScaleError):
        await add_career_matching_component(
            session, profile=profile, scale_family=ScaleFamily.WORK_STYLE, scale_key="autonomy",  # MNP_ONLY
            normalized_value=0.5, transformation_version="test_v0.1",
        )
    with pytest.raises(MatchDisabledScaleError):
        await add_career_matching_component(
            session, profile=profile, scale_family=ScaleFamily.WORK_VALUES, scale_key="growth",  # MNP_ONLY
            normalized_value=0.5, transformation_version="test_v0.1",
        )


async def test_work_values_mapping_correct(session):
    """#15 -- only DIRECT Work Values scales (independence_value,
    impact_helping, recognition_status) may ever receive a component;
    PROXY (income, stability) may not."""
    from app.services.knowledge.seed import ensure_seed_knowledge_base

    await seed_alpha_long_form(session)
    await ensure_seed_knowledge_base(session)
    await session.commit()
    career = await get_career_by_code(session, "registered_nurse")
    profile = await create_career_matching_profile(
        session, career_id=career.id, career_vector_version="v_test", matching_methodology_version="golden_test_v0.1",
        source_version="onet_test", mapping_version="mnp_test",
    )
    component = await add_career_matching_component(
        session, profile=profile, scale_family=ScaleFamily.WORK_VALUES, scale_key="impact_helping",
        normalized_value=0.9, transformation_version="test_v0.1", source_system="onet",
    )
    assert component.mapping_status == MappingStatus.DIRECT

    with pytest.raises(MatchDisabledScaleError):
        await add_career_matching_component(
            session, profile=profile, scale_family=ScaleFamily.WORK_VALUES, scale_key="income",  # PROXY
            normalized_value=0.5, transformation_version="test_v0.1",
        )


async def test_environment_mapping_follows_approved_mapping_only(session):
    """#16 -- all 5 Work Environment scales are MATCH_ENABLED per the
    approved mapping doc (2 DIRECT, 3 DERIVED); none are rejected, but the
    Alpha seed itself creates zero Environment components (honest scope
    limitation, doc 24) -- this test proves the MECHANISM would accept a
    genuinely-sourced Environment component if one existed."""
    from app.services.knowledge.seed import ensure_seed_knowledge_base

    await seed_alpha_long_form(session)
    await ensure_seed_knowledge_base(session)
    await session.commit()
    career = await get_career_by_code(session, "registered_nurse")
    profile = await create_career_matching_profile(
        session, career_id=career.id, career_vector_version="v_test", matching_methodology_version="golden_test_v0.1",
        source_version="onet_test", mapping_version="mnp_test",
    )
    component = await add_career_matching_component(
        session, profile=profile, scale_family=ScaleFamily.WORK_ENVIRONMENT, scale_key="collaboration_context",
        normalized_value=0.8, transformation_version="test_v0.1",
    )
    assert component.mapping_status == MappingStatus.DIRECT


async def test_missing_source_value_stays_missing_not_zero(session):
    """#17 -- community_outreach_coordinator is UNMAPPED, so it has NO
    RIASEC components at all (not six zeros)."""
    await seed_alpha_career_matching_profiles(session)
    await session.commit()

    career = await get_career_by_code(session, "community_outreach_coordinator")
    view = await get_career_matching_profile(session, career.id)
    assert view.interests.components == []  # genuinely absent, never a fabricated 0-vector


async def test_match_coverage_inputs_derivable(session):
    """#25 -- CareerVectorView.coverage() can be computed from what M3
    persisted, without M3 itself computing a final pairwise Match Coverage."""
    await seed_alpha_career_matching_profiles(session)
    await session.commit()

    career = await get_career_by_code(session, "sales_manager")
    view = await get_career_matching_profile(session, career.id)
    # 10 Work Style scales total, only 2 (leadership, initiative) have real data for this career
    all_work_style_keys = [
        "autonomy", "structure_preference", "ambiguity_tolerance", "pace", "collaboration",
        "leadership", "customer_interaction", "decision_responsibility", "routine_tolerance", "initiative",
    ]
    assert view.work_styles.coverage(all_work_style_keys) == pytest.approx(2 / 10)
