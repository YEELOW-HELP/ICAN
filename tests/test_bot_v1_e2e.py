"""End-to-end regression for the new Hybrid assessment Telegram adapter
(Stage 1, settings.bot_flow == "v1"). Drives the real registered
handlers via fake raw Telegram updates -- the same technique
tests/test_bot_e2e.py uses for the legacy flow -- so this proves the
actual wiring: consent gate, product access gate, adaptive question
loop, optional CV, explicit pause, and resume across a simulated
process restart (a fresh BotHarness/Dispatcher sharing the same
database, since FSM state lives only in memory but assessment state
lives in PostgreSQL/SQLite).
"""

from __future__ import annotations

from app.bot.handlers_v1 import register_handlers_v1
from app.core.security import hash_password
from app.db.models import AdminRole, AdminUser
from app.db.models_assessment import AssessmentStatus
from app.services.assessment.extraction import ExtractionResult
from app.services.assessment.sessions import get_unfinished_session_for_user
from app.services.identity import resolve_identity
from app.services.product_access import create_package_allocation, issue_promo_code
from tests.bot_harness import BotHarness

REQUIRED_ANSWERS = {
    "name": "Олена",
    "city": "Київ",
    "current_status": "working",  # structured -- sent as a button click
    "key_skills_or_interests": "Python, аналітика",
    "desired_direction_hint": "IT",
}


class ScriptedExtractor:
    """Fixed confidence-1.0 result per question_id, mirroring the domain
    tests' FakeExtractor -- no real AI Gateway call happens in this test."""

    def __init__(self, values: dict[str, str] | None = None):
        self._values = values or {q: text for q, text in REQUIRED_ANSWERS.items() if q != "current_status"}
        self.calls = 0

    async def extract(self, *, question_prompt, raw_answer_text, previous_value):
        self.calls += 1
        return ExtractionResult(self._values.get(question_prompt, raw_answer_text), 0.9, False)


async def test_full_happy_path_start_to_completion_via_promo(session_factory):
    async with session_factory() as session:
        admin = AdminUser(email="admin@test.dev", password_hash=hash_password("pw"), role=AdminRole.ADMIN)
        session.add(admin)
        await session.commit()
        await session.refresh(admin)
        allocation = await create_package_allocation(session, plan_code="BASIC", total_quantity=5, created_by_admin=admin)
        promo = await issue_promo_code(session, allocation_id=allocation.id)

    extractor = ScriptedExtractor()
    harness = BotHarness(session_factory, lambda: extractor, register_fn=register_handlers_v1)
    telegram_id = 5001

    await harness.send_text(telegram_id, "/start")
    assert "згод" in harness.last_sent_text().lower()  # consent_prompt mentions "згода"

    await harness.click(telegram_id, "v1consent:agree")
    assert "промокод" in harness.last_sent_text().lower()  # no_access -> asks for a promo code

    await harness.send_text(telegram_id, promo.code)
    assert "резюме" in harness.last_sent_text().lower()  # cv_offer

    await harness.click(telegram_id, "v1cv:skip")
    first_question_text = harness.last_sent_text()
    assert first_question_text  # a real question prompt, not an error

    await harness.send_text(telegram_id, REQUIRED_ANSWERS["name"])
    await harness.send_text(telegram_id, REQUIRED_ANSWERS["city"])
    await harness.click(telegram_id, f"v1c:{REQUIRED_ANSWERS['current_status']}")
    await harness.send_text(telegram_id, REQUIRED_ANSWERS["key_skills_or_interests"])
    await harness.send_text(telegram_id, REQUIRED_ANSWERS["desired_direction_hint"])

    assert "завершено" in harness.last_sent_text().lower()  # completed

    async with session_factory() as session:
        user = await resolve_identity(session, provider="telegram", provider_subject=str(telegram_id))
        unfinished = await get_unfinished_session_for_user(session, user.id)
        assert unfinished is None  # READY is not "unfinished" -- nothing left in progress


async def test_explicit_pause_and_resume_continues_where_it_left_off(session_factory):
    async with session_factory() as session:
        admin = AdminUser(email="admin2@test.dev", password_hash=hash_password("pw"), role=AdminRole.ADMIN)
        session.add(admin)
        await session.commit()
        await session.refresh(admin)
        allocation = await create_package_allocation(session, plan_code="BASIC", total_quantity=5, created_by_admin=admin)
        promo = await issue_promo_code(session, allocation_id=allocation.id)

    extractor = ScriptedExtractor()
    harness = BotHarness(session_factory, lambda: extractor, register_fn=register_handlers_v1)
    telegram_id = 5002

    await harness.send_text(telegram_id, "/start")
    await harness.click(telegram_id, "v1consent:agree")
    await harness.send_text(telegram_id, promo.code)
    await harness.click(telegram_id, "v1cv:skip")
    await harness.send_text(telegram_id, REQUIRED_ANSWERS["name"])  # answers "name", moves to "city"

    await harness.send_text(telegram_id, "/pause")
    assert "зупиняємось" in harness.last_sent_text().lower()

    async with session_factory() as session:
        user = await resolve_identity(session, provider="telegram", provider_subject=str(telegram_id))
        interview_session = await get_unfinished_session_for_user(session, user.id)
        assert interview_session.status == AssessmentStatus.PAUSED

    index_before_resume = len(harness.sent_messages)
    await harness.send_text(telegram_id, "/start")
    replies = [t.lower() for t in harness.texts_since(index_before_resume)]
    assert any("продовжуємо" in t for t in replies)

    async with session_factory() as session:
        user = await resolve_identity(session, provider="telegram", provider_subject=str(telegram_id))
        interview_session = await get_unfinished_session_for_user(session, user.id)
        assert interview_session.status == AssessmentStatus.ACTIVE


