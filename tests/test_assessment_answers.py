import pytest

from app.core.security import hash_password
from app.db.models import AdminRole, AdminUser
from app.db.models_assessment import AssessmentStatus
from app.db.models_identity import IdentityUser
from app.services.assessment.extraction import ExtractionResult
from app.services.assessment.sessions import complete_assessment, pause_assessment, start_assessment, submit_answer
from app.services.exceptions import (
    AssessmentOwnershipError,
    InvalidStateTransitionError,
    UnfinishedAssessmentExistsError,
)
from app.services.product_access import grant_manual_access


class FakeExtractor:
    """Duck-types AnswerExtractor -- returns a scripted sequence of
    results and counts how many times it was actually called, the same
    pattern already established for AIGateway/ScreeningAgent tests."""

    def __init__(self, results):
        self._results = list(results)
        self.calls = 0

    async def extract(self, *, question_prompt, raw_answer_text, previous_value):
        self.calls += 1
        return self._results.pop(0)


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


async def test_first_answer_moves_draft_session_to_active(session_factory):
    async with session_factory() as session:
        user = await _make_user_with_basic_access(session)
        interview_session = await start_assessment(session, user_id=user.id, plan_code="BASIC")
        assert interview_session.status == AssessmentStatus.DRAFT

        await submit_answer(
            session,
            session_id=interview_session.id,
            user_id=user.id,
            question_id="current_status",
            raw_text="working",
            idempotency_key="k1",
            source="telegram",
        )
        await session.refresh(interview_session)
        assert interview_session.status == AssessmentStatus.ACTIVE


async def test_structured_question_never_calls_the_extractor(session_factory):
    async with session_factory() as session:
        user = await _make_user_with_basic_access(session)
        interview_session = await start_assessment(session, user_id=user.id, plan_code="BASIC")
        extractor = FakeExtractor([])  # any call would raise IndexError

        answer = await submit_answer(
            session,
            session_id=interview_session.id,
            user_id=user.id,
            question_id="current_status",
            raw_text="working",
            idempotency_key="k1",
            source="telegram",
            extractor=extractor,
        )
        assert extractor.calls == 0
        assert answer.confidence == 1.0
        assert answer.extracted_value == "working"


async def test_open_question_calls_extractor_and_stores_result(session_factory):
    async with session_factory() as session:
        user = await _make_user_with_basic_access(session)
        interview_session = await start_assessment(session, user_id=user.id, plan_code="BASIC")
        extractor = FakeExtractor([ExtractionResult("Kyiv", 0.9, False)])

        answer = await submit_answer(
            session,
            session_id=interview_session.id,
            user_id=user.id,
            question_id="city",
            raw_text="я живу в Києві",
            idempotency_key="k1",
            source="telegram",
            extractor=extractor,
        )
        assert extractor.calls == 1
        assert answer.extracted_value == "Kyiv"
        assert answer.confidence == 0.9


async def test_duplicate_submission_is_idempotent_no_duplicate_answer_or_ai_call(session_factory):
    async with session_factory() as session:
        user = await _make_user_with_basic_access(session)
        interview_session = await start_assessment(session, user_id=user.id, plan_code="BASIC")
        extractor = FakeExtractor([ExtractionResult("Kyiv", 0.9, False)])

        first = await submit_answer(
            session,
            session_id=interview_session.id,
            user_id=user.id,
            question_id="city",
            raw_text="Київ",
            idempotency_key="same-key",
            source="telegram",
            extractor=extractor,
        )
        second = await submit_answer(
            session,
            session_id=interview_session.id,
            user_id=user.id,
            question_id="city",
            raw_text="Київ",
            idempotency_key="same-key",
            source="telegram",
            extractor=extractor,
        )

        assert first.id == second.id
        assert extractor.calls == 1  # not called again on the duplicate

        from sqlalchemy import func, select

        from app.db.models_assessment import Answer

        count = (
            await session.execute(select(func.count()).select_from(Answer).where(Answer.session_id == interview_session.id))
        ).scalar_one()
        assert count == 1


