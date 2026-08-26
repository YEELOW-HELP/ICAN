"""Stage 3A curated seed (brief §15/§25 M/N): idempotent, no duplicates,
diverse, structurally sound end to end.
"""

from sqlalchemy import select

from app.db.models_knowledge import (
    Career,
    CareerAlias,
    CareerRelation,
    CareerRequirement,
    CareerSkill,
    CareerWorkContext,
    KnowledgeBaseVersion,
    KnowledgeBaseVersionStatus,
    RequirementCertainty,
)
from app.services.knowledge.seed import ensure_seed_knowledge_base


async def test_seed_creates_expected_number_of_careers_across_domains(session_factory):
    async with session_factory() as session:
        version = await ensure_seed_knowledge_base(session)

        assert version.status == KnowledgeBaseVersionStatus.PUBLISHED
        assert version.is_current is True

        careers = (await session.execute(select(Career).where(Career.knowledge_base_version_id == version.id))).scalars().all()
        assert 30 <= len(careers) <= 50

        domains = {c.domain for c in careers}
        assert len(domains) >= 10  # broad diversity, not a narrow cluster


async def test_seed_is_idempotent_no_duplicate_careers(session_factory):
    async with session_factory() as session:
        first = await ensure_seed_knowledge_base(session)
        second = await ensure_seed_knowledge_base(session)

        assert first.id == second.id

        versions = (await session.execute(select(KnowledgeBaseVersion))).scalars().all()
        assert len(versions) == 1

        careers = (await session.execute(select(Career))).scalars().all()
        codes = [c.code for c in careers]
        assert len(codes) == len(set(codes))


async def test_seed_populates_aliases_skills_and_work_context_for_every_career(session_factory):
    async with session_factory() as session:
        version = await ensure_seed_knowledge_base(session)
        careers = (await session.execute(select(Career).where(Career.knowledge_base_version_id == version.id))).scalars().all()

        for career in careers:
            aliases = (await session.execute(select(CareerAlias).where(CareerAlias.career_id == career.id))).scalars().all()
            assert len(aliases) >= 1

            skills = (await session.execute(select(CareerSkill).where(CareerSkill.career_id == career.id))).scalars().all()
            assert len(skills) >= 1

            work_context = (
                await session.execute(select(CareerWorkContext).where(CareerWorkContext.career_id == career.id))
            ).scalar_one_or_none()
            assert work_context is not None


async def test_seed_requirements_never_use_hard_factual_without_a_source(session_factory):
    async with session_factory() as session:
        await ensure_seed_knowledge_base(session)
        requirements = (await session.execute(select(CareerRequirement))).scalars().all()
        assert len(requirements) > 0
        for requirement in requirements:
            if requirement.certainty == RequirementCertainty.HARD_FACTUAL:
                assert requirement.source_id is not None


async def test_seed_has_no_market_sensitive_facts(session_factory):
    from app.db.models_knowledge import CareerFact

    async with session_factory() as session:
        await ensure_seed_knowledge_base(session)
        facts = (await session.execute(select(CareerFact))).scalars().all()
        assert all(not f.is_market_sensitive for f in facts)


async def test_seed_relations_reference_real_careers_in_same_version(session_factory):
    async with session_factory() as session:
        version = await ensure_seed_knowledge_base(session)
        relations = (await session.execute(select(CareerRelation))).scalars().all()
        assert len(relations) > 0

        career_ids = {
            row[0] for row in (await session.execute(select(Career.id).where(Career.knowledge_base_version_id == version.id))).all()
        }
        for relation in relations:
            assert relation.from_career_id in career_ids
            assert relation.to_career_id in career_ids