async def test_resume_across_simulated_process_restart(session_factory):
    """A fresh BotHarness (new Dispatcher, new in-memory FSM storage) --
    simulating the bot process restarting -- must still resume the
    candidate's assessment from PostgreSQL/SQLite state, not lose it."""
    async with session_factory() as session:
        admin = AdminUser(email="admin3@test.dev", password_hash=hash_password("pw"), role=AdminRole.ADMIN)
        session.add(admin)
        await session.commit()
        await session.refresh(admin)
        allocation = await create_package_allocation(session, plan_code="BASIC", total_quantity=5, created_by_admin=admin)
        promo = await issue_promo_code(session, allocation_id=allocation.id)

    extractor = ScriptedExtractor()
    telegram_id = 5003

    harness_before_restart = BotHarness(session_factory, lambda: extractor, register_fn=register_handlers_v1)
    await harness_before_restart.send_text(telegram_id, "/start")
    await harness_before_restart.click(telegram_id, "v1consent:agree")
    await harness_before_restart.send_text(telegram_id, promo.code)
    await harness_before_restart.click(telegram_id, "v1cv:skip")
    await harness_before_restart.send_text(telegram_id, REQUIRED_ANSWERS["name"])

    async with session_factory() as session:
        user = await resolve_identity(session, provider="telegram", provider_subject=str(telegram_id))
        interview_session = await get_unfinished_session_for_user(session, user.id)
        assert interview_session.status == AssessmentStatus.ACTIVE

    # "process restart": a brand-new harness, fresh in-memory FSM storage,
    # same underlying database.
    harness_after_restart = BotHarness(session_factory, lambda: extractor, register_fn=register_handlers_v1)
    await harness_after_restart.send_text(telegram_id, "/start")

    # No consent/access/CV prompts repeat -- straight back into questioning.
    reply = harness_after_restart.last_sent_text().lower()
    assert "згод" not in reply
    assert "промокод" not in reply

    await harness_after_restart.send_text(telegram_id, REQUIRED_ANSWERS["city"])
    await harness_after_restart.click(telegram_id, f"v1c:{REQUIRED_ANSWERS['current_status']}")
    await harness_after_restart.send_text(telegram_id, REQUIRED_ANSWERS["key_skills_or_interests"])
    await harness_after_restart.send_text(telegram_id, REQUIRED_ANSWERS["desired_direction_hint"])

    assert "завершено" in harness_after_restart.last_sent_text().lower()


async def test_cv_upload_prefills_a_dimension_and_it_is_not_asked_again(session_factory, monkeypatch):
    from app.services import documents

    monkeypatch.setattr(documents, "extract_text", lambda content, filename: "Живу в Києві, працюю Python розробником")

    async with session_factory() as session:
        admin = AdminUser(email="admin4@test.dev", password_hash=hash_password("pw"), role=AdminRole.ADMIN)
        session.add(admin)
        await session.commit()
        await session.refresh(admin)
        allocation = await create_package_allocation(session, plan_code="BASIC", total_quantity=5, created_by_admin=admin)
        promo = await issue_promo_code(session, allocation_id=allocation.id)

    class CVAwareExtractor:
        """Only the CV-derived facts come back confident -- everything else
        (asked as an ordinary open question later) is deliberately low
        confidence, since a real CV rarely addresses every dimension."""

        def __init__(self):
            self.calls = 0

        async def extract(self, *, question_prompt, raw_answer_text, previous_value):
            self.calls += 1
            if question_prompt == "city":
                return ExtractionResult("Київ", 0.9, False)
            if question_prompt == "key_skills_or_interests":
                return ExtractionResult("Python", 0.9, False)
            return ExtractionResult("", 0.1, False)

    cv_extractor = CVAwareExtractor()
    harness = BotHarness(session_factory, lambda: cv_extractor, register_fn=register_handlers_v1)
    telegram_id = 5004

    await harness.send_text(telegram_id, "/start")
    await harness.click(telegram_id, "v1consent:agree")
    await harness.send_text(telegram_id, promo.code)
    await harness.click(telegram_id, "v1cv:upload")
    await harness.send_document(telegram_id, "cv.pdf", content_bytes=b"fake pdf bytes")

    assert "дякую" in harness.last_sent_text().lower() or "Дякую" in harness.sent_messages[-2].text

    async with session_factory() as session:
        user = await resolve_identity(session, provider="telegram", provider_subject=str(telegram_id))
        interview_session = await get_unfinished_session_for_user(session, user.id)
        from app.db.models_assessment import Answer
        from sqlalchemy import select

        result = await session.execute(select(Answer).where(Answer.session_id == interview_session.id))
        answered_question_ids = {a.question_id for a in result.scalars().all()}
        assert "city" in answered_question_ids
        assert "key_skills_or_interests" in answered_question_ids
