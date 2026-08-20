from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.schemas.profile import ProfileDraft
from app.services.screening import ScreeningAgent


def _fake_client(tool_input: dict):
    block = SimpleNamespace(type="tool_use", input=tool_input)
    response = SimpleNamespace(content=[block])
    client = SimpleNamespace(messages=SimpleNamespace(create=AsyncMock(return_value=response)))
    return client


async def test_process_message_merges_new_facts_onto_existing_profile():
    client = _fake_client(
        {
            "profile": {"city": "Харків", "total_experience": "8 років"},
            "reply_to_user": "Яку освіту ви маєте?",
            "ready_for_confirmation": False,
        }
    )
    agent = ScreeningAgent(client=client)

    current = ProfileDraft(name="Олена")
    result = await agent.process_message(history=[], current_profile=current, user_message="8 років досвіду")

    assert result.profile.name == "Олена"  # preserved, not overwritten
    assert result.profile.city == "Харків"
    assert result.profile.total_experience == "8 років"
    assert result.ready_for_confirmation is False
    assert result.reply_to_user == "Яку освіту ви маєте?"


async def test_process_message_never_lets_null_fields_erase_known_facts():
    client = _fake_client(
        {
            "profile": {"city": None, "country": None},
            "reply_to_user": "Продовжимо?",
            "ready_for_confirmation": False,
        }
    )
    agent = ScreeningAgent(client=client)

    current = ProfileDraft(city="Харків")
    result = await agent.process_message(history=[], current_profile=current, user_message="так")

    assert result.profile.city == "Харків"


async def test_process_message_reports_ready_for_confirmation():
    client = _fake_client(
        {
            "profile": {},
            "reply_to_user": "Ось що я про вас зрозумів: ...",
            "ready_for_confirmation": True,
        }
    )
    agent = ScreeningAgent(client=client)

    result = await agent.process_message(history=[], current_profile=ProfileDraft(), user_message="все вірно")

    assert result.ready_for_confirmation is True
