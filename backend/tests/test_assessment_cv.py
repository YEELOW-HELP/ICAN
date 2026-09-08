"""Optional CV upload as an evidence source (Stage 1, Section 15/21).
CV text is never silently trusted -- it goes through the same
confidence-scored extraction pipeline as any open answer, tagged
Answer.source="cv", and a low-confidence CV guess must not suppress a
question that should still be asked.
"""

import pytest

from app.core.config import settings
from app.core.security import hash_password
from app.db.models import AdminRole, AdminUser
from app.db.models_assessment import CVExtractionStatus
from app.db.models_identity import IdentityUser
from app.services import documents
from app.services.assessment.extraction import ExtractionResult
from app.services.assessment.cv import upload_cv
from app.services.assessment.next_question import get_next_question
from app.services.assessment.sessions import start_assessment
from app.services.exceptions import CVFileTooLargeError
from app.services.product_access import grant_manual_access


class ScriptedExtractor:
    def __init__(self, results_by_question):
        self._results = dict(results_by_question)
        self.calls = []

    async def extract(self, *, question_prompt, raw_answer_text, previous_value):
        self.calls.append(question_prompt)
        return self._results.get(question_prompt, ExtractionResult("", 0.0, False))


async def _make_user_with_basic_access(session):
    user = IdentityUser()
    session.add(user)
    await session.flush()
    admin = AdminUser(email="admin@test.dev", password_hash=hash_password("pw"), role=AdminRole.ADMIN)
    session.add(admin)
    await session.commit()
    await session.refresh(user)
    await session.refresh(admin)
    await grant_manual_access(session, user_id=user.id, plan_code="BASIC", granted_by_admin=admin)
    return user


async def test_supported_docx_upload_extracts_facts_and_marks_success(session_factory, monkeypatch):
    monkeypatch.setattr(documents, "extract_text", lambda content, filename: "Кваліфікований Python розробник з Києва")

    async with session_factory() as session:
        user = await _make_user_with_basic_access(session)
        interview_session = await start_assessment(session, user_id=user.id, plan_code="BASIC")

        extractor = ScriptedExtractor(
            {
                "name": ExtractionResult("", 0.1, False),
                "city": ExtractionResult("Київ", 0.9, False),
                "key_skills_or_interests": ExtractionResult("Python", 0.85, False),
                "desired_direction_hint": ExtractionResult("", 0.2, False),
                "total_experience": ExtractionResult("", 0.1, False),
                "constraints": ExtractionResult("", 0.1, False),
            }
        )

        cv_upload = await upload_cv(
            session, session_id=interview_session.id, user_id=user.id,
            filename="cv.docx", content_bytes=b"fake docx bytes", extractor=extractor,
        )

        assert cv_upload.extraction_status == CVExtractionStatus.SUCCESS

        statuses = await get_next_question(session, interview_session.id)
        # "city" and "key_skills_or_interests" should now be resolved from the CV
        assert statuses.question is None or statuses.question.question_id not in ("city", "key_skills_or_interests")


async def test_unsupported_file_type_is_recorded_not_raised(session_factory):
    async with session_factory() as session:
        user = await _make_user_with_basic_access(session)
        interview_session = await start_assessment(session, user_id=user.id, plan_code="BASIC")

        cv_upload = await upload_cv(
            session, session_id=interview_session.id, user_id=user.id,
            filename="cv.txt", content_bytes=b"plain text resume",
        )
        assert cv_upload.extraction_status == CVExtractionStatus.UNSUPPORTED


async def test_empty_extracted_text_is_recorded_as_empty(session_factory, monkeypatch):
    monkeypatch.setattr(documents, "extract_text", lambda content, filename: "   ")

    async with session_factory() as session:
        user = await _make_user_with_basic_access(session)
        interview_session = await start_assessment(session, user_id=user.id, plan_code="BASIC")

        cv_upload = await upload_cv(
            session, session_id=interview_session.id, user_id=user.id,
            filename="cv.pdf", content_bytes=b"fake pdf bytes",
        )
        assert cv_upload.extraction_status == CVExtractionStatus.EMPTY


async def test_low_confidence_cv_extraction_does_not_create_an_answer(session_factory, monkeypatch):
    monkeypatch.setattr(documents, "extract_text", lambda content, filename: "неясний текст")

    async with session_factory() as session:
        user = await _make_user_with_basic_access(session)
        interview_session = await start_assessment(session, user_id=user.id, plan_code="BASIC")

        extractor = ScriptedExtractor({})  # everything defaults to confidence 0.0
        await upload_cv(
            session, session_id=interview_session.id, user_id=user.id,
            filename="cv.pdf", content_bytes=b"fake pdf bytes", extractor=extractor,
        )

        result = await get_next_question(session, interview_session.id)
        assert result.question is not None
        assert result.reason.value == "missing"


async def test_oversized_cv_file_is_rejected_before_extraction(session_factory, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_size_mb", 1)

    async with session_factory() as session:
        user = await _make_user_with_basic_access(session)
        interview_session = await start_assessment(session, user_id=user.id, plan_code="BASIC")

        oversized = b"x" * (2 * 1024 * 1024)
        with pytest.raises(CVFileTooLargeError):
            await upload_cv(
                session, session_id=interview_session.id, user_id=user.id,
                filename="cv.pdf", content_bytes=oversized,
            )
