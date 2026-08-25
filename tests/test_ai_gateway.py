import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.ai_gateway import AIGateway


def _client(content, stop_reason="tool_use", usage=None):
    response = SimpleNamespace(content=content, stop_reason=stop_reason, usage=usage)
    return SimpleNamespace(messages=SimpleNamespace(create=AsyncMock(return_value=response)))


async def test_call_tool_extracts_tool_input_and_trace_metadata():
    block = SimpleNamespace(type="tool_use", input={"reply_to_user": "hi", "ready_for_confirmation": False, "profile": {}})
    usage = SimpleNamespace(input_tokens=120, output_tokens=40)
    gateway = AIGateway(client=_client([block], usage=usage))

    result = await gateway.call_tool(
        task_name="screening_turn",
        prompt_version="legacy-screening-v1",
        model="claude-sonnet-5",
        system="sys",
        messages=[{"role": "user", "content": "hello"}],
        tools=[{"name": "update_profile"}],
        tool_choice={"type": "tool", "name": "update_profile"},
        max_tokens=100,
    )

    assert result.tool_input == {"reply_to_user": "hi", "ready_for_confirmation": False, "profile": {}}
    assert result.trace.task_name == "screening_turn"
    assert result.trace.prompt_version == "legacy-screening-v1"
    assert result.trace.provider == "anthropic"
    assert result.trace.model == "claude-sonnet-5"
    assert result.trace.input_tokens == 120
    assert result.trace.output_tokens == 40
    assert result.trace.stop_reason == "tool_use"
    assert result.trace.latency_ms >= 0
    assert result.trace.retry_count == 0
    uuid.UUID(result.trace.trace_id)  # doesn't raise -- a real, well-formed trace id


async def test_call_tool_returns_none_input_when_no_tool_use_block_present():
    gateway = AIGateway(client=_client([], stop_reason="max_tokens"))

    result = await gateway.call_tool(
        task_name="screening_turn",
        prompt_version="legacy-screening-v1",
        model="claude-sonnet-5",
        system="sys",
        messages=[],
        tools=[],
        tool_choice={"type": "tool", "name": "update_profile"},
        max_tokens=100,
    )

    assert result.tool_input is None
    assert result.trace.stop_reason == "max_tokens"
    # trace metadata is still fully populated even on a degraded response
    assert result.trace.task_name == "screening_turn"


async def test_call_tool_defaults_token_counts_to_zero_when_usage_missing():
    gateway = AIGateway(client=_client([], usage=None))

    result = await gateway.call_tool(
        task_name="screening_turn",
        prompt_version="legacy-screening-v1",
        model="claude-sonnet-5",
        system="sys",
        messages=[],
        tools=[],
        tool_choice={"type": "tool", "name": "update_profile"},
        max_tokens=100,
    )

    assert result.trace.input_tokens == 0
    assert result.trace.output_tokens == 0


async def test_estimated_cost_computed_for_known_model():
    usage = SimpleNamespace(input_tokens=1_000_000, output_tokens=1_000_000)
    gateway = AIGateway(client=_client([], usage=usage))

    result = await gateway.call_tool(
        task_name="screening_turn",
        prompt_version="legacy-screening-v1",
        model="claude-sonnet-5",
        system="sys",
        messages=[],
        tools=[],
        tool_choice={"type": "tool", "name": "update_profile"},
        max_tokens=100,
    )

    assert result.trace.estimated_cost_usd == 3.0 + 15.0


async def test_estimated_cost_is_none_for_unpriced_model():
    usage = SimpleNamespace(input_tokens=1000, output_tokens=1000)
    gateway = AIGateway(client=_client([], usage=usage))

    result = await gateway.call_tool(
        task_name="screening_turn",
        prompt_version="legacy-screening-v1",
        model="some-future-model",
        system="sys",
        messages=[],
        tools=[],
        tool_choice={"type": "tool", "name": "update_profile"},
        max_tokens=100,
    )

    assert result.trace.estimated_cost_usd is None
