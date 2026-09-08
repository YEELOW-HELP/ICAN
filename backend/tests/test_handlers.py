from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.bot.handlers import FORCED_WRAP_UP, _finalize_anketa, _run_screening_turn
from app.core.config import settings
from app.db.models import ScreeningState
from app.schemas.profile import ProfileDraft
from app.services import profile_service
from app.services.screening import ScreeningResult


class _CountingAgent:
    def __init__(self) -> None:
        self.calls = 0
        self.process_message = AsyncMock(side_effect=self._respond)

    async def _respond(self, history, current_profile, user_message):
        self.calls += 1
        return ScreeningResult(profile=current_profile, reply_to_user="Ще одне запитання?", ready_for_confirmation=False)


async def test_screening_stops_calling_the_api_past_the_turn_cap(session, monkeypatch):
    monkeypatch.setattr(settings, "max_screening_turns", 2)
    user = await profile_service.get_or_create_user(session, telegram_id=555)
    agent = _CountingAgent()

    for i in range(5):
        reply, ready = await _run_screening_turn(session, agent, user, f"повідомлення {i}")

    assert agent.calls == 2  # never exceeds the cap, even after 5 user turns
    assert reply.startswith(FORCED_WRAP_UP)  # followed by the profile card, same as any other confirmation
    assert ready is True


async def test_finalize_anketa_saves_profile_and_dialogue_without_any_api_call(session):
    user = await profile_service.get_or_create_user(session, telegram_id=777)
    answers = {
        "city": "Харків",
        "desired_role": "бухгалтер",
        "experience": "5+ років",
        "employment_format": "full-time",
        "work_format": "remote",
        "income": "35000 грн",
    }

    text = await _finalize_anketa(session, user, answers)

    assert "Шукаєш: бухгалтер" in text
    assert "Місто: Харків" in text

    profile = await profile_service.get_profile(session, user)
    assert profile.city == "Харків"
    assert profile.desired_role == "бухгалтер"
    assert user.screening_state == ScreeningState.AWAITING_CONFIRMATION

    messages = await profile_service.get_messages(session, user)
    assert [m.content for m in messages] == [
        "[Анкета] city=Харків; desired_role=бухгалтер; experience=5+ років; "
        "employment_format=full-time; work_format=remote; income=35000 грн",
        text,
    ]
