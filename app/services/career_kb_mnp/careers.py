"""MNP V1 -- Career CRUD, lifecycle, requirements, aliases, relations,
external mappings (`MNP_CAREER_PROFILE_SCHEMA_V1`,
`MNP_CAREER_KB_ARCHITECTURE_V1`). Adding/editing/archiving a career never
requires a Matching Engine code change (BLOCK C reads whatever is
currently ACTIVE)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_career_kb_mnp import (
    CareerAliasType,
    CareerLifecycleStatus,
    CareerRelationType,
    ExternalMappingType,
    ExternalSourceSystem,
    ImportanceLevel,
    MnpCareer,
    MnpCareerAlias,
    MnpCareerAttribute,
    MnpCareerFamily,
    MnpCareerKnowledgeRequirement,
    MnpCareerRelation,
    MnpCareerRequirement,
    MnpCareerSkillRequirement,
    MnpCareerTask,
    MnpExternalMapping,
    RequirementCategory,
    RequirementHardness,
    RequirementType,
)
from app.services.audit import record_audit
from app.services.exceptions import (
    MnpCareerNotFoundError,
    MnpDuplicateCareerCodeError,
    MnpInvalidLifecycleTransitionError,
)

# MNP_CAREER_KB_ARCHITECTURE_V1 "Lifecycle": DRAFT -> VALIDATED -> ACTIVE
# -> REVIEW_DUE -> ACTIVE/ARCHIVED. ARCHIVED -> ACTIVE is "restore"
# (explicit action, not a normal forward transition, but reachable the
# same way).
_ALLOWED_TRANSITIONS: dict[CareerLifecycleStatus, set[CareerLifecycleStatus]] = {
    CareerLifecycleStatus.DRAFT: {CareerLifecycleStatus.VALIDATED},
    CareerLifecycleStatus.VALIDATED: {CareerLifecycleStatus.ACTIVE, CareerLifecycleStatus.DRAFT},
    CareerLifecycleStatus.ACTIVE: {CareerLifecycleStatus.REVIEW_DUE, CareerLifecycleStatus.ARCHIVED},
    CareerLifecycleStatus.REVIEW_DUE: {CareerLifecycleStatus.ACTIVE, CareerLifecycleStatus.ARCHIVED},
    CareerLifecycleStatus.ARCHIVED: {CareerLifecycleStatus.ACTIVE},  # restore
}


async def get_or_create_career_family(
    session: AsyncSession, *, code: str, name_uk: str, name_en: str
) -> MnpCareerFamily:
    existing = await session.execute(select(MnpCareerFamily).where(MnpCareerFamily.code == code))
    found = existing.scalar_one_or_none()
    if found is not None:
        return found
    family = MnpCareerFamily(code=code, name_uk=name_uk, name_en=name_en)
    session.add(family)
    await session.flush()
    return family


async def get_career_by_code(session: AsyncSession, code: str) -> MnpCareer:
    result = await session.execute(select(MnpCareer).where(MnpCareer.code == code))
    career = result.scalar_one_or_none()
    if career is None:
        raise MnpCareerNotFoundError(f"no MnpCareer with code={code!r}")
    return career


async def create_career(
    session: AsyncSession,
    *,
    code: str,
    canonical_name_uk: str,
    canonical_name_en: str,
    description_short_uk: str,
    career_family: MnpCareerFamily,
    description_long_uk: str | None = None,
    catalog_priority: int = 0,
    actor_admin_id: int | None = None,
) -> MnpCareer:
    existing = await session.execute(select(MnpCareer).where(MnpCareer.code == code))
    if existing.scalar_one_or_none() is not None:
        raise MnpDuplicateCareerCodeError(f"MnpCareer code={code!r} already exists")

    career = MnpCareer(
        code=code,
        canonical_name_uk=canonical_name_uk,
        canonical_name_en=canonical_name_en,
        description_short_uk=description_short_uk,
        description_long_uk=description_long_uk,
        career_family_id=career_family.id,
        status=CareerLifecycleStatus.DRAFT,
        catalog_priority=catalog_priority,
        career_profile_version=1,
    )
    session.add(career)
    await session.flush()
    await record_audit(
        session, entity_type="mnp_career", entity_id=str(career.id), action="created",
        actor_admin_id=actor_admin_id, after={"code": code, "status": "draft"},
    )
    return career


async def transition_career_status(
    session: AsyncSession, career: MnpCareer, *, to_status: CareerLifecycleStatus, actor_admin_id: int | None = None,
    reason: str | None = None,
) -> MnpCareer:
    allowed = _ALLOWED_TRANSITIONS.get(career.status, set())
    if to_status not in allowed:
        raise MnpInvalidLifecycleTransitionError(
            f"cannot move MnpCareer {career.code!r} from {career.status.value} to {to_status.value}"
        )
    before = {"status": career.status.value}
    career.status = to_status
    if to_status == CareerLifecycleStatus.ACTIVE and career.published_at is None:
        career.published_at = datetime.now(timezone.utc)
    if to_status == CareerLifecycleStatus.REVIEW_DUE:
        career.reviewed_at = datetime.now(timezone.utc)
    await session.flush()
    await record_audit(
        session, entity_type="mnp_career", entity_id=str(career.id),
        action=f"status_changed_to_{to_status.value}",
        actor_admin_id=actor_admin_id, before=before, after={"status": to_status.value, "reason": reason},
    )
    return career


async def bump_career_profile_version(
    session: AsyncSession, career: MnpCareer, *, actor_admin_id: int | None = None, change_summary: str,
) -> MnpCareer:
    """Any substantive edit to a career's requirements/attributes/tasks
    calls this -- per-career versioning (MNP_CAREER_PROFILE_SCHEMA_V1
    §29), independent of every other career's version."""

    before_version = career.career_profile_version
    career.career_profile_version += 1
    await session.flush()
    await record_audit(
        session, entity_type="mnp_career", entity_id=str(career.id), action="profile_version_bumped",
        actor_admin_id=actor_admin_id,
        before={"career_profile_version": before_version}, after={
            "career_profile_version": career.career_profile_version, "change_summary": change_summary,
        },
    )
    return career


