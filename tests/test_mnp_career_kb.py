"""MNP V1 BLOCK A -- Career Knowledge Base: CRUD, lifecycle transitions,
audit trail, and the 5-career vertical slice seed."""

import pytest
from sqlalchemy import select

from app.db.models_career_card import SkillAliasType, SkillStatus, SkillType
from app.db.models_career_kb_mnp import CareerLifecycleStatus, MnpCareer
from app.db.models_platform import AuditLog
from app.services.career_kb_mnp.careers import (
    create_career,
    get_career_by_code,
    get_or_create_career_family,
    transition_career_status,
)
from app.services.career_kb_mnp.seed_alpha import ALPHA_CAREER_CODES, seed_alpha_career_kb
from app.services.career_kb_mnp.skills import (
    activate_skill,
    add_skill_alias,
    create_skill,
    queue_unmapped_phrase,
    resolve_phrase,
)
from app.services.exceptions import (
    MnpCareerNotFoundError,
    MnpDuplicateCareerCodeError,
    MnpInvalidLifecycleTransitionError,
)


async def test_create_career_and_lookup(session):
    family = await get_or_create_career_family(session, code="sales", name_uk="Продажі", name_en="Sales")
    career = await create_career(
        session, code="test_role", canonical_name_uk="Тестова роль", canonical_name_en="Test Role",
        description_short_uk="desc", career_family=family,
    )
    await session.commit()
    assert career.status == CareerLifecycleStatus.DRAFT
    assert career.career_profile_version == 1

    found = await get_career_by_code(session, "test_role")
    assert found.id == career.id

    with pytest.raises(MnpCareerNotFoundError):
        await get_career_by_code(session, "does_not_exist")


async def test_duplicate_career_code_rejected(session):
    family = await get_or_create_career_family(session, code="sales", name_uk="Продажі", name_en="Sales")
    await create_career(
        session, code="dup_role", canonical_name_uk="A", canonical_name_en="A", description_short_uk="d",
        career_family=family,
    )
    await session.commit()
    with pytest.raises(MnpDuplicateCareerCodeError):
        await create_career(
            session, code="dup_role", canonical_name_uk="B", canonical_name_en="B", description_short_uk="d",
            career_family=family,
        )


async def test_lifecycle_transitions_enforced(session):
    """Only the documented DRAFT->VALIDATED->ACTIVE->REVIEW_DUE->
    ACTIVE/ARCHIVED (+ restore) transitions are allowed -- a skip (DRAFT
    straight to ACTIVE) is rejected."""

    family = await get_or_create_career_family(session, code="sales", name_uk="Продажі", name_en="Sales")
    career = await create_career(
        session, code="lifecycle_role", canonical_name_uk="A", canonical_name_en="A", description_short_uk="d",
        career_family=family,
    )
    await session.commit()

    with pytest.raises(MnpInvalidLifecycleTransitionError):
        await transition_career_status(session, career, to_status=CareerLifecycleStatus.ACTIVE)

    await transition_career_status(session, career, to_status=CareerLifecycleStatus.VALIDATED)
    await transition_career_status(session, career, to_status=CareerLifecycleStatus.ACTIVE)
    assert career.published_at is not None

    await transition_career_status(session, career, to_status=CareerLifecycleStatus.ARCHIVED)
    assert career.status == CareerLifecycleStatus.ARCHIVED

    # Restore.
    await transition_career_status(session, career, to_status=CareerLifecycleStatus.ACTIVE)
    assert career.status == CareerLifecycleStatus.ACTIVE


async def test_career_lifecycle_changes_are_audited(session):
    family = await get_or_create_career_family(session, code="sales", name_uk="Продажі", name_en="Sales")
    career = await create_career(
        session, code="audited_role", canonical_name_uk="A", canonical_name_en="A", description_short_uk="d",
        career_family=family, actor_admin_id=None,
    )
    await session.commit()
    await transition_career_status(session, career, to_status=CareerLifecycleStatus.VALIDATED)

    logs = (
        await session.execute(select(AuditLog).where(AuditLog.entity_id == str(career.id)))
    ).scalars().all()
    actions = {log.action for log in logs}
    assert "created" in actions
    assert "status_changed_to_validated" in actions


