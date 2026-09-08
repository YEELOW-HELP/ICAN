"""CV upload -> deterministic extraction -> CANDIDATE facts -> user review
-> confirm -> Person KB.

Reuses the existing MNP resume parser's pure functions (no AI, no LLM
tokens). A candidate fact is NEVER written to the Person KB before a human
confirms it -- `extract_candidates` returns a plain dict the browser holds
until `apply_confirmed`. The uploaded file is always saved as an
`MnpPersonDocument` (type CV) so nothing is lost even on a parse failure.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models_person_kb import (
    ActivityType,
    CredentialType,
    EducationLevel,
    LanguageLevel,
    MnpPersonDocument,
    PersonDocumentType,
    PersonEvidenceState,
    PersonSource,
    TriState,
)
from app.services.person_kb import service
from app.services.resume_parser_mnp.extract import parse_resume_sections
from app.services.resume_parser_mnp.extraction import (
    CorruptFileError,
    NoTextLayerError,
    UnsupportedDocumentError,
    extract_text,
)
from app.services.resume_parser_mnp.sections import split_into_sections

CV_PARSER_VERSION = "person_kb_cv_intake_v1"

_LEVEL_MAP = {"a1": LanguageLevel.A1, "a2": LanguageLevel.A2, "b1": LanguageLevel.B1,
              "b2": LanguageLevel.B2, "c1": LanguageLevel.C1, "c2": LanguageLevel.C2,
              "native": LanguageLevel.NATIVE}
_EDU_LEVEL_MAP = {"bachelor": EducationLevel.BACHELOR, "master": EducationLevel.MASTER,
                  "specialist": EducationLevel.SPECIALIST, "phd": EducationLevel.PHD,
                  "secondary": EducationLevel.SECONDARY, "vocational": EducationLevel.VOCATIONAL}


class CvParseError(Exception):
    """CV could not be turned into candidate facts -- caller offers the
    manual profile flow. `document_id` is set (the file is saved)."""

    def __init__(self, message: str, document_id: uuid.UUID | None = None):
        super().__init__(message)
        self.document_id = document_id


def _storage_dir() -> Path:
    d = Path(settings.mnp_resume_storage_dir)
    d.mkdir(parents=True, exist_ok=True)
    return d


async def _save_cv_document(session: AsyncSession, person_id: uuid.UUID, *, filename: str,
                            content: bytes, mime_type: str | None) -> MnpPersonDocument:
    safe = f"{uuid.uuid4().hex}_{Path(filename).name}"
    path = _storage_dir() / safe
    path.write_bytes(content)
    return await service.add_document(
        session, person_id, document_type=PersonDocumentType.CV.value, filename=filename,
        storage_ref=str(path), mime_type=mime_type, file_size=len(content), note="Завантажене резюме")


async def extract_candidates(session: AsyncSession, person_id: uuid.UUID, *, filename: str,
                             content: bytes, mime_type: str | None = None) -> dict:
    """Save the CV, extract candidate facts. Raises `CvParseError` (with a
    saved `document_id`) if the file can't be parsed."""
    doc = await _save_cv_document(session, person_id, filename=filename, content=content, mime_type=mime_type)
    try:
        text = extract_text(content, filename)
    except UnsupportedDocumentError:
        raise CvParseError("Формат файлу не підтримується.", doc.id)
    except NoTextLayerError:
        raise CvParseError("У файлі немає тексту для розпізнавання (можливо, це скан).", doc.id)
    except CorruptFileError:
        raise CvParseError("Файл пошкоджено.", doc.id)
    if not text.strip():
        raise CvParseError("Не вдалося прочитати текст резюме.", doc.id)

    parsed = parse_resume_sections(split_into_sections(text))

    candidates = {
        "document_id": str(doc.id),
        "parser_version": CV_PARSER_VERSION,
        "experiences": [{
            "raw_job_title": e.raw_job_title, "company_name": e.company_name,
            "start_date": e.start_date.isoformat() if e.start_date else None,
            "end_date": e.end_date.isoformat() if e.end_date else None,
            "is_current": TriState.YES.value if e.is_current else TriState.UNKNOWN.value,
            "responsibilities_description": e.responsibilities_raw or None,
            "achievements": "\n".join(e.achievements) or None,
        } for e in parsed.experiences],
        "educations": [{
            "education_level": (_EDU_LEVEL_MAP.get((ed.level or "").lower(), EducationLevel.UNKNOWN)).value,
            "specialty_or_qualification": ed.raw_line[:255] if ed.raw_line else None,
            "end_year": ed.graduation_year,
        } for ed in parsed.educations],
        "skills": [{"raw_input": s} for s in parsed.raw_skill_phrases],
        "languages": [{
            "language": lg.language_code, "level": _LEVEL_MAP.get(
                (lg.overall_level or "").lower(), LanguageLevel.UNKNOWN).value,
        } for lg in parsed.languages],
        "credentials": [{"title": c.name, "credential_type": CredentialType.OTHER.value}
                        for c in parsed.credentials],
    }
    total = sum(len(candidates[k]) for k in ("experiences", "educations", "skills", "languages", "credentials"))
    if total == 0:
        raise CvParseError("Не вдалося виділити факти з резюме.", doc.id)
    return candidates


