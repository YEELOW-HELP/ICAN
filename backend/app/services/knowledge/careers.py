"""Career Knowledge Base write-side services (Issue #4). Every mutation
here operates on a DRAFT `KnowledgeBaseVersion` only -- a PUBLISHED
version is immutable (enforced by `versioning.get_draft_version`, which
every function below calls first).

Provenance is enforced here, not left to caller discipline:
- a `CareerRequirement` with `certainty=HARD_FACTUAL` must carry a
  `source_id` (brief §9);
- a `CareerFact` with `is_market_sensitive=True` must carry a `source_id`
  and an `as_of_date` (brief §20) -- "unknown" beats a plausible-looking
  fabrication.
"""

from __future__ import annotations

import re
import uuid
from datetime import date

from sqlalchemy.exc import IntegrityError
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
    FactVerificationState,
    IndoorOutdoor,
    KnowledgeSource,
    RelationType,
    RequirementCategory,
    RequirementCertainty,
    SkillRequirementType,
    SourceStatus,
    TravelRequirement,
    WorkSetting,
)
from app.services.exceptions import (
    CareerNotFoundError,
    CrossVersionRelationError,
    DuplicateCareerCodeError,
    HardFactualRequirementRequiresSourceError,
    MarketSensitiveFactRequiresSourceError,
)
from app.services.knowledge.versioning import get_draft_version

_NORMALIZE_RE = re.compile(r"\s+")


def normalize_alias_text(text: str) -> str:
    return _NORMALIZE_RE.sub(" ", text.strip().casefold())


async def create_knowledge_source(
    session: AsyncSession,
    *,
    source_type: str,
    publisher: str,
    title: str,
    url: str | None = None,
    country_region: str | None = None,
    publication_date: date | None = None,
    trust_level: str | None = None,
    notes: str | None = None,
) -> KnowledgeSource:
    source = KnowledgeSource(
        source_type=source_type, publisher=publisher, title=title, url=url, country_region=country_region,
        publication_date=publication_date, trust_level=trust_level, status=SourceStatus.ACTIVE, notes=notes,
    )
    session.add(source)
    await session.commit()
    await session.refresh(source)
    return source


async def create_career(
    session: AsyncSession,
    *,
    knowledge_base_version_id: uuid.UUID,
    code: str,
    title_uk: str,
    short_description: str,
    domain: CareerDomain,
    title_en: str | None = None,
    typical_activities: str | None = None,
    status: CareerStatus = CareerStatus.ACTIVE,
    works_with_people: float | None = None,
    works_with_data: float | None = None,
    works_with_technology: float | None = None,
    creative_component: float | None = None,
    analytical_component: float | None = None,
    autonomy_level: float | None = None,
    structure_routine_level: float | None = None,
    external_esco_id: str | None = None,
    external_onet_id: str | None = None,
    external_isco_id: str | None = None,
) -> Career:
    await get_draft_version(session, knowledge_base_version_id)  # raises if not a mutable draft

    career = Career(
        knowledge_base_version_id=knowledge_base_version_id, code=code, title_uk=title_uk, title_en=title_en,
        domain=domain, status=status, short_description=short_description, typical_activities=typical_activities,
        works_with_people=works_with_people, works_with_data=works_with_data,
        works_with_technology=works_with_technology, creative_component=creative_component,
        analytical_component=analytical_component, autonomy_level=autonomy_level,
        structure_routine_level=structure_routine_level, external_esco_id=external_esco_id,
        external_onet_id=external_onet_id, external_isco_id=external_isco_id,
    )
    session.add(career)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise DuplicateCareerCodeError(
            f"career code {code!r} already exists in KnowledgeBaseVersion {knowledge_base_version_id}"
        ) from None
    await session.refresh(career)
    return career


async def add_career_alias(
    session: AsyncSession, *, career_id: uuid.UUID, alias_text: str, locale: str = "uk"
) -> CareerAlias:
    career = await _get_career_or_raise(session, career_id)
    await get_draft_version(session, career.knowledge_base_version_id)

    alias = CareerAlias(career_id=career_id, alias_text=alias_text, locale=locale, normalized_text=normalize_alias_text(alias_text))
    session.add(alias)
    await session.commit()
    await session.refresh(alias)
    return alias


async def add_career_skill(
    session: AsyncSession,
    *,
    career_id: uuid.UUID,
    skill_term_id: uuid.UUID,
    requirement_type: SkillRequirementType,
    expected_level: str | None = None,
    source_id: uuid.UUID | None = None,
    notes: str | None = None,
) -> CareerSkill:
    career = await _get_career_or_raise(session, career_id)
    await get_draft_version(session, career.knowledge_base_version_id)

    career_skill = CareerSkill(
        career_id=career_id, skill_term_id=skill_term_id, requirement_type=requirement_type,
        expected_level=expected_level, source_id=source_id, notes=notes,
    )
    session.add(career_skill)
    await session.commit()
    await session.refresh(career_skill)
    return career_skill