async def add_career_alias(
    session: AsyncSession, career: MnpCareer, *, alias: str, language: str = "uk",
    alias_type: CareerAliasType, source: str | None = None, confidence: float | None = None,
) -> MnpCareerAlias:
    existing = await session.execute(
        select(MnpCareerAlias).where(
            MnpCareerAlias.career_id == career.id, MnpCareerAlias.language == language, MnpCareerAlias.alias == alias
        )
    )
    found = existing.scalar_one_or_none()
    if found is not None:
        return found
    row = MnpCareerAlias(
        career_id=career.id, alias=alias, language=language, alias_type=alias_type,
        source=source, confidence=confidence, status=CareerLifecycleStatus.ACTIVE,
    )
    session.add(row)
    await session.flush()
    return row


async def add_career_task(
    session: AsyncSession, career: MnpCareer, *, task_code: str, title_uk: str, importance: ImportanceLevel,
    title_en: str | None = None, description: str | None = None, source: str | None = None,
    source_version: str | None = None, confidence: float | None = None,
) -> MnpCareerTask:
    row = MnpCareerTask(
        career_id=career.id, task_code=task_code, title_uk=title_uk, title_en=title_en,
        description=description, importance=importance, source=source, source_version=source_version,
        confidence=confidence,
    )
    session.add(row)
    await session.flush()
    return row


async def add_skill_requirement(
    session: AsyncSession, career: MnpCareer, skill_id: uuid.UUID, *, importance: ImportanceLevel,
    required_level: str, requirement_type: RequirementType, source: str | None = None,
    source_version: str | None = None, confidence: float = 0.5,
) -> MnpCareerSkillRequirement:
    existing = await session.execute(
        select(MnpCareerSkillRequirement).where(
            MnpCareerSkillRequirement.career_id == career.id, MnpCareerSkillRequirement.skill_id == skill_id
        )
    )
    found = existing.scalar_one_or_none()
    if found is not None:
        return found
    row = MnpCareerSkillRequirement(
        career_id=career.id, skill_id=skill_id, importance=importance, required_level=required_level,
        requirement_type=requirement_type, source=source, source_version=source_version, confidence=confidence,
    )
    session.add(row)
    await session.flush()
    return row


