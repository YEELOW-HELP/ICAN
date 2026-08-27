"""Career records, skill links, requirements, relations, provenance
enforcement (brief §7-13, §25 E/G/H/I/J/K/L).
"""

from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.models_knowledge import (
    CareerDomain,
    FactVerificationState,
    RelationType,
    RequirementCategory,
    RequirementCertainty,
    SkillRequirementType,
)
from app.services.exceptions import (
    CrossVersionRelationError,
    DuplicateCareerCodeError,
    HardFactualRequirementRequiresSourceError,
    KnowledgeBaseVersionNotDraftError,
    MarketSensitiveFactRequiresSourceError,
)
from app.services.knowledge.careers import (
    add_career_alias,
    add_career_fact,
    add_career_relation,
    add_career_requirement,
    add_career_skill,
    create_career,
    create_knowledge_source,
)
from app.services.knowledge.skills import ensure_skills_taxonomy, get_skill_term_by_key
from app.services.knowledge.versioning import create_draft_version, publish_version


async def _make_career(session, code="test_career", domain=CareerDomain.TECHNOLOGY, kb_version=None):
    if kb_version is None:
        kb_version = await create_draft_version(session)
    career = await create_career(
        session, knowledge_base_version_id=kb_version.id, code=code, title_uk="Тестова кар'єра",
        short_description="Опис.", domain=domain,
    )
    return career, kb_version


async def test_career_code_is_unique_within_a_version(session_factory):
    async with session_factory() as session:
        _, kb_version = await _make_career(session, code="dup")
        with pytest.raises(DuplicateCareerCodeError):
            await create_career(
                session, knowledge_base_version_id=kb_version.id, code="dup", title_uk="Інша назва",
                short_description="...", domain=CareerDomain.FINANCE,
            )


async def test_same_code_allowed_across_different_versions(session_factory):
    async with session_factory() as session:
        career1, kb_version1 = await _make_career(session, code="repeatable")
        await publish_version(session, kb_version1.id)
        kb_version2 = await create_draft_version(session)
        career2 = await create_career(
            session, knowledge_base_version_id=kb_version2.id, code="repeatable", title_uk="Тест",
            short_description="...", domain=CareerDomain.TECHNOLOGY,
        )
        assert career1.id != career2.id
        assert career1.code == career2.code


async def test_cannot_add_career_to_a_published_version(session_factory):
    async with session_factory() as session:
        kb_version = await create_draft_version(session)
        published = await publish_version(session, kb_version.id)
        with pytest.raises(KnowledgeBaseVersionNotDraftError):
            await create_career(
                session, knowledge_base_version_id=published.id, code="too_late", title_uk="X",
                short_description="...", domain=CareerDomain.TECHNOLOGY,
            )


async def test_career_alias_search_normalization_is_case_insensitive(session_factory):
    async with session_factory() as session:
        career, _ = await _make_career(session)
        alias = await add_career_alias(session, career_id=career.id, alias_text="  Розробник ПЗ  ")
        assert alias.normalized_text == "розробник пз"


async def test_career_skill_links_to_taxonomy_term(session_factory):
    async with session_factory() as session:
        career, _ = await _make_career(session)
        skills_version = await ensure_skills_taxonomy(session)
        term = await get_skill_term_by_key(session, taxonomy_version_id=skills_version.id, term_key="programming")

        career_skill = await add_career_skill(
            session, career_id=career.id, skill_term_id=term.id, requirement_type=SkillRequirementType.REQUIRED
        )
        assert career_skill.skill_term_id == term.id
        assert career_skill.requirement_type == SkillRequirementType.REQUIRED


async def test_hard_factual_requirement_without_source_is_rejected(session_factory):
    async with session_factory() as session:
        career, _ = await _make_career(session)
        with pytest.raises(HardFactualRequirementRequiresSourceError):
            await add_career_requirement(
                session, career_id=career.id, category=RequirementCategory.LICENSE,
                description="Requires a license.", certainty=RequirementCertainty.HARD_FACTUAL,
            )


async def test_hard_factual_requirement_with_source_is_accepted(session_factory):
    async with session_factory() as session:
        career, _ = await _make_career(session)
        source = await create_knowledge_source(
            session, source_type="government", publisher="Ministry of Health", title="Licensing regulation"
        )
        requirement = await add_career_requirement(
            session, career_id=career.id, category=RequirementCategory.LICENSE,
            description="Requires a license.", certainty=RequirementCertainty.HARD_FACTUAL, source_id=source.id,
        )
        assert requirement.source_id == source.id


async def test_typical_recommendation_requirement_does_not_need_a_source(session_factory):
    async with session_factory() as session:
        career, _ = await _make_career(session)
        requirement = await add_career_requirement(
            session, career_id=career.id, category=RequirementCategory.EDUCATION,
            description="A degree is typically expected.", certainty=RequirementCertainty.TYPICAL_RECOMMENDATION,
        )
        assert requirement.source_id is None


async def test_market_sensitive_fact_without_source_is_rejected(session_factory):
    async with session_factory() as session:
        career, _ = await _make_career(session)
        with pytest.raises(MarketSensitiveFactRequiresSourceError):
            await add_career_fact(
                session, career_id=career.id, fact_type="salary_range", value_text="high",
                is_market_sensitive=True,
            )


async def test_market_sensitive_fact_without_as_of_date_is_rejected(session_factory):
    async with session_factory() as session:
        career, _ = await _make_career(session)
        source = await create_knowledge_source(session, source_type="industry_report", publisher="X", title="Y")
        with pytest.raises(MarketSensitiveFactRequiresSourceError):
            await add_career_fact(
                session, career_id=career.id, fact_type="salary_range", value_text="high",
                is_market_sensitive=True, source_id=source.id,
            )


