"""Matching V1 M3 -- Alpha catalog seeding (Founder Review test items
#1-4, #26)."""

from sqlalchemy import select

from app.db.models_career_kb import CareerMatchingProfile
from app.db.models_knowledge import Career
from app.services.career_kb.seed import ALPHA_CAREER_CODES, seed_alpha_career_matching_profiles
from app.services.knowledge.retrieval import get_career_by_code
from app.services.knowledge.seed import ensure_seed_knowledge_base


async def test_alpha_career_catalog_seeds(session):
    """#1."""
    profiles = await seed_alpha_career_matching_profiles(session)
    await session.commit()
    assert len(profiles) == len(ALPHA_CAREER_CODES)


async def test_exact_alpha_career_count_deterministic():
    """#2 -- within the Founder-specified 20-30 range."""
    assert 20 <= len(ALPHA_CAREER_CODES) <= 30
    assert len(ALPHA_CAREER_CODES) == len(set(ALPHA_CAREER_CODES))  # no duplicates
    assert len(ALPHA_CAREER_CODES) == 24


async def test_seed_idempotent(session):
    """#3."""
    profiles_a = await seed_alpha_career_matching_profiles(session)
    await session.commit()
    profiles_b = await seed_alpha_career_matching_profiles(session)
    await session.commit()

    assert {p.id for p in profiles_a} == {p.id for p in profiles_b}

    result = await session.execute(select(CareerMatchingProfile))
    all_profiles = result.scalars().all()
    assert len(all_profiles) == len(ALPHA_CAREER_CODES)  # no duplicates on re-run


async def test_career_code_remains_canonical(session):
    """#4 -- Career.code is untouched; the matching layer only ever reads
    it, never writes to it."""
    await ensure_seed_knowledge_base(session)
    before = await get_career_by_code(session, "software_developer")
    code_before = before.code
    external_onet_id_before = before.external_onet_id

    await seed_alpha_career_matching_profiles(session)
    await session.commit()

    after = await get_career_by_code(session, "software_developer")
    assert after.id == before.id
    assert after.code == code_before
    assert after.external_onet_id == external_onet_id_before  # M3 never populates this legacy single-value field


async def test_stage_3a_career_rows_not_destructively_modified(session):
    """#26 -- every Stage 3A field on every Alpha career is byte-identical
    before and after the M3 seed runs."""
    await ensure_seed_knowledge_base(session)
    result = await session.execute(select(Career))
    before = {c.id: (c.code, c.title_uk, c.domain, c.short_description, c.works_with_people) for c in result.scalars().all()}

    await seed_alpha_career_matching_profiles(session)
    await session.commit()

    result = await session.execute(select(Career))
    after = {c.id: (c.code, c.title_uk, c.domain, c.short_description, c.works_with_people) for c in result.scalars().all()}

    assert before == after
