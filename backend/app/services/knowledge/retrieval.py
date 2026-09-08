"""Career Knowledge Base retrieval (brief §17) -- the only service layer
Stage 3B's future Direction Intelligence should ever query through. No
raw SQL belongs outside this module; no LLM call is required for any
function here (brief §23: Stage 3A retrieval is deterministic).

Every function defaults to the *current published* KnowledgeBaseVersion
unless an explicit `knowledge_base_version_id` is given -- this is what
lets a historical artifact re-query exactly the knowledge it was
generated from, even after the KB has moved on (brief §14).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_knowledge import (
    Career,
    CareerAlias,
    CareerDomain,
    CareerFact,
    CareerRelation,
    CareerRequirement,
    CareerSkill,
    CareerStatus,
    CareerWorkContext,
    KnowledgeSource,
)
from app.services.exceptions import CareerNotFoundError
from app.services.knowledge.careers import normalize_alias_text
from app.services.knowledge.versioning import get_current_knowledge_version

__all__ = [
    "get_current_knowledge_version",
    "get_career",
    "get_career_by_code",
    "find_careers",
    "get_career_details",
    "get_career_skills",
    "get_career_requirements",
    "get_career_relations",
    "get_career_facts",
    "get_sources_for_career",
    "search_careers",
    "CareerDetails",
]


@dataclass(frozen=True)
class CareerDetails:
    career: Career
    aliases: list[CareerAlias] = field(default_factory=list)
    skills: list[CareerSkill] = field(default_factory=list)
    requirements: list[CareerRequirement] = field(default_factory=list)
    work_context: CareerWorkContext | None = None
    relations: list[CareerRelation] = field(default_factory=list)
    facts: list[CareerFact] = field(default_factory=list)


async def _resolve_version_id(session: AsyncSession, knowledge_base_version_id: uuid.UUID | None) -> uuid.UUID:
    if knowledge_base_version_id is not None:
        return knowledge_base_version_id
    current = await get_current_knowledge_version(session)
    return current.id


async def get_career(session: AsyncSession, career_id: uuid.UUID) -> Career:
    career = await session.get(Career, career_id)
    if career is None:
        raise CareerNotFoundError(f"Career {career_id} does not exist")
    return career


async def get_career_by_code(
    session: AsyncSession, code: str, *, knowledge_base_version_id: uuid.UUID | None = None
) -> Career:
    version_id = await _resolve_version_id(session, knowledge_base_version_id)
    result = await session.execute(
        select(Career).where(Career.knowledge_base_version_id == version_id, Career.code == code)
    )
    career = result.scalar_one_or_none()
    if career is None:
        raise CareerNotFoundError(f"Career code {code!r} does not exist in KnowledgeBaseVersion {version_id}")
    return career


async def find_careers(
    session: AsyncSession,
    *,
    knowledge_base_version_id: uuid.UUID | None = None,
    domain: CareerDomain | None = None,
    status: CareerStatus | None = CareerStatus.ACTIVE,
    min_characteristics: dict[str, float] | None = None,
    max_characteristics: dict[str, float] | None = None,
) -> list[Career]:
    """`min_characteristics`/`max_characteristics` filter on Career's own
    float columns by attribute name (e.g. `{"works_with_people": 0.6}`) --
    the "query/filter by structured characteristics" requirement (brief
    §17), without callers ever writing SQL."""
    version_id = await _resolve_version_id(session, knowledge_base_version_id)
    query = select(Career).where(Career.knowledge_base_version_id == version_id)
    if domain is not None:
        query = query.where(Career.domain == domain)
    if status is not None:
        query = query.where(Career.status == status)
    for attr, min_value in (min_characteristics or {}).items():
        query = query.where(getattr(Career, attr) >= min_value)
    for attr, max_value in (max_characteristics or {}).items():
        query = query.where(getattr(Career, attr) <= max_value)

    result = await session.execute(query.order_by(Career.title_uk))
    return list(result.scalars().all())


async def get_career_skills(session: AsyncSession, career_id: uuid.UUID) -> list[CareerSkill]:
    result = await session.execute(select(CareerSkill).where(CareerSkill.career_id == career_id))
    return list(result.scalars().all())


async def get_career_requirements(session: AsyncSession, career_id: uuid.UUID) -> list[CareerRequirement]:
    result = await session.execute(select(CareerRequirement).where(CareerRequirement.career_id == career_id))
    return list(result.scalars().all())


async def get_career_relations(session: AsyncSession, career_id: uuid.UUID) -> list[CareerRelation]:
    """Both directions -- a relation where this career is either the
    source or the target is relevant to it."""
    result = await session.execute(
        select(CareerRelation).where(
            or_(CareerRelation.from_career_id == career_id, CareerRelation.to_career_id == career_id)
        )
    )
    return list(result.scalars().all())


async def get_career_facts(
    session: AsyncSession, career_id: uuid.UUID, *, include_market_sensitive: bool = True
) -> list[CareerFact]:
    query = select(CareerFact).where(CareerFact.career_id == career_id)
    if not include_market_sensitive:
        query = query.where(CareerFact.is_market_sensitive.is_(False))
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_sources_for_career(session: AsyncSession, career_id: uuid.UUID) -> list[KnowledgeSource]:
    """Every KnowledgeSource referenced by any skill/requirement/relation/
    fact attached to this career -- answers "where did this come from?"
    at the whole-career level."""
    source_ids: set[uuid.UUID] = set()
    for skill in await get_career_skills(session, career_id):
        if skill.source_id:
            source_ids.add(skill.source_id)
    for requirement in await get_career_requirements(session, career_id):
        if requirement.source_id:
            source_ids.add(requirement.source_id)
    for relation in await get_career_relations(session, career_id):
        if relation.source_id:
            source_ids.add(relation.source_id)
    for fact in await get_career_facts(session, career_id):
        if fact.source_id:
            source_ids.add(fact.source_id)

    if not source_ids:
        return []
    result = await session.execute(select(KnowledgeSource).where(KnowledgeSource.id.in_(source_ids)))
    return list(result.scalars().all())


async def get_career_details(session: AsyncSession, career_id: uuid.UUID) -> CareerDetails:
    career = await get_career(session, career_id)
    aliases_result = await session.execute(select(CareerAlias).where(CareerAlias.career_id == career_id))
    work_context_result = await session.execute(
        select(CareerWorkContext).where(CareerWorkContext.career_id == career_id)
    )
    return CareerDetails(
        career=career,
        aliases=list(aliases_result.scalars().all()),
        skills=await get_career_skills(session, career_id),
        requirements=await get_career_requirements(session, career_id),
        work_context=work_context_result.scalar_one_or_none(),
        relations=await get_career_relations(session, career_id),
        facts=await get_career_facts(session, career_id),
    )


async def search_careers(
    session: AsyncSession, query_text: str, *, locale: str = "uk", knowledge_base_version_id: uuid.UUID | None = None
) -> list[Career]:
    """Case-insensitive lookup by canonical title OR any alias (brief
    §18). Locale-ready: `locale` filters which aliases are considered,
    but the mechanism (normalized-text equality/prefix match) is not
    Ukrainian-specific -- adding `en`/`de`/`ru` aliases later needs no
    code change here."""
    version_id = await _resolve_version_id(session, knowledge_base_version_id)
    normalized = normalize_alias_text(query_text)

    alias_matches = await session.execute(
        select(CareerAlias.career_id).where(
            CareerAlias.locale == locale, CareerAlias.normalized_text.like(f"%{normalized}%")
        )
    )
    career_ids = {row[0] for row in alias_matches.all()}

    title_column = Career.title_uk if locale == "uk" else Career.title_en
    title_matches = await session.execute(
        select(Career.id).where(Career.knowledge_base_version_id == version_id, title_column.ilike(f"%{query_text}%"))
    )
    career_ids |= {row[0] for row in title_matches.all()}

    if not career_ids:
        return []
    result = await session.execute(
        select(Career).where(Career.id.in_(career_ids), Career.knowledge_base_version_id == version_id).order_by(Career.title_uk)
    )
    return list(result.scalars().all())
