"""Regression baseline for Issue #12 checklist: "ошибки/недоступность AI
provider" — the candidate must get a graceful reply, and the bot must not
crash, if the screening agent raises (rate limit, timeout, provider outage,
malformed API response surfaced as an exception rather than a bad payload)."""

from app.bot.handlers import TURN_ERROR_REPLY
from app.core.config import settings
from tests.bot_harness import BotHarness


class ExplodingAgent:
    """Simulates any exception from the AI provider (e.g. anthropic.APIError,
    a timeout, a connection failure) surfacing out of `process_message`."""

    def __init__(self, exc: Exception):
        self._exc = exc
        self.calls = 0

    async def process_message(self, history, current_profile, user_message):
        self.calls += 1
        raise self._exc


async def test_ai_provider_exception_during_chat_gets_graceful_reply_not_a_crash(session_factory, monkeypatch):
    monkeypatch.setattr(settings, "debounce_seconds", 0.05)
    agent = ExplodingAgent(ConnectionError("Anthropic API unreachable"))
    harness = BotHarness(session_factory, agent)
    telegram_id = 777

    await harness.click(telegram_id, "method:chat")
    await harness.send_text(telegram_id, "привіт, я шукаю роботу")
    import asyncio

    await asyncio.sleep(settings.debounce_seconds + 0.15)

    assert agent.calls == 1
    assert harness.last_sent_text() == TURN_ERROR_REPLY


async def test_bot_keeps_working_for_the_user_after_a_provider_failure(session_factory, monkeypatch):
    """One bad turn must not wedge the conversation — a subsequent message
    should reach the agent again, not repeat the error forever from stale
    state."""
    monkeypatch.setattr(settings, "debounce_seconds", 0.05)

    class FlakyAgent:
        def __init__(self):
            self.calls = 0

        async def process_message(self, history, current_profile, user_message):
            self.calls += 1
            if self.calls == 1:
                raise TimeoutError("provider timed out")
            from app.schemas.profile import ProfileDraft
            from app.services.screening import ScreeningResult

            return ScreeningResult(profile=ProfileDraft(city="Львів"), reply_to_user="Яку роботу шукаєш?", ready_for_confirmation=False)

    import asyncio

    agent = FlakyAgent()
    harness = BotHarness(session_factory, agent)
    telegram_id = 778

    await harness.click(telegram_id, "method:chat")
    await harness.send_text(telegram_id, "перше повідомлення")
    await asyncio.sleep(settings.debounce_seconds + 0.15)
    assert harness.last_sent_text() == TURN_ERROR_REPLY

    await harness.send_text(telegram_id, "друге повідомлення")
    await asyncio.sleep(settings.debounce_seconds + 0.15)
    assert agent.calls == 2
    assert harness.last_sent_text() == "Яку роботу шукаєш?"
