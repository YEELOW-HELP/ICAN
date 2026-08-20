from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.schemas.profile import ProfileDraft
from app.services.screening import FALLBACK_REPLY, ScreeningAgent


def _fake_client(tool_input: dict, stop_reason: str = "tool_use"):
    block = SimpleNamespace(type="tool_use", input=tool_input)
    response = SimpleNamespace(content=[block], stop_reason=stop_reason)
    client = SimpleNamespace(messages=SimpleNamespace(create=AsyncMock(return_value=response)))
    return client


def _fake_client_no_tool_use():
    """Simulates a response truncated (e.g. by max_tokens) before any tool_use
    block was emitted at all — a more extreme case of the same failure mode."""
    response = SimpleNamespace(content=[], stop_reason="max_tokens")
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


async def test_process_message_falls_back_when_reply_to_user_is_missing():
    # Claude's tool `required` list is a strong hint, not a guarantee — this
    # reproduces a real failure seen in production where the model omitted
    # reply_to_user, which used to crash the whole turn with a KeyError.
    client = _fake_client({"profile": {"city": "Харків"}, "ready_for_confirmation": False})
    agent = ScreeningAgent(client=client)

    result = await agent.process_message(history=[], current_profile=ProfileDraft(), user_message="Харків")

    assert result.reply_to_user == FALLBACK_REPLY
    assert result.profile.city == "Харків"  # extraction still applied even though reply text was missing


async def test_process_message_falls_back_when_no_tool_use_block_present():
    client = _fake_client_no_tool_use()
    agent = ScreeningAgent(client=client)

    result = await agent.process_message(history=[], current_profile=ProfileDraft(name="Олена"), user_message="...")

    assert result.reply_to_user == FALLBACK_REPLY
    assert result.ready_for_confirmation is False
    assert result.profile.name == "Олена"  # nothing lost from the existing profile