async def test_skill_unknown_phrase_never_autocreates_canonical_skill(session):
    """SS-FQ-004 (approved): an unresolved phrase goes to the review
    queue, never auto-creates a new canonical MnpSkill."""

    skill = await resolve_phrase(session, "a phrase nobody ever aliased")
    assert skill is None

    from app.db.models_career_card import MnpSkill

    count_before = len((await session.execute(select(MnpSkill))).scalars().all())
    queued = await queue_unmapped_phrase(
        session, career_card_id=__import__("uuid").uuid4(), raw_phrase="a phrase nobody ever aliased"
    )
    await session.commit()
    count_after = len((await session.execute(select(MnpSkill))).scalars().all())
    assert count_before == count_after
    assert queued.raw_phrase == "a phrase nobody ever aliased"


async def test_skill_alias_resolution_case_and_punctuation_insensitive(session):
    skill = await create_skill(
        session, canonical_name_en="Microsoft Excel", canonical_name_uk="Excel", skill_type=SkillType.TOOL,
        taxonomy_version="v_test",
    )
    await activate_skill(session, skill)
    await add_skill_alias(session, skill, alias="MS Excel", language="uk", alias_type=SkillAliasType.ABBREVIATION)
    await session.commit()

    resolved = await resolve_phrase(session, "ms  excel!!")
    assert resolved is not None
    assert resolved.id == skill.id


async def test_archived_skill_not_resolved(session):
    from app.services.career_kb_mnp.skills import archive_skill

    skill = await create_skill(
        session, canonical_name_en="Old Tool", canonical_name_uk="Старий інструмент", skill_type=SkillType.TOOL,
        taxonomy_version="v_test",
    )
    await add_skill_alias(session, skill, alias="старий інструмент", language="uk", alias_type=SkillAliasType.EXACT_SYNONYM)
    await archive_skill(session, skill)
    await session.commit()

    resolved = await resolve_phrase(session, "старий інструмент")
    assert resolved is None


# ---------------------------------------------------------------------------
# 5-career vertical slice

async def test_seed_alpha_career_kb_creates_5_active_careers(session):
    from app.db.models_career_kb_mnp import MnpCareerAlias, MnpCareerSkillRequirement, MnpCareerTask

    await seed_alpha_career_kb(session)

    for code in ALPHA_CAREER_CODES:
        career = await get_career_by_code(session, code)
        assert career.status == CareerLifecycleStatus.ACTIVE
        assert career.market_data_limited is True  # honest -- no fabricated market data seeded

        skill_reqs = (
            await session.execute(select(MnpCareerSkillRequirement).where(MnpCareerSkillRequirement.career_id == career.id))
        ).scalars().all()
        tasks = (await session.execute(select(MnpCareerTask).where(MnpCareerTask.career_id == career.id))).scalars().all()
        aliases = (
            await session.execute(select(MnpCareerAlias).where(MnpCareerAlias.career_id == career.id))
        ).scalars().all()
        assert skill_reqs != []
        assert tasks != []
        assert aliases != []


async def test_seed_alpha_career_kb_is_idempotent(session):
    await seed_alpha_career_kb(session)
    result1 = await session.execute(select(MnpCareer))
    count1 = len(result1.scalars().all())

    await seed_alpha_career_kb(session)
    result2 = await session.execute(select(MnpCareer))
    count2 = len(result2.scalars().all())

    assert count1 == count2 == len(ALPHA_CAREER_CODES)


async def test_seed_alpha_no_fabricated_market_data(session):
    """MNP_UA_MARKET_DATA_MODEL_V1 "Rules": no unsupported salary/demand
    claims -- confirms zero MnpMarketSnapshot rows exist after seeding."""

    from app.db.models_career_kb_mnp import MnpMarketSnapshot

    await seed_alpha_career_kb(session)
    snapshots = (await session.execute(select(MnpMarketSnapshot))).scalars().all()
    assert snapshots == []