async def add_knowledge_requirement(
    session: AsyncSession, career: MnpCareer, knowledge_id: uuid.UUID, *, importance: ImportanceLevel,
    required_level: str, requirement_type: RequirementType, source: str | None = None, confidence: float = 0.5,
) -> MnpCareerKnowledgeRequirement:
    existing = await session.execute(
        select(MnpCareerKnowledgeRequirement).where(
            MnpCareerKnowledgeRequirement.career_id == career.id,
            MnpCareerKnowledgeRequirement.knowledge_id == knowledge_id,
        )
    )
    found = existing.scalar_one_or_none()
    if found is not None:
        return found
    row = MnpCareerKnowledgeRequirement(
        career_id=career.id, knowledge_id=knowledge_id, importance=importance, required_level=required_level,
        requirement_type=requirement_type, source=source, confidence=confidence,
    )
    session.add(row)
    await session.flush()
    return row


async def add_requirement(
    session: AsyncSession, career: MnpCareer, *, category: RequirementCategory, description: str,
    hardness: RequirementHardness, value: str | None = None, country: str | None = None,
    source: str | None = None, source_version: str | None = None, confidence: float = 0.5,
) -> MnpCareerRequirement:
    """MNP_EVIDENCE_AND_CONFIDENCE_MODEL_V1 §20: a HARD requirement is
    only ever a real Feasibility BLOCKED input if it also carries a real
    `source` -- callers that want to mark something HARD without a source
    should not (this function doesn't enforce it as a hard invariant like
    Stage 3A's HardFactualRequirementRequiresSourceError, since MNP's
    RequirementHardness is deliberately simpler than Stage 3A's
    certainty model; the Feasibility engine, BLOCK C, is the actual
    enforcement point per MNP_FEASIBILITY_RULES_V1)."""

    row = MnpCareerRequirement(
        career_id=career.id, category=category, description=description, value=value,
        hardness=hardness, country=country, source=source, source_version=source_version, confidence=confidence,
    )
    session.add(row)
    await session.flush()
    return row


async def add_career_attribute(
    session: AsyncSession, career: MnpCareer, *, attribute_group: str, attribute_key: str,
    value_numeric: float | None = None, value_text: str | None = None, source: str | None = None,
    confidence: float | None = None,
) -> MnpCareerAttribute:
    existing = await session.execute(
        select(MnpCareerAttribute).where(
            MnpCareerAttribute.career_id == career.id,
            MnpCareerAttribute.attribute_group == attribute_group,
            MnpCareerAttribute.attribute_key == attribute_key,
        )
    )
    found = existing.scalar_one_or_none()
    if found is not None:
        return found
    row = MnpCareerAttribute(
        career_id=career.id, attribute_group=attribute_group, attribute_key=attribute_key,
        value_numeric=value_numeric, value_text=value_text, source=source, confidence=confidence,
    )
    session.add(row)
    await session.flush()
    return row


async def add_career_relation(
    session: AsyncSession, from_career: MnpCareer, to_career: MnpCareer, *, relation_type: CareerRelationType,
    strength: float | None = None, source: str | None = None,
) -> MnpCareerRelation:
    existing = await session.execute(
        select(MnpCareerRelation).where(
            MnpCareerRelation.from_career_id == from_career.id,
            MnpCareerRelation.to_career_id == to_career.id,
            MnpCareerRelation.relation_type == relation_type,
        )
    )
    found = existing.scalar_one_or_none()
    if found is not None:
        return found
    row = MnpCareerRelation(
        from_career_id=from_career.id, to_career_id=to_career.id, relation_type=relation_type,
        strength=strength, source=source,
    )
    session.add(row)
    await session.flush()
    return row


async def add_external_mapping(
    session: AsyncSession, *, entity_type: str, mnp_entity_id: uuid.UUID, source_system: ExternalSourceSystem,
    external_id: str, mapping_type: ExternalMappingType, external_label: str | None = None,
    confidence: float | None = None, source_version: str | None = None,
) -> MnpExternalMapping:
    """Lightcast is not a valid `source_system` (Founder Decision #18) --
    enforced by `ExternalSourceSystem` simply not defining that member,
    not by a runtime check here."""

    existing = await session.execute(
        select(MnpExternalMapping).where(
            MnpExternalMapping.entity_type == entity_type,
            MnpExternalMapping.mnp_entity_id == mnp_entity_id,
            MnpExternalMapping.source_system == source_system,
            MnpExternalMapping.external_id == external_id,
        )
    )
    found = existing.scalar_one_or_none()
    if found is not None:
        return found
    row = MnpExternalMapping(
        entity_type=entity_type, mnp_entity_id=mnp_entity_id, source_system=source_system,
        external_id=external_id, external_label=external_label, mapping_type=mapping_type,
        confidence=confidence, source_version=source_version,
    )
    session.add(row)
    await session.flush()
    return row
