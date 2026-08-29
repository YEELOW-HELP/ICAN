"""Shared "apply one raw skill phrase to a CareerCard" logic -- used by
both the resume parser (BLOCK B Flow A) and the questionnaire (Flow B),
so the resolve-or-queue + idempotent PersonSkill + Evidence sequence
lives in exactly one place."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_career_card import (
    EvidenceSourceType,
    EvidenceType,
    MnpCareerCard,
    MnpPersonSkill,
    ProficiencyLevel,
)
from app.services.career_card_mnp.card import record_evidence
from app.services.career_kb_mnp.skills import queue_unmapped_phrase, resolve_phrase


async def apply_skill_phrase(
    session: AsyncSession, career_card: MnpCareerCard, phrase: str, *, source_type: EvidenceSourceType,
    document_id: uuid.UUID | None = None, proficiency: ProficiencyLevel = ProficiencyLevel.WORKING,
    evidence_strength: float = 0.6, confidence: float = 0.6,
) -> MnpPersonSkill | None:
    """Returns the (possibly pre-existing) `MnpPersonSkill`, or `None` if
    the phrase could not be resolved to a canonical `MnpSkill` (queued for
    review instead -- SS-FQ-004, never auto-creates a new Skill)."""

    skill = await resolve_phrase(session, phrase)
    if skill is None:
        await queue_unmapped_phrase(session, career_card_id=career_card.id, raw_phrase=phrase, context="skills")
        return None

    existing = await session.execute(
        select(MnpPersonSkill).where(
            MnpPersonSkill.career_card_id == career_card.id, MnpPersonSkill.skill_id == skill.id
        )
    )
    found = existing.scalar_one_or_none()
    if found is not None:
        return found

    person_skill = MnpPersonSkill(
        career_card_id=career_card.id, skill_id=skill.id, proficiency_level=proficiency,
        evidence_strength=evidence_strength, confidence=confidence, source_type=source_type,
    )
    session.add(person_skill)
    await session.flush()
    await record_evidence(
        session, career_card, entity_type="person_skill", entity_id=person_skill.id,
        evidence_type=EvidenceType.CLAIMED, source_type=source_type, source_ref=phrase,
        document_id=document_id, strength_internal=evidence_strength,
    )
    return person_skill