async def apply_confirmed(session: AsyncSession, person_id: uuid.UUID, confirmed: dict, *,
                          document_id: str | None = None) -> None:
    """Write the user-reviewed candidate set into the Person KB. Every row
    is `evidence_state = USER_CONFIRMED`, `source = CV_CONFIRMED`. Raw job
    titles / responsibility text are written verbatim."""
    doc_uuid = uuid.UUID(document_id) if document_id else None

    for e in confirmed.get("experiences", []):
        if not (e.get("raw_job_title") or "").strip():
            continue
        await service.add_row(session, person_id, "experiences", {
            **{k: e.get(k) for k in ("raw_job_title", "company_name", "start_date", "end_date",
                                     "responsibilities_description", "achievements", "tools_used",
                                     "industry", "employment_type")},
            "is_current": e.get("is_current") or TriState.UNKNOWN.value,
            "supporting_document_id": str(doc_uuid) if doc_uuid else None,
            "evidence_state": PersonEvidenceState.USER_CONFIRMED.value,
        }, source=PersonSource.CV_CONFIRMED)

    for ed in confirmed.get("educations", []):
        if not any(ed.get(k) for k in ("institution_name", "specialty_or_qualification", "end_year")):
            continue
        await service.add_row(session, person_id, "educations", {
            **{k: ed.get(k) for k in ("education_level", "institution_name",
                                      "specialty_or_qualification", "start_year", "end_year",
                                      "status", "description")},
            "supporting_document_id": str(doc_uuid) if doc_uuid else None,
            "evidence_state": PersonEvidenceState.USER_CONFIRMED.value,
        }, source=PersonSource.CV_CONFIRMED)

    for c in confirmed.get("credentials", []):
        if not (c.get("title") or "").strip():
            continue
        await service.add_row(session, person_id, "credentials", {
            **{k: c.get(k) for k in ("credential_type", "title", "provider", "issue_date",
                                     "expiry_date", "credential_number", "description")},
            "supporting_document_id": str(doc_uuid) if doc_uuid else None,
            "evidence_state": PersonEvidenceState.USER_CONFIRMED.value,
        }, source=PersonSource.CV_CONFIRMED)

    for lg in confirmed.get("languages", []):
        if not (lg.get("language") or "").strip():
            continue
        await service.add_row(session, person_id, "languages", {
            "language": lg["language"], "level": lg.get("level") or LanguageLevel.UNKNOWN.value,
            "certificate": lg.get("certificate"),
            "supporting_document_id": str(doc_uuid) if doc_uuid else None,
            "evidence_state": PersonEvidenceState.USER_CONFIRMED.value,
        }, source=PersonSource.CV_CONFIRMED)

    for s in confirmed.get("skills", []):
        raw = (s.get("raw_input") or "").strip()
        if not raw and not s.get("canonical_skill_id"):
            continue
        await service.add_skill(
            session, person_id, canonical_skill_id=s.get("canonical_skill_id"), raw_input=raw or None,
            proficiency=s.get("proficiency"),
            evidence_state=PersonEvidenceState.USER_CONFIRMED.value, source=PersonSource.CV_CONFIRMED)
