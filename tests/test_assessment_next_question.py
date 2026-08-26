from sqlalchemy import func, select

from app.core.security import hash_password
from app.db.models import AdminRole, AdminUser
from app.db.models_assessment import QuestionSelection, SelectionReason
from app.db.models_identity import IdentityUser
from app.services.assessment.extraction import ExtractionResult
from app.services.assessment.sessions import get_next_question_for_session, start_assessment, submit_answer
from app.services.product_access import grant_manual_access


class FakeExtractor:
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


async def test_first_call_selects_a_missing_required_question_with_reason(session_factory):
    async with session_factory() as session:
        user = await _make_user_with_basic_access(session)
        interview_session = await start_assessment(session, user_id=user.id, plan_code="BASIC")

        result = await get_next_question_for_session(session, session_id=interview_session.id, user_id=user.id)

        assert result.ready_for_completion is False
        assert result.question is not None
        assert result.reason == SelectionReason.MISSING

        selection_count = (
            await session.execute(select(func.count()).select_from(QuestionSelection).where(QuestionSelection.session_id == interview_session.id))
        ).scalar_one()
        assert selection_count == 1


async def test_resolved_question_is_never_reselected(session_factory):
    async with session_factory() as session:
        user = await _make_user_with_basic_access(session)
        interview_session = await start_assessment(session, user_id=user.id, plan_code="BASIC")

        await submit_answer(
            session, session_id=interview_session.id, user_id=user.id, question_id="city",
            raw_text="Київ", idempotency_key="k1", source="telegram",
            extractor=FakeExtractor([ExtractionResult("Київ", 0.95, False)]),
        )

        for _ in range(10):
            result = await get_next_question_for_session(session, session_id=interview_session.id, user_id=user.id)
            if result.question is not None:
                assert result.question.question_id != "city"
            if result.ready_for_completion:
                break


async def test_low_confidence_answer_triggers_reselection_with_reason(session_factory):
    async with session_factory() as session:
        user = await _make_user_with_basic_access(session)
        interview_session = await start_assessment(session, user_id=user.id, plan_code="BASIC")

        await submit_answer(
            session, session_id=interview_session.id, user_id=user.id, question_id="city",
            raw_text="не знаю", idempotency_key="k1", source="telegram",
            extractor=FakeExtractor([ExtractionResult("не знаю", 0.2, False)]),
        )

        # keep asking until "city" resurfaces (other missing questions may come first)
        seen_city_with_low_confidence = False
        for _ in range(10):
            result = await get_next_question_for_session(session, session_id=interview_session.id, user_id=user.id)
            if result.question is not None and result.question.question_id == "city":
                assert result.reason == SelectionReason.LOW_CONFIDENCE
                seen_city_with_low_confidence = True
                break
            if result.question is None:
                break
            # answer whatever else was asked so the loop can progress to "city" again
            await submit_answer(
                session, session_id=interview_session.id, user_id=user.id, question_id=result.question.question_id,
                raw_text="placeholder", idempotency_key=f"filler-{result.question.question_id}", source="telegram",
                extractor=FakeExtractor([ExtractionResult("placeholder", 0.95, False)]),
            )
        assert seen_city_with_low_confidence


async def test_contradiction_triggers_reselection_with_reason(session_factory):
    async with session_factory() as session:
        user = await _make_user_with_basic_access(session)
        interview_session = await start_assessment(session, user_id=user.id, plan_code="BASIC")

        await submit_answer(
            session, session_id=interview_session.id, user_id=user.id, question_id="city",
            raw_text="Київ", idempotency_key="k1", source="telegram",
            extractor=FakeExtractor([ExtractionResult("Київ", 0.9, False)]),
        )
        await submit_answer(
            session, session_id=interview_session.id, user_id=user.id, question_id="city",
            raw_text="насправді Львів", idempotency_key="k2", source="telegram",
            extractor=FakeExtractor([ExtractionResult("Львів", 0.9, True)]),
        )

        result = await get_next_question_for_session(session, session_id=interview_session.id, user_id=user.id)
        assert result.question is not None
        assert result.question.question_id == "city"
        assert result.reason == SelectionReason.CONTRADICTION


async def test_question_selection_links_to_resulting_answer(session_factory):
    async with session_factory() as session:
        user = await _make_user_with_basic_access(session)
        interview_session = await start_assessment(session, user_id=user.id, plan_code="BASIC")

        result = await get_next_question_for_session(session, session_id=interview_session.id, user_id=user.id)
        question_id = result.question.question_id

        answer = await submit_answer(
            session, session_id=interview_session.id, user_id=user.id, question_id=question_id,
            raw_text="answer text", idempotency_key="k1", source="telegram",
            extractor=FakeExtractor([ExtractionResult("answer text", 0.9, False)]) if question_id != "current_status" else None,
        )

        selection = (
            await session.execute(
                select(QuestionSelection).where(QuestionSelection.session_id == interview_session.id, QuestionSelection.question_id == question_id)
            )
        ).scalar_one()
        assert selection.answer_id == answer.id
        assert selection.answered_at is not None


async def test_all_required_resolved_means_ready_for_completion(session_factory):
    async with session_factory() as session:
        user = await _make_user_with_basic_access(session)
        interview_session = await start_assessment(session, user_id=user.id, plan_code="BASIC")

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

        result = await get_next_question_for_session(session, session_id=interview_session.id, user_id=user.id)
        assert result.ready_for_completion is True
        assert result.question is None


async def test_safety_cap_forces_completion_eligibility_even_with_unresolved_dimensions(session_factory, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "max_assessment_questions", 2)

    async with session_factory() as session:
        user = await _make_user_with_basic_access(session)
        interview_session = await start_assessment(session, user_id=user.id, plan_code="BASIC")

        # exhaust the cap with two selections, never answering anything
        for _ in range(2):
            result = await get_next_question_for_session(session, session_id=interview_session.id, user_id=user.id)
            assert result.terminated_by_safety_cap is False

        capped_result = await get_next_question_for_session(session, session_id=interview_session.id, user_id=user.id)
        assert capped_result.terminated_by_safety_cap is True
        assert capped_result.ready_for_completion is True
        assert capped_result.question is None