async def test_market_sensitive_fact_with_full_provenance_is_accepted(session_factory):
    async with session_factory() as session:
        career, _ = await _make_career(session)
        source = await create_knowledge_source(session, source_type="industry_report", publisher="X", title="Y")
        fact = await add_career_fact(
            session, career_id=career.id, fact_type="salary_range", value_text="high",
            is_market_sensitive=True, source_id=source.id, as_of_date=date(2026, 1, 1),
            verification_state=FactVerificationState.VERIFIED,
        )
        assert fact.is_market_sensitive is True
        assert fact.source_id == source.id
        assert fact.as_of_date == date(2026, 1, 1)


async def test_non_market_sensitive_fact_does_not_need_a_source(session_factory):
    async with session_factory() as session:
        career, _ = await _make_career(session)
        fact = await add_career_fact(
            session, career_id=career.id, fact_type="work_context.remote_possible", value_text="sometimes",
        )
        assert fact.source_id is None


async def test_career_relation_between_two_careers_in_same_version(session_factory):
    async with session_factory() as session:
        kb_version = await create_draft_version(session)
        career_a, _ = await _make_career(session, code="a", kb_version=kb_version)
        career_b, _ = await _make_career(session, code="b", kb_version=kb_version)

        relation = await add_career_relation(
            session, from_career_id=career_a.id, to_career_id=career_b.id, relation_type=RelationType.ADJACENT_TO
        )
        assert relation.from_career_id == career_a.id
        assert relation.to_career_id == career_b.id


async def test_career_relation_across_different_versions_is_rejected(session_factory):
    async with session_factory() as session:
        career_a, kb_version1 = await _make_career(session, code="a")
        await publish_version(session, kb_version1.id)
        kb_version2 = await create_draft_version(session)
        career_b, _ = await _make_career(session, code="b", kb_version=kb_version2)

        with pytest.raises(CrossVersionRelationError):
            await add_career_relation(
                session, from_career_id=career_a.id, to_career_id=career_b.id, relation_type=RelationType.RELATED_TO
            )


async def test_duplicate_relation_triple_is_rejected_at_db_level(session_factory):
    async with session_factory() as session:
        kb_version = await create_draft_version(session)
        career_a, _ = await _make_career(session, code="a", kb_version=kb_version)
        career_b, _ = await _make_career(session, code="b", kb_version=kb_version)

        await add_career_relation(
            session, from_career_id=career_a.id, to_career_id=career_b.id, relation_type=RelationType.ADJACENT_TO
        )

        from app.db.models_knowledge import CareerRelation

        session.add(CareerRelation(from_career_id=career_a.id, to_career_id=career_b.id, relation_type=RelationType.ADJACENT_TO))
        with pytest.raises(IntegrityError):
            await session.commit()


async def test_source_provenance_answers_where_did_this_come_from(session_factory):
    """Every source-backed factual assertion must be traceable to a
    KnowledgeSource -- verified end to end via get_sources_for_career."""
    from app.services.knowledge.retrieval import get_sources_for_career

    async with session_factory() as session:
        career, _ = await _make_career(session)
        source = await create_knowledge_source(session, source_type="government", publisher="X", title="Y")
        await add_career_requirement(
            session, career_id=career.id, category=RequirementCategory.LICENSE, description="...",
            certainty=RequirementCertainty.HARD_FACTUAL, source_id=source.id,
        )

        sources = await get_sources_for_career(session, career.id)
        assert len(sources) == 1
        assert sources[0].id == source.id


async def test_direct_orm_write_bypasses_provenance_guards_this_is_why_the_service_layer_is_the_contract(session_factory):
    """Founder-approved write-path contract (docs/engineering/16_...md
    section 13): HARD_FACTUAL/market-sensitive provenance is enforced in
    app/services/knowledge/careers.py, NOT by a DB CHECK constraint --
    consistent with this codebase's existing enforcement-at-the-service-
    layer convention (RBAC, idempotency, etc.). This test makes that
    trade-off's real consequence visible in the suite itself: a direct
    ORM write that skips careers.add_career_fact() entirely bypasses the
    guard it would otherwise hit. This is not a bug to fix -- it is the
    reason every future handler/API/Admin curation surface MUST mutate
    these entities exclusively through app/services/knowledge/*, never
    via a direct session.add()/execute() from outside that module."""
    from app.db.models_knowledge import CareerFact

    async with session_factory() as session:
        career, _ = await _make_career(session)

        # The approved path rejects this exact shape:
        with pytest.raises(MarketSensitiveFactRequiresSourceError):
            await add_career_fact(
                session, career_id=career.id, fact_type="salary_range", value_text="high",
                is_market_sensitive=True,
            )

        # A direct ORM write constructing the identical, guard-violating
        # row succeeds -- proving the guard lives in the service function,
        # not the schema, and therefore must never be bypassed in practice.
        bypassed = CareerFact(
            career_id=career.id, knowledge_base_version_id=career.knowledge_base_version_id,
            fact_type="salary_range", value_text="high", is_market_sensitive=True,
            verification_state=FactVerificationState.UNVERIFIED, source_id=None,
        )
        session.add(bypassed)
        await session.commit()  # succeeds -- no DB-level CHECK exists to stop it
        assert bypassed.source_id is None
        assert bypassed.is_market_sensitive is True
