"""End-to-end regression tests for the Telegram bot: real registered
handlers, real FSM, real debounce timing -- only the Telegram API network
boundary and the AI provider are faked. These lock down ICAN 1.1's actual
user-facing behavior as a baseline before the v3.1 migration touches
anything underneath it (Issue #12 / Sprint 0)."""

import asyncio

from sqlalchemy import select

from app.core.config import settings
from app.db.models import ScreeningState, User
from app.schemas.profile import ProfileDraft
from app.services.crm import clients as client_service
from app.services.screening import ScreeningResult
from tests.bot_harness import BotHarness


class ScriptedAgent:
    """Fake ScreeningAgent that returns a pre-scripted sequence of results
    and records how many times it was actually called -- lets tests assert
    the AI is (or is NOT) invoked without hitting a real provider."""

    def __init__(self, results: list[ScreeningResult]):
        self._results = list(results)
        self.calls = 0

    async def process_message(self, history, current_profile, user_message):
        self.calls += 1
        return self._results.pop(0)


async def _wait_for_debounce():
    await asyncio.sleep(settings.debounce_seconds + 0.15)


def _button_texts(message):
    if not message.reply_markup:
        return []
    return [b.text for row in message.reply_markup.inline_keyboard for b in row]


async def test_start_sends_onboarding_with_two_buttons(session_factory):
    harness = BotHarness(session_factory, ScriptedAgent([]))

    await harness.send_text(111, "/start")

    assert len(harness.sent_messages) == 1
    msg = harness.sent_messages[0]
    assert "Привіт! Я ICAN" in msg.text
    buttons = _button_texts(msg)
    assert any("Почати" in b for b in buttons)
    assert any("резюме" in b for b in buttons)


async def test_telegram_screening_happy_path_through_confirmation(session_factory, monkeypatch):
    """The core loop: /start -> choose chat -> converse -> confirm. Also
    verifies the bot->CRM bridge fires as a side effect of real confirmation
    (not just the isolated service-level test in test_crm_bridge.py)."""
    monkeypatch.setattr(settings, "debounce_seconds", 0.05)

    agent = ScriptedAgent(
        [
            ScreeningResult(
                profile=ProfileDraft(city="Харків"),
                reply_to_user="Яку роботу шукаєш?",
                ready_for_confirmation=False,
            ),
            ScreeningResult(
                profile=ProfileDraft(city="Харків", desired_role="водій"),
                reply_to_user="Твій профіль\n\nШукаєш: водій\nМісто: Харків",
                ready_for_confirmation=True,
            ),
        ]
    )
    harness = BotHarness(session_factory, agent)
    telegram_id = 222

    await harness.send_text(telegram_id, "/start")
    await harness.click(telegram_id, "onb:start")
    await harness.click(telegram_id, "method:chat")
    assert "Розкажи трохи про себе" in harness.last_sent_text()

    await harness.send_text(telegram_id, "Я з Харкова")
    await _wait_for_debounce()
    assert agent.calls == 1
    assert harness.last_sent_text() == "Яку роботу шукаєш?"

    await harness.send_text(telegram_id, "Шукаю роботу водієм")
    await _wait_for_debounce()
    assert agent.calls == 2
    confirm_msg = harness.sent_messages[-1]
    assert "Твій профіль" in confirm_msg.text
    assert any("правильно" in b for b in _button_texts(confirm_msg))

    await harness.click(telegram_id, "profile_confirm")
    assert "збережено" in harness.last_sent_text()

    async with session_factory() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one()
        assert user.screening_state == ScreeningState.CONFIRMED

        client = await client_service.get_client_by_telegram_user(session, user.id)
        assert client is not None, "bot confirmation must create a linked CRM client"
        assert client.profile.primary_target == "водій"


async def test_profile_edit_returns_to_chat_and_screens_again(session_factory, monkeypatch):
    monkeypatch.setattr(settings, "debounce_seconds", 0.05)
    agent = ScriptedAgent(
        [
            ScreeningResult(profile=ProfileDraft(city="Київ"), reply_to_user="Твій профіль", ready_for_confirmation=True),
            ScreeningResult(profile=ProfileDraft(city="Львів"), reply_to_user="Оновлено", ready_for_confirmation=False),
        ]
    )
    harness = BotHarness(session_factory, agent)
    telegram_id = 333

    await harness.click(telegram_id, "method:chat")
    await harness.send_text(telegram_id, "живу в Києві")
    await _wait_for_debounce()
    assert agent.calls == 1

    await harness.click(telegram_id, "profile_edit")
    assert "виправити" in harness.last_sent_text()

    await harness.send_text(telegram_id, "насправді я у Львові")
    await _wait_for_debounce()
    assert agent.calls == 2
    assert harness.last_sent_text() == "Оновлено"


async def test_returning_confirmed_user_sees_profile_card_not_onboarding(session_factory):
    agent = ScriptedAgent([])
    harness = BotHarness(session_factory, agent)
    telegram_id = 444

    async with session_factory() as session:
        from app.services import profile_service

        user = await profile_service.get_or_create_user(session, telegram_id)
        await profile_service.apply_profile_draft(session, user, ProfileDraft(name="Олена", desired_role="бухгалтер"))
        await profile_service.confirm_profile(session, user)

    await harness.send_text(telegram_id, "/start")

    msg = harness.last_sent_text()
    assert "З поверненням" in msg
    assert "бухгалтер" in msg
    assert agent.calls == 0  # returning-user card is rendered from stored data, no AI call


async def test_confirmed_user_message_gets_already_done_without_calling_ai(session_factory, monkeypatch):
    monkeypatch.setattr(settings, "debounce_seconds", 0.05)
    agent = ScriptedAgent([])  # any call would raise IndexError -- proves the AI is never invoked
    harness = BotHarness(session_factory, agent)
    telegram_id = 555

    async with session_factory() as session:
        from app.services import profile_service

        user = await profile_service.get_or_create_user(session, telegram_id)
        await profile_service.confirm_profile(session, user)

    await harness.send_text(telegram_id, "чи можу я щось змінити?")
    await _wait_for_debounce()

    assert agent.calls == 0
    assert "вже проходили скринінг" in harness.last_sent_text()
