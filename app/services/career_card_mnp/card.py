"""MNP V1 -- Career Card creation and versioned snapshotting
(MNP_DATA_MODEL_V1 §4/§6, Founder Decision #7/DM-FQ-002: one long-lived
master card, calculations use immutable versioned snapshots)."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models_career_card import (
    EntryMode,
    EvidenceSourceType,
    EvidenceType,
    MnpAssessmentSession,
    MnpCareerCard,
    MnpCareerCardVersion,
    MnpEvidence,
    SessionStatus,
    SourceMode,
)
from app.services.exceptions import MnpCareerCardNotFoundError

METHODOLOGY_VERSION = "mnp_methodology_v1.0"


def _jsonable(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    return value


async def start_assessment_session(
    session: AsyncSession, *, user_id: uuid.UUID, entry_mode: EntryMode,
) -> MnpAssessmentSession:
    row = MnpAssessmentSession(
        user_id=user_id, entry_mode=entry_mode, status=SessionStatus.IN_PROGRESS,
        methodology_version=METHODOLOGY_VERSION,
    )
    session.add(row)
    await session.flush()
    return row


async def get_or_create_career_card(
    session: AsyncSession, *, user_id: uuid.UUID, assessment_session_id: uuid.UUID, source_mode: SourceMode,
) -> MnpCareerCard:
    """Founder Decision #7: ONE master card per user. A second call
    (e.g. a returning user starting a new session) returns the existing
    card, retargeted at the new session -- it never creates a duplicate."""

    existing = await session.execute(select(MnpCareerCard).where(MnpCareerCard.user_id == user_id))
    card = existing.scalar_one_or_none()
    if card is not None:
        card.assessment_session_id = assessment_session_id
        if source_mode != card.source_mode:
            card.source_mode = SourceMode.MIXED
        await session.flush()
        return card

    card = MnpCareerCard(
        user_id=user_id, assessment_session_id=assessment_session_id, version=1, source_mode=source_mode,
    )
    session.add(card)
    await session.flush()
    return card


async def get_career_card_by_user(session: AsyncSession, user_id: uuid.UUID) -> MnpCareerCard:
    existing = await session.execute(select(MnpCareerCard).where(MnpCareerCard.user_id == user_id))
    card = existing.scalar_one_or_none()
    if card is None:
        raise MnpCareerCardNotFoundError(f"no MnpCareerCard for user {user_id}")
    return card


async def record_evidence(
    session: AsyncSession, career_card: MnpCareerCard, *, entity_type: str, entity_id: uuid.UUID,
    evidence_type: EvidenceType, source_type: EvidenceSourceType, source_ref: str | None = None,
    excerpt: str | None = None, document_id: uuid.UUID | None = None, strength_internal: float = 0.5,
    parser_confidence: float | None = None,
) -> MnpEvidence:
    """MNP_EVIDENCE_AND_CONFIDENCE_MODEL_V1 §4. Never marks VERIFIED by
    itself -- callers pass `evidence_type` explicitly; the resume parser
    and questionnaire only ever pass CLAIMED/INFERRED
    (MNP_RESUME_PARSER_V1 "Evidence": "Parser never marks VERIFIED by
    itself")."""

    row = MnpEvidence(
        career_card_id=career_card.id, entity_type=entity_type, entity_id=entity_id, evidence_type=evidence_type,
        source_type=source_type, source_ref=source_ref, excerpt=excerpt, document_id=document_id,
        strength_internal=strength_internal, parser_confidence=parser_confidence,
    )
    session.add(row)
    await session.flush()
    return row


async def serialize_career_card(session: AsyncSession, career_card: MnpCareerCard) -> dict:
    """Full denormalized snapshot -- deliberately independent of the live
    tables' shape evolving later (MNP_EVIDENCE_AND_CONFIDENCE_MODEL_V1
    §24 Auditability: a historical MatchRun must stay reproducible)."""

    result = await session.execute(
        select(MnpCareerCard)
        .where(MnpCareerCard.id == career_card.id)
        .options(
            selectinload(MnpCareerCard.experiences),
            selectinload(MnpCareerCard.educations),
            selectinload(MnpCareerCard.achievements),
            selectinload(MnpCareerCard.credentials),
            selectinload(MnpCareerCard.languages),
            selectinload(MnpCareerCard.person_skills),
            selectinload(MnpCareerCard.person_knowledge),
            selectinload(MnpCareerCard.goals),
            selectinload(MnpCareerCard.income_target),
            selectinload(MnpCareerCard.preference_profile),
            selectinload(MnpCareerCard.work_values),
            selectinload(MnpCareerCard.constraints),
            selectinload(MnpCareerCard.learning_capacity),
        )
    )
    card = result.scalar_one()

    def _dump(obj) -> dict:
        return {
            c.name: _jsonable(getattr(obj, c.name))
            for c in obj.__table__.columns
        }

    return {
        "career_card_id": str(card.id),
        "version": card.version,
        "source_mode": card.source_mode.value,
        "experiences": [_dump(e) for e in card.experiences],
        "educations": [_dump(e) for e in card.educations],
        "achievements": [_dump(a) for a in card.achievements],
        "credentials": [_dump(c) for c in card.credentials],
        "languages": [_dump(l) for l in card.languages],
        "person_skills": [_dump(s) for s in card.person_skills],
        "person_knowledge": [_dump(k) for k in card.person_knowledge],
        "goals": [_dump(g) for g in card.goals],
        "income_target": _dump(card.income_target) if card.income_target else None,
        "preference_profile": _dump(card.preference_profile) if card.preference_profile else None,
        "work_values": [_dump(w) for w in card.work_values],
        "constraints": [_dump(c) for c in card.constraints],
        "learning_capacity": _dump(card.learning_capacity) if card.learning_capacity else None,
    }


async def snapshot_career_card(session: AsyncSession, career_card: MnpCareerCard) -> MnpCareerCardVersion:
    """Bumps `MnpCareerCard.version` and writes the immutable snapshot a
    `MnpMatchRun` will pin. Called once per recalculation (initial result
    and every subsequent "edit Career Card -> recalculate")."""

    career_card.version += 1
    snapshot = await serialize_career_card(session, career_card)
    snapshot["version"] = career_card.version
    row = MnpCareerCardVersion(career_card_id=career_card.id, version=career_card.version, snapshot=snapshot)
    session.add(row)
    await session.flush()
    return row
