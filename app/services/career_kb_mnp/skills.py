"""MNP V1 -- Skill taxonomy CRUD (`MNP_SKILL_SCHEMA_V1`). ADMIN/EDITOR
operations only; the resume parser and questionnaire (BLOCK B) call
`resolve_phrase` read-only and never create a canonical Skill themselves
(SS-FQ-004, approved: "нет. Unknown phrase -> review queue")."""

from __future__ import annotations

import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_career_card import (
    MnpPersonSkill,
    MnpSkill,
    MnpSkillAlias,
    SkillAliasType,
    MnpUnmappedPhrase,
    SkillStatus,
    SkillType,
)
from app.services.audit import record_audit
from app.services.exceptions import MnpSkillNotFoundError


def normalize_phrase(raw: str) -> str:
    """Deterministic normalization used both when storing an alias and
    when resolving a raw CV/questionnaire phrase against it -- lowercase,
    collapse whitespace, strip punctuation MNP_SKILL_SCHEMA_V1 §8 doesn't
    consider meaningful (so "MS Excel" and "ms excel" match the same
    alias row)."""

    text = raw.strip().lower()
    text = re.sub(r"[^\w\s+#.]", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


async def create_skill(
    session: AsyncSession,
    *,
    canonical_name_en: str,
    canonical_name_uk: str,
    skill_type: SkillType,
    taxonomy_version: str,
    description: str | None = None,
    skill_family: str | None = None,
    actor_admin_id: int | None = None,
) -> MnpSkill:
    skill = MnpSkill(
        canonical_name_en=canonical_name_en,
        canonical_name_uk=canonical_name_uk,
        skill_type=skill_type,
        status=SkillStatus.DRAFT,
        description=description,
        taxonomy_version=taxonomy_version,
        skill_family=skill_family,
    )
    session.add(skill)
    await session.flush()
    await record_audit(
        session, entity_type="mnp_skill", entity_id=str(skill.id), action="created",
        actor_admin_id=actor_admin_id, after={"canonical_name_en": canonical_name_en, "skill_type": skill_type.value},
    )
    return skill


async def activate_skill(session: AsyncSession, skill: MnpSkill, *, actor_admin_id: int | None = None) -> MnpSkill:
    before = {"status": skill.status.value}
    skill.status = SkillStatus.ACTIVE
    await session.flush()
    await record_audit(
        session, entity_type="mnp_skill", entity_id=str(skill.id), action="activated",
        actor_admin_id=actor_admin_id, before=before, after={"status": skill.status.value},
    )
    return skill


async def archive_skill(session: AsyncSession, skill: MnpSkill, *, actor_admin_id: int | None = None) -> MnpSkill:
    """Never a hard delete -- a Skill in use by PersonSkill/
    CareerSkillRequirement rows must stay resolvable for historical
    MatchRuns (MNP_SKILL_SCHEMA_V1 §19: 'Удаление используемого Skill
    запрещено: только ARCHIVED / merge with migration')."""

    before = {"status": skill.status.value}
    skill.status = SkillStatus.ARCHIVED
    await session.flush()
    await record_audit(
        session, entity_type="mnp_skill", entity_id=str(skill.id), action="archived",
        actor_admin_id=actor_admin_id, before=before, after={"status": skill.status.value},
    )
    return skill


async def add_skill_alias(
    session: AsyncSession,
    skill: MnpSkill,
    *,
    alias: str,
    language: str = "uk",
    alias_type: SkillAliasType,
    source: str | None = None,
    confidence: float | None = None,
) -> MnpSkillAlias:
    """Idempotent: re-adding the same (skill, language, alias) is a
    no-op, so seed scripts can be re-run safely."""

    existing = await session.execute(
        select(MnpSkillAlias).where(
            MnpSkillAlias.skill_id == skill.id,
            MnpSkillAlias.language == language,
            MnpSkillAlias.alias == alias,
        )
    )
    found = existing.scalar_one_or_none()
    if found is not None:
        return found

    row = MnpSkillAlias(
        skill_id=skill.id, alias=alias, language=language, alias_type=alias_type,
        source=source, status=SkillStatus.ACTIVE, confidence=confidence,
    )
    session.add(row)
    await session.flush()
    return row


async def resolve_phrase(session: AsyncSession, raw_phrase: str, *, language: str = "uk") -> MnpSkill | None:
    """MNP_SKILL_SCHEMA_V1 §8 steps 3-4: exact alias, then normalized
    alias. Never falls back to fuzzy/LLM matching in BASIC (no LLM
    tokens) -- an unresolved phrase is the caller's job to queue via
    `queue_unmapped_phrase`, never silently dropped."""

    normalized = normalize_phrase(raw_phrase)
    result = await session.execute(
        select(MnpSkillAlias).where(MnpSkillAlias.language == language)
    )
    for row in result.scalars().all():
        if normalize_phrase(row.alias) == normalized:
            skill = await session.get(MnpSkill, row.skill_id)
            if skill is not None and skill.status != SkillStatus.ARCHIVED:
                return skill
    return None


async def queue_unmapped_phrase(
    session: AsyncSession, *, career_card_id: uuid.UUID, raw_phrase: str, context: str | None = None
) -> MnpUnmappedPhrase:
    row = MnpUnmappedPhrase(career_card_id=career_card_id, raw_phrase=raw_phrase, context=context)
    session.add(row)
    await session.flush()
    return row


async def get_skill_by_id(session: AsyncSession, skill_id: uuid.UUID) -> MnpSkill:
    skill = await session.get(MnpSkill, skill_id)
    if skill is None:
        raise MnpSkillNotFoundError(f"no MnpSkill {skill_id}")
    return skill
