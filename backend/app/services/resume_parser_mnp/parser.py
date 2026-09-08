"""MNP V1 -- Resume Parser DB orchestration: applies a pure `ParsedResume`
to a `MnpCareerCard` (Experience/Education/PersonSkill/Language/
Credential rows + Evidence), and the top-level upload entrypoint
(`upload_and_parse_resume`) implementing the full
`MNP_RESUME_PARSER_V1` pipeline: upload -> validate -> text extraction ->
section detection -> entity extraction -> normalization -> evidence
creation -> Career Card update. No mandatory confirmation screen --
the Career Card is immediately usable (Founder Decision #6)."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models_career_card import (
    DocumentType,
    EntryMode,
    EvidenceSourceType,
    EvidenceType,
    MnpAchievement,
    MnpCareerCard,
    MnpCredential,
    MnpEducation,
    MnpExperience,
    MnpLanguage,
    MnpSourceDocument,
    SourceMode,
    TextExtractionStatus,
)
from app.services.career_card_mnp.card import (
    get_or_create_career_card,
    record_evidence,
    snapshot_career_card,
    start_assessment_session,
)
from app.services.career_card_mnp.skill_application import apply_skill_phrase
from app.services.career_kb_mnp.alias_resolution import resolve_job_title_to_career
from app.services.crm.storage import LocalFileStorage
from app.services.exceptions import CVFileTooLargeError
from app.services.resume_parser_mnp.extract import ParsedResume, parse_resume_sections
from app.services.resume_parser_mnp.extraction import (
    CorruptFileError,
    NoTextLayerError,
    UnsupportedDocumentError,
    extract_text,
)
from app.services.resume_parser_mnp.sections import split_into_sections

PARSER_VERSION = "mnp_resume_parser_v0.1"

_storage = LocalFileStorage(settings.mnp_resume_storage_dir)


async def apply_parsed_resume_to_career_card(
    session: AsyncSession, career_card: MnpCareerCard, parsed: ParsedResume, *, document_id: uuid.UUID,
) -> None:
    for exp in parsed.experiences:
        matched_career = await resolve_job_title_to_career(session, exp.raw_job_title)
        row = MnpExperience(
            career_card_id=career_card.id,
            company_name=exp.company_name,
            raw_job_title=exp.raw_job_title,
            normalized_career_id=matched_career.id if matched_career else None,
            start_date=exp.start_date,
            end_date=exp.end_date,
            is_current=exp.is_current,
            responsibilities_raw=exp.responsibilities_raw or None,
            management_scope=exp.management_scope,
            team_size=exp.team_size,
            source_type=EvidenceSourceType.CV,
            confidence=0.8 if exp.start_date else 0.5,
        )
        session.add(row)
        await session.flush()
        await record_evidence(
            session, career_card, entity_type="experience", entity_id=row.id, evidence_type=EvidenceType.CLAIMED,
            source_type=EvidenceSourceType.CV, excerpt=exp.responsibilities_raw[:500] or None,
            document_id=document_id, strength_internal=0.7,
        )
        for achievement_text in exp.achievements:
            achievement_row = MnpAchievement(
                career_card_id=career_card.id, experience_id=row.id, description=achievement_text,
                source_type=EvidenceSourceType.CV, confidence=0.6,
            )
            session.add(achievement_row)
            await session.flush()
            await record_evidence(
                session, career_card, entity_type="achievement", entity_id=achievement_row.id,
                evidence_type=EvidenceType.CLAIMED, source_type=EvidenceSourceType.CV, excerpt=achievement_text,
                document_id=document_id, strength_internal=0.7,
            )
        if exp.management_scope:
            # MNP_EVIDENCE_AND_CONFIDENCE_MODEL_V1 §3 example: "керував
            # командою з 8 співробітників" -> INFERRED Team Management,
            # not CLAIMED (the CV states team size, not the "Team
            # Leadership" skill/competency itself).
            await record_evidence(
                session, career_card, entity_type="experience", entity_id=row.id, evidence_type=EvidenceType.INFERRED,
                source_type=EvidenceSourceType.CV, excerpt=f"team_size={exp.team_size}",
                document_id=document_id, strength_internal=0.6,
            )

    for edu in parsed.educations:
        row = MnpEducation(
            career_card_id=career_card.id,
            level=edu.level or "unknown",
            graduation_year=edu.graduation_year,
            source_type=EvidenceSourceType.CV,
            confidence=0.7 if edu.level else 0.4,
        )
        session.add(row)
        await session.flush()
        await record_evidence(
            session, career_card, entity_type="education", entity_id=row.id, evidence_type=EvidenceType.CLAIMED,
            source_type=EvidenceSourceType.CV, excerpt=edu.raw_line[:500], document_id=document_id,
        )

    for phrase in parsed.raw_skill_phrases:
        await apply_skill_phrase(session, career_card, phrase, source_type=EvidenceSourceType.CV, document_id=document_id)

    for lang in parsed.languages:
        row = MnpLanguage(
            career_card_id=career_card.id, language_code=lang.language_code, overall_level=lang.overall_level,
            source_type=EvidenceSourceType.CV, confidence=0.7 if lang.overall_level else 0.4,
        )
        session.add(row)
        await session.flush()
        await record_evidence(
            session, career_card, entity_type="language", entity_id=row.id, evidence_type=EvidenceType.CLAIMED,
            source_type=EvidenceSourceType.CV, excerpt=lang.raw_line, document_id=document_id,
        )

    for cred in parsed.credentials:
        row = MnpCredential(
            career_card_id=career_card.id, credential_type="certification", name=cred.name,
            source_type=EvidenceSourceType.CV, confidence=0.6,
        )
        session.add(row)
        await session.flush()
        await record_evidence(
            session, career_card, entity_type="credential", entity_id=row.id, evidence_type=EvidenceType.CLAIMED,
            source_type=EvidenceSourceType.CV, excerpt=cred.name, document_id=document_id,
        )

    await session.flush()


async def upload_and_parse_resume(
    session: AsyncSession, *, user_id: uuid.UUID, filename: str, content_bytes: bytes,
) -> tuple[MnpCareerCard, MnpSourceDocument]:
    """Returns the (immediately usable, no confirmation step) CareerCard
    and the SourceDocument tracking row. Raises `CVFileTooLargeError` for
    an oversized upload -- everything else (unsupported format, corrupt
    file, no text layer) is recorded as a `TextExtractionStatus` on the
    returned document instead of raising, so the caller can offer the
    manual questionnaire as a fallback (MNP_RESUME_PARSER_V1 "Error
    states")."""

    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(content_bytes) > max_bytes:
        raise CVFileTooLargeError(f"Resume exceeds {settings.max_upload_size_mb}MB limit")

    assessment_session = await start_assessment_session(session, user_id=user_id, entry_mode=EntryMode.RESUME)
    career_card = await get_or_create_career_card(
        session, user_id=user_id, assessment_session_id=assessment_session.id, source_mode=SourceMode.RESUME,
    )

    storage_key = _storage.save(str(user_id), filename, content_bytes)
    document = MnpSourceDocument(
        user_id=user_id, assessment_session_id=assessment_session.id, document_type=DocumentType.RESUME,
        filename=filename, file_size=len(content_bytes), storage_ref=storage_key,
        text_extraction_status=TextExtractionStatus.PENDING, parser_version=PARSER_VERSION,
    )
    session.add(document)
    await session.flush()

    try:
        text = extract_text(content_bytes, filename)
    except UnsupportedDocumentError:
        document.text_extraction_status = TextExtractionStatus.UNSUPPORTED_FORMAT
        await session.commit()
        return career_card, document
    except NoTextLayerError:
        document.text_extraction_status = TextExtractionStatus.OCR_REQUIRED
        await session.commit()
        return career_card, document
    except CorruptFileError:
        document.text_extraction_status = TextExtractionStatus.CORRUPT_FILE
        await session.commit()
        return career_card, document

    sections = split_into_sections(text)
    parsed = parse_resume_sections(sections)
    await apply_parsed_resume_to_career_card(session, career_card, parsed, document_id=document.id)

    has_any_entity = bool(
        parsed.experiences or parsed.educations or parsed.raw_skill_phrases or parsed.languages or parsed.credentials
    )
    document.text_extraction_status = (
        TextExtractionStatus.EXTRACTED if has_any_entity else TextExtractionStatus.PARSE_PARTIAL
    )
    await snapshot_career_card(session, career_card)
    await session.commit()
    return career_card, document