async def test_paused_session_auto_resumes_to_active_on_valid_answer(session_factory):
    async with session_factory() as session:
        user = await _make_user_with_basic_access(session)
        interview_session = await start_assessment(session, user_id=user.id, plan_code="BASIC")
        await submit_answer(
            session, session_id=interview_session.id, user_id=user.id, question_id="current_status",
            raw_text="working", idempotency_key="k1", source="telegram",
        )
        await pause_assessment(session, session_id=interview_session.id, user_id=user.id)
        await session.refresh(interview_session)
        assert interview_session.status == AssessmentStatus.PAUSED

        await submit_answer(
            session, session_id=interview_session.id, user_id=user.id, question_id="name",
            raw_text="Олена", idempotency_key="k2", source="telegram",
            extractor=FakeExtractor([ExtractionResult("Олена", 0.9, False)]),
        )
        await session.refresh(interview_session)
        assert interview_session.status == AssessmentStatus.ACTIVE


async def test_completed_session_rejects_new_answers(session_factory):
    async with session_factory() as session:
        user = await _make_user_with_basic_access(session)
        interview_session = await start_assessment(session, user_id=user.id, plan_code="BASIC")

        # answer every required dimension to satisfy the minimum-data rule
        answers = {
            "name": "Олена", "city": "Київ", "current_status": "working",
            "key_skills_or_interests": "Python", "desired_direction_hint": "IT",
        }
        for i, (qid, text) in enumerate(answers.items()):
            extractor = None if qid == "current_status" else FakeExtractor([ExtractionResult(text, 0.9, False)])
            await submit_answer(
                session, session_id=interview_session.id, user_id=user.id, question_id=qid,
                raw_text=text, idempotency_key=f"k{i}", source="telegram", extractor=extractor,
            )

        await complete_assessment(session, session_id=interview_session.id, user_id=user.id)
        await session.refresh(interview_session)
        assert interview_session.status.value == "ready"

        with pytest.raises(InvalidStateTransitionError):
            await submit_answer(
                session, session_id=interview_session.id, user_id=user.id, question_id="constraints",
                raw_text="none", idempotency_key="after-complete", source="telegram",
            )


async def test_cannot_start_second_assessment_while_one_is_unfinished(session_factory):
    async with session_factory() as session:
        user = await _make_user_with_basic_access(session)
        await start_assessment(session, user_id=user.id, plan_code="BASIC")

        with pytest.raises(UnfinishedAssessmentExistsError):
            await start_assessment(session, user_id=user.id, plan_code="BASIC")


async def test_can_start_new_assessment_after_previous_one_completed(session_factory):
    async with session_factory() as session:
        user = await _make_user_with_basic_access(session)
        first = await start_assessment(session, user_id=user.id, plan_code="BASIC")

        answers = {
            "name": "Олена", "city": "Київ", "current_status": "working",
            "key_skills_or_interests": "Python", "desired_direction_hint": "IT",
        }
        for i, (qid, text) in enumerate(answers.items()):
            extractor = None if qid == "current_status" else FakeExtractor([ExtractionResult(text, 0.9, False)])
            await submit_answer(
                session, session_id=first.id, user_id=user.id, question_id=qid,
                raw_text=text, idempotency_key=f"k{i}", source="telegram", extractor=extractor,
            )
        await complete_assessment(session, session_id=first.id, user_id=user.id)

        second = await start_assessment(session, user_id=user.id, plan_code="BASIC")
        assert second.id != first.id


async def test_cannot_submit_answer_to_another_users_session(session_factory):
    async with session_factory() as session:
        owner = await _make_user_with_basic_access(session)
        interview_session = await start_assessment(session, user_id=owner.id, plan_code="BASIC")

        intruder = IdentityUser()
        session.add(intruder)
        await session.commit()
        await session.refresh(intruder)

        with pytest.raises(AssessmentOwnershipError):
            await submit_answer(
                session, session_id=interview_session.id, user_id=intruder.id, question_id="city",
                raw_text="Львів", idempotency_key="k1", source="telegram",
            )