async def add_career_requirement(
    session: AsyncSession,
    *,
    career_id: uuid.UUID,
    category: RequirementCategory,
    description: str,
    certainty: RequirementCertainty,
    jurisdiction: str | None = None,
    source_id: uuid.UUID | None = None,
) -> CareerRequirement:
    career = await _get_career_or_raise(session, career_id)
    await get_draft_version(session, career.knowledge_base_version_id)

    if certainty == RequirementCertainty.HARD_FACTUAL and source_id is None:
        raise HardFactualRequirementRequiresSourceError(
            f"requirement {description!r} is marked hard_factual but has no source_id"
        )

    requirement = CareerRequirement(
        career_id=career_id, category=category, description=description, certainty=certainty,
        jurisdiction=jurisdiction, source_id=source_id,
    )
    session.add(requirement)
    await session.commit()
    await session.refresh(requirement)
    return requirement


async def set_career_work_context(
    session: AsyncSession,
    *,
    career_id: uuid.UUID,
    setting: WorkSetting | None = None,
    indoor_outdoor: IndoorOutdoor | None = None,
    travel_required: TravelRequirement | None = None,
    shift_work: bool | None = None,
    physical_intensity: float | None = None,
    teamwork_level: float | None = None,
    customer_interaction_level: float | None = None,
    client_facing: bool | None = None,
    repetitive_vs_varied: float | None = None,
    schedule_predictability: float | None = None,
    responsibility_level: float | None = None,
    stress_level: float | None = None,
) -> CareerWorkContext:
    career = await _get_career_or_raise(session, career_id)
    await get_draft_version(session, career.knowledge_base_version_id)

    work_context = CareerWorkContext(
        career_id=career_id, setting=setting, indoor_outdoor=indoor_outdoor, travel_required=travel_required,
        shift_work=shift_work, physical_intensity=physical_intensity, teamwork_level=teamwork_level,
        customer_interaction_level=customer_interaction_level, client_facing=client_facing,
        repetitive_vs_varied=repetitive_vs_varied, schedule_predictability=schedule_predictability,
        responsibility_level=responsibility_level, stress_level=stress_level,
    )
    session.add(work_context)
    await session.commit()
    await session.refresh(work_context)
    return work_context


async def add_career_relation(
    session: AsyncSession,
    *,
    from_career_id: uuid.UUID,
    to_career_id: uuid.UUID,
    relation_type: RelationType,
    source_id: uuid.UUID | None = None,
    notes: str | None = None,
) -> CareerRelation:
    from_career = await _get_career_or_raise(session, from_career_id)
    to_career = await _get_career_or_raise(session, to_career_id)
    if from_career.knowledge_base_version_id != to_career.knowledge_base_version_id:
        raise CrossVersionRelationError(
            f"careers {from_career_id} and {to_career_id} belong to different KnowledgeBaseVersions"
        )
    await get_draft_version(session, from_career.knowledge_base_version_id)

    relation = CareerRelation(
        from_career_id=from_career_id, to_career_id=to_career_id, relation_type=relation_type,
        source_id=source_id, notes=notes,
    )
    session.add(relation)
    await session.commit()
    await session.refresh(relation)
    return relation


async def add_career_fact(
    session: AsyncSession,
    *,
    career_id: uuid.UUID,
    fact_type: str,
    value_text: str,
    is_market_sensitive: bool = False,
    value_metadata: dict | None = None,
    geography: str | None = None,
    verification_state: FactVerificationState = FactVerificationState.UNVERIFIED,
    source_id: uuid.UUID | None = None,
    as_of_date: date | None = None,
) -> CareerFact:
    career = await _get_career_or_raise(session, career_id)
    await get_draft_version(session, career.knowledge_base_version_id)

    if is_market_sensitive and (source_id is None or as_of_date is None):
        raise MarketSensitiveFactRequiresSourceError(
            f"fact {fact_type!r} on career {career_id} is market-sensitive and requires both source_id and as_of_date"
        )

    fact = CareerFact(
        career_id=career_id, knowledge_base_version_id=career.knowledge_base_version_id, fact_type=fact_type,
        value_text=value_text, value_metadata=value_metadata, geography=geography,
        is_market_sensitive=is_market_sensitive, verification_state=verification_state, source_id=source_id,
        as_of_date=as_of_date,
    )
    session.add(fact)
    await session.commit()
    await session.refresh(fact)
    return fact


async def _get_career_or_raise(session: AsyncSession, career_id: uuid.UUID) -> Career:
    career = await session.get(Career, career_id)
    if career is None:
        raise CareerNotFoundError(f"Career {career_id} does not exist")
    return career
