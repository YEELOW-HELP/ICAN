"""Optional CV/resume upload as an evidence source (Stage 1, Section 15).
Reuses the existing app/services/documents.py extraction unchanged --
supported formats follow whatever that module already handles safely
(PDF/DOCX today), nothing is invented here. Extracted text is never
silently trusted: each dimension the CV *might* answer still goes through
the same confidence-scored extraction as an open question, and a
low-confidence CV-derived guess never becomes an Answer row at all (it
would otherwise incorrectly mark a dimension "resolved" and suppress a
question that should still be asked).

This does not create the Stage 2 Human Potential Profile or any Evidence
Graph entity -- CV facts land as ordinary `Answer` rows tagged
`source="cv"`, nothing more.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models_assessment import Answer, CVExtractionStatus, CVUpload
from app.services import documents
from app.services.assessment.completeness import LOW_CONFIDENCE_THRESHOLD, compute_completeness
from app.services.assessment.extraction import AnswerExtractor
from app.services.assessment.next_question import mark_question_answered
from app.services.assessment.question_bank import QUESTION_BANK
from app.services.assessment.sessions import find_answer_by_idempotency_key, get_owned_session
from app.services.events import emit_event
from app.services.exceptions import CVFileTooLargeError


async def upload_cv(
    session: AsyncSession,
    *,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    filename: str,
    content_bytes: bytes,
    extractor: AnswerExtractor | None = None,
) -> CVUpload:
    await get_owned_session(session, session_id=session_id, user_id=user_id)

    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(content_bytes) > max_bytes:
        raise CVFileTooLargeError(f"CV file exceeds {settings.max_upload_size_mb}MB limit")

    cv_upload = CVUpload(session_id=session_id, filename=filename, extraction_status=CVExtractionStatus.PENDING)
    session.add(cv_upload)
    await session.commit()
    await session.refresh(cv_upload)
    emit_event("cv_uploaded", user_id=str(user_id), session_id=str(session_id))

    try:
        text = documents.extract_text(content_bytes, filename)
    except documents.UnsupportedDocumentError:
        cv_upload.extraction_status = CVExtractionStatus.UNSUPPORTED
        await session.commit()
        emit_event("cv_processed", session_id=str(session_id), status="unsupported")
        return cv_upload

    if not text.strip():
        cv_upload.extraction_status = CVExtractionStatus.EMPTY
        await session.commit()
        emit_event("cv_processed", session_id=str(session_id), status="empty")
        return cv_upload

    cv_upload.extraction_status = CVExtractionStatus.SUCCESS
    cv_upload.extracted_text = text
    await session.commit()

    await _apply_cv_facts(session, session_id=session_id, cv_upload_id=cv_upload.id, cv_text=text, extractor=extractor)

    emit_event("cv_processed", session_id=str(session_id), status="success")
    return cv_upload


async def _apply_cv_facts(
    session: AsyncSession,
    *,
    session_id: uuid.UUID,
    cv_upload_id: uuid.UUID,
    cv_text: str,
    extractor: AnswerExtractor | None,
) -> None:
    """Only records a fact from the CV when extraction is confident it
    actually addresses the question -- a vague/absent match must not
    silently mark a dimension resolved."""
    active_extractor = extractor or AnswerExtractor()
    statuses = await compute_completeness(session, session_id)

    for question in QUESTION_BANK:
        if question.kind != "open" or statuses[question.question_id].state == "resolved":
            continue

        idempotency_key = f"cv:{cv_upload_id}:{question.question_id}"
        if await find_answer_by_idempotency_key(session, session_id, idempotency_key) is not None:
            continue  # this CV was already processed for this question (re-processing safety)

        result = await active_extractor.extract(
            question_prompt=question.question_id, raw_answer_text=cv_text, previous_value=None
        )
        if result.confidence < LOW_CONFIDENCE_THRESHOLD:
            continue  # CV didn't clearly address this dimension -- still ask it normally

        answer = Answer(
            session_id=session_id,
            question_id=question.question_id,
            answer_text=cv_text,
            extracted_value=result.extracted_value,
            confidence=result.confidence,
            contradicts_previous=False,
            source="cv",
            idempotency_key=idempotency_key,
        )
        session.add(answer)
        await session.commit()
        await session.refresh(answer)
        await mark_question_answered(session, session_id=session_id, question_id=question.question_id, answer_id=answer.id)
