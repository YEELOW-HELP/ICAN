"""Stage 1 failure model: an AI Gateway/provider failure during answer
extraction must never lose the candidate's raw words, never move the
session to FAILED, and never fabricate an Answer row. See Section 14/24
of the Stage 1 brief and the docstring on submit_answer's extraction
branch in app/services/assessment/sessions.py.
"""

import pytest
from sqlalchemy import func, select

from app.core.security import hash_password
from app.db.models import AdminRole, AdminUser
from app.db.models_assessment import Answer, AssessmentStatus, InterviewMessage
from app.db.models_identity import IdentityUser
from app.services.assessment.sessions import start_assessment, submit_answer
from app.services.product_access import grant_manual_access


class ExplodingExtractor:
    """Simulates any exception from the AI provider (rate limit, timeout,
    outage, malformed response) surfacing out of AnswerExtractor.extract."""

    def __init__(self, exc: Exception):
        self._exc = exc
        self.calls = 0

    async def extract(self, *, question_prompt, raw_answer_text, previous_value):
        self.calls += 1
        raise self._exc


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


async def test_provider_failure_propagates_and_does_not_fail_the_session(session_factory):
    async with session_factory() as session:
        user = await _make_user_with_basic_access(session)
        interview_session = await start_assessment(session, user_id=user.id, plan_code="BASIC")
        extractor = ExplodingExtractor(ConnectionError("Anthropic API unreachable"))

        with pytest.raises(ConnectionError):
            await submit_answer(
                session, session_id=interview_session.id, user_id=user.id, question_id="city",
                raw_text="я живу в Києві", idempotency_key="k1", source="telegram",
                extractor=extractor,
            )

        assert extractor.calls == 1
        await session.refresh(interview_session)
        assert interview_session.status == AssessmentStatus.ACTIVE


async def test_provider_failure_still_preserves_raw_transcript_message(session_factory):
    async with session_factory() as session:
        user = await _make_user_with_basic_access(session)
        interview_session = await start_assessment(session, user_id=user.id, plan_code="BASIC")
        extractor = ExplodingExtractor(TimeoutError("provider timed out"))

        with pytest.raises(TimeoutError):
            await submit_answer(
                session, session_id=interview_session.id, user_id=user.id, question_id="city",
                raw_text="я живу в Києві", idempotency_key="k1", source="telegram",
                extractor=extractor,
            )

        message = (
            await session.execute(
                select(InterviewMessage).where(
                    InterviewMessage.session_id == interview_session.id, InterviewMessage.role == "user"
                )
            )
        ).scalar_one()
        assert message.content == "я живу в Києві"


async def test_provider_failure_creates_no_answer_row(session_factory):
    async with session_factory() as session:
        user = await _make_user_with_basic_access(session)
        interview_session = await start_assessment(session, user_id=user.id, plan_code="BASIC")
        extractor = ExplodingExtractor(RuntimeError("malformed tool response"))

        with pytest.raises(RuntimeError):
            await submit_answer(
                session, session_id=interview_session.id, user_id=user.id, question_id="city",
                raw_text="я живу в Києві", idempotency_key="k1", source="telegram",
                extractor=extractor,
            )

        count = (
            await session.execute(select(func.count()).select_from(Answer).where(Answer.session_id == interview_session.id))
        ).scalar_one()
        assert count == 0


async def test_retry_after_provider_failure_is_not_automatic_but_succeeds_on_next_attempt(session_factory):
    """No automatic retry/fallback exists (Section 15) -- the caller (the
    Telegram adapter) must ask the candidate again and resubmit with a new
    idempotency key. A fresh attempt after a failure works normally."""
    async with session_factory() as session:
        user = await _make_user_with_basic_access(session)
        interview_session = await start_assessment(session, user_id=user.id, plan_code="BASIC")
        failing = ExplodingExtractor(ConnectionError("transient outage"))

        with pytest.raises(ConnectionError):
            await submit_answer(
                session, session_id=interview_session.id, user_id=user.id, question_id="city",
                raw_text="я живу в Києві", idempotency_key="attempt-1", source="telegram",
                extractor=failing,
            )
        assert failing.calls == 1

        from app.services.assessment.extraction import ExtractionResult

        class WorkingExtractor:
            def __init__(self):
                self.calls = 0

            async def extract(self, *, question_prompt, raw_answer_text, previous_value):
                self.calls += 1
                return ExtractionResult("Kyiv", 0.9, False)

        working = WorkingExtractor()
        answer = await submit_answer(
            session, session_id=interview_session.id, user_id=user.id, question_id="city",
            raw_text="я живу в Києві", idempotency_key="attempt-2", source="telegram",
            extractor=working,
        )
        assert working.calls == 1
        assert answer.extracted_value == "Kyiv"

        count = (
            await session.execute(select(func.count()).select_from(Answer).where(Answer.session_id == interview_session.id))
        ).scalar_one()
        assert count == 1
