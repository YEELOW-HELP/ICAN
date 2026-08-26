"""Retrieval service layer, aliases/search, locale-readiness, PII
independence (brief §17/§18/§21, §25 F/O/P/Q).
"""

import pytest

from app.db.models_knowledge import CareerDomain
from app.services.exceptions import CareerNotFoundError
from app.services.knowledge.careers import add_career_alias, create_career
from app.services.knowledge.retrieval import (
    find_careers,
    get_career,
    get_career_by_code,
    get_career_details,
    search_careers,
)
from app.services.knowledge.seed import ensure_seed_knowledge_base
from app.services.knowledge.versioning import create_draft_version, publish_version


async def test_get_career_by_code_uses_current_version_by_default(session_factory):
    async with session_factory() as session:
        version = await ensure_seed_knowledge_base(session)
        career = await get_career_by_code(session, "software_developer")
        assert career.knowledge_base_version_id == version.id
        assert career.code == "software_developer"


async def test_get_career_by_nonexistent_code_raises(session_factory):
    async with session_factory() as session:
        await ensure_seed_knowledge_base(session)
        with pytest.raises(CareerNotFoundError):
            await get_career_by_code(session, "does_not_exist")


async def test_find_careers_filters_by_domain(session_factory):
    async with session_factory() as session:
        await ensure_seed_knowledge_base(session)
        results = await find_careers(session, domain=CareerDomain.HEALTHCARE)
        assert len(results) == 2
        assert all(c.domain == CareerDomain.HEALTHCARE for c in results)


async def test_find_careers_filters_by_structured_characteristics(session_factory):
    async with session_factory() as session:
        await ensure_seed_knowledge_base(session)
        highly_people_facing = await find_careers(session, min_characteristics={"works_with_people": 0.85})
        assert len(highly_people_facing) > 0
        assert all(c.works_with_people >= 0.85 for c in highly_people_facing)

        low_data_focus = await find_careers(session, max_characteristics={"works_with_data": 0.2})
        assert all(c.works_with_data is None or c.works_with_data <= 0.2 for c in low_data_focus)


async def test_search_careers_by_ukrainian_alias_case_insensitive(session_factory):
    async with session_factory() as session:
        await ensure_seed_knowledge_base(session)
        results = await search_careers(session, "розробник")
        codes = {c.code for c in results}
        assert "software_developer" in codes


async def test_search_careers_by_canonical_title(session_factory):
    async with session_factory() as session:
        await ensure_seed_knowledge_base(session)
        results = await search_careers(session, "Медична сестра")
        codes = {c.code for c in results}
        assert "registered_nurse" in codes


async def test_search_careers_by_english_locale_alias(session_factory):
    async with session_factory() as session:
        version = await ensure_seed_knowledge_base(session)
        career = await get_career_by_code(session, "software_developer")

        results = await search_careers(session, "Software Developer", locale="en")
        codes = {c.code for c in results}
        assert "software_developer" in codes


async def test_search_returns_empty_for_unrelated_query(session_factory):
    async with session_factory() as session:
        await ensure_seed_knowledge_base(session)
        results = await search_careers(session, "xyzunrelatedqueryzzz")
        assert results == []


async def test_get_career_details_bundles_everything(session_factory):
    async with session_factory() as session:
        await ensure_seed_knowledge_base(session)
        career = await get_career_by_code(session, "electrician")
        details = await get_career_details(session, career.id)

        assert details.career.id == career.id
        assert len(details.aliases) >= 1
        assert len(details.skills) >= 1
        assert details.work_context is not None
        assert len(details.requirements) >= 1


async def test_retrieval_defaults_to_current_version_even_after_republish(session_factory):
    async with session_factory() as session:
        v1 = await ensure_seed_knowledge_base(session)

        v2_draft = await create_draft_version(session)
        await create_career(
            session, knowledge_base_version_id=v2_draft.id, code="new_career_only_in_v2",
            title_uk="Нова кар'єра", short_description="...", domain=CareerDomain.TECHNOLOGY,
        )
        v2 = await publish_version(session, v2_draft.id)

        # v1's software_developer no longer resolves as "current" by code lookup
        with pytest.raises(CareerNotFoundError):
            await get_career_by_code(session, "software_developer")  # only exists in v1, not v2

        # but it is still directly reachable/queryable by explicit version
        old_career = await get_career_by_code(session, "software_developer", knowledge_base_version_id=v1.id)
        assert old_career.knowledge_base_version_id == v1.id


def test_knowledge_models_have_no_foreign_key_into_user_or_assessment_tables():
    """Bounded-domain separation (brief §21): Career Knowledge must never
    reference identity_users/interview_sessions/evidence/profile_claims."""
    from app.db import models_knowledge

    forbidden_targets = {"identity_users", "interview_sessions", "evidence", "profile_claims", "potential_profiles", "answers"}
    knowledge_tables = [
        t for t in models_knowledge.Base.metadata.tables.values() if t.name.startswith(("career", "knowledge_"))
    ]
    assert len(knowledge_tables) >= 8  # sanity: the Stage 3A tables are actually present
    for table in knowledge_tables:
        for fk in table.foreign_keys:
            assert fk.column.table.name not in forbidden_targets, (
                f"{table.name}.{fk.parent.name} references {fk.column.table.name} -- Career Knowledge must stay a separate bounded domain"
            )
