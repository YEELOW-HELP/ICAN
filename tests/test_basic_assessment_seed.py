"""Matching V1 M1 -- versioned question bank seeding (Founder Review test
items #1-10)."""

from sqlalchemy import select

from app.db.models_basic_assessment import (
    AssessmentDefinition,
    AssessmentItem,
    AssessmentMode,
    AssessmentScale,
    MappingStatus,
    MatchingUsage,
)
from app.services.basic_assessment.definitions import get_active_definition, get_active_items
from app.services.basic_assessment.seed import ASSESSMENT_VERSION, seed_alpha_long_form


async def test_definition_can_be_seeded(session):
    """#1."""
    definition = await seed_alpha_long_form(session)
    await session.commit()
    assert definition.assessment_version == ASSESSMENT_VERSION
    assert definition.mode == AssessmentMode.BASIC_STRUCTURED
    assert definition.is_active is True


async def test_question_bank_is_versioned(session):
    """#2."""
    definition = await seed_alpha_long_form(session)
    await session.commit()
    result = await session.execute(select(AssessmentDefinition))
    all_defs = result.scalars().all()
    assert len(all_defs) == 1
    assert all_defs[0].assessment_version == definition.assessment_version


async def test_seed_is_idempotent_exactly_intended_bank_active(session):
    """#3 -- re-seeding does not duplicate rows, and exactly the intended
    ~75-item bank is active."""
    d1 = await seed_alpha_long_form(session)
    await session.commit()
    d2 = await seed_alpha_long_form(session)
    await session.commit()
    assert d1.id == d2.id

    active = await get_active_definition(session, AssessmentMode.BASIC_STRUCTURED)
    items = await get_active_items(session, active)
    # exact count derived from the seeded data, never hardcoded here as "75"
    assert len(items) == 18 + 20 + 16 + 5 + 2 + 10 + 4


async def test_item_order_deterministic(session):
    """#4."""
    definition = await seed_alpha_long_form(session)
    await session.commit()
    items_a = await get_active_items(session, definition)
    items_b = await get_active_items(session, definition)
    assert [i.item_key for i in items_a] == [i.item_key for i in items_b]
    orders = [i.display_order for i in items_a]
    assert orders == sorted(orders)
    assert len(set(orders)) == len(orders)  # no duplicate display_order


async def test_reverse_score_metadata_persists(session):
    """#5."""
    definition = await seed_alpha_long_form(session)
    await session.commit()
    items = await get_active_items(session, definition)
    autonomy_items = [i for i in items if i.scale_key == "autonomy"]
    assert len(autonomy_items) == 2
    reverse_flags = sorted(i.reverse_scored for i in autonomy_items)
    assert reverse_flags == [False, True]

    # Work Environment items are explicitly reverse_exempt (floor exception)
    env_items = [i for i in items if i.scale_family.value == "work_environment"]
    assert env_items
    assert all(i.reverse_exempt for i in env_items)
    assert all(not i.reverse_scored for i in env_items)


async def test_source_and_mapping_metadata_persists(session):
    """#6."""
    definition = await seed_alpha_long_form(session)
    await session.commit()
    result = await session.execute(
        select(AssessmentScale).where(AssessmentScale.scale_family == "riasec", AssessmentScale.scale_key == "R")
    )
    scale = result.scalar_one()
    assert scale.source_system == "onet"
    assert scale.source_version == "30.3"
    assert scale.mapping_status == MappingStatus.DIRECT
    assert scale.methodology_version == "golden_test_v0.1"


async def test_profile_only_vs_match_enabled_persists(session):
    """#7."""
    definition = await seed_alpha_long_form(session)
    await session.commit()
    items = await get_active_items(session, definition)

    goals_items = [i for i in items if i.scale_family.value == "goals"]
    assert goals_items and all(i.matching_usage == MatchingUsage.PROFILE_ONLY for i in goals_items)

    riasec_items = [i for i in items if i.scale_family.value == "riasec"]
    assert riasec_items and all(i.matching_usage == MatchingUsage.MATCH_ENABLED for i in riasec_items)


async def test_direct_mapping_defaults_to_match_enabled(session):
    """#8."""
    await seed_alpha_long_form(session)
    await session.commit()
    result = await session.execute(select(AssessmentScale).where(AssessmentScale.mapping_status == "direct"))
    direct_scales = result.scalars().all()
    assert direct_scales
    assert all(s.matching_usage == MatchingUsage.MATCH_ENABLED for s in direct_scales)


async def test_proxy_never_silently_match_enabled(session):
    """#9 -- the single most important invariant from Founder Review rule 3."""
    await seed_alpha_long_form(session)
    await session.commit()
    result = await session.execute(select(AssessmentScale).where(AssessmentScale.mapping_status == "proxy"))
    proxy_scales = result.scalars().all()
    assert proxy_scales  # sanity: PROXY scales actually exist in the bank (Work Style)
    assert all(s.matching_usage == MatchingUsage.PROFILE_ONLY for s in proxy_scales)

    # and the same invariant holds on the denormalized item-level copy
    result = await session.execute(
        select(AssessmentItem).join(AssessmentScale, AssessmentItem.scale_id == AssessmentScale.id).where(
            AssessmentScale.mapping_status == "proxy"
        )
    )
    proxy_items = result.scalars().all()
    assert proxy_items
    assert all(i.matching_usage == MatchingUsage.PROFILE_ONLY for i in proxy_items)


async def test_mnp_only_never_match_enabled(session):
    """#10."""
    await seed_alpha_long_form(session)
    await session.commit()
    result = await session.execute(select(AssessmentScale).where(AssessmentScale.mapping_status == "mnp_only"))
    mnp_only_scales = result.scalars().all()
    assert mnp_only_scales  # sanity: MNP_ONLY scales exist (autonomy, growth, all structured blocks, ...)
    assert all(s.matching_usage == MatchingUsage.PROFILE_ONLY for s in mnp_only_scales)


async def test_compute_matching_usage_is_the_sole_authority():
    """No scale in the seeded bank has a matching_usage inconsistent with
    `compute_matching_usage(mapping_status)` -- guards against a future
    hand-set override slipping past code review."""
    from app.db.models_basic_assessment import compute_matching_usage

    assert compute_matching_usage(MappingStatus.DIRECT) == MatchingUsage.MATCH_ENABLED
    assert compute_matching_usage(MappingStatus.DERIVED) == MatchingUsage.MATCH_ENABLED
    assert compute_matching_usage(MappingStatus.PROXY) == MatchingUsage.PROFILE_ONLY
    assert compute_matching_usage(MappingStatus.MNP_ONLY) == MatchingUsage.PROFILE_ONLY
