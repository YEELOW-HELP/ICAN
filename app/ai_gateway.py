"""AI Gateway (docs/architecture/04_AI_SYSTEM.md): the single seam between
business services and LLM providers. "No business service calls an LLM
provider directly" — this module is where that call happens instead.

Sprint 0 Part 4 (Issue #12) scope: wrap the one direct Anthropic call ICAN
1.1 currently makes (`ScreeningAgent`, previously the only remaining
`AsyncAnthropic` call site in the app) exactly as-is — same model, same tool
schema, same system prompt, same behavior — while starting to capture the
metadata the target architecture requires per-call: task name, prompt
version, trace id, token counts, latency, estimated cost. Nothing about how
the call is made changes yet; this only introduces the seam.

Deliberately out of scope here: retries/fallback providers, schema
validation of the structured output (still done by the caller, as before),
and persisted trace storage — no `AITrace` table exists in the schema yet
(tracked in `docs/engineering/11_TECHNICAL_DEBT_REGISTER.md` alongside the
similarly-undefined `AuditLog`). Traces are structured-logged instead until
that lands.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any

from anthropic import AsyncAnthropic

from app.core.config import settings

logger = logging.getLogger("app.ai_gateway")

# Published per-million-token USD pricing, keyed by model. Used only to
# estimate cost for observability logging — never billed against this.
_PRICE_PER_MTOK_USD: dict[str, tuple[float, float]] = {
    # model: (input, output)
    "claude-sonnet-5": (3.0, 15.0),
}


@dataclass(frozen=True)
class GatewayTrace:
    """The per-call metadata docs/architecture/04_AI_SYSTEM.md requires the
    gateway to capture, regardless of where it eventually gets persisted."""

    trace_id: str
    task_name: str
    provider: str
    model: str
    prompt_version: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    estimated_cost_usd: float | None
    retry_count: int
    stop_reason: str | None


@dataclass(frozen=True)
class GatewayResult:
    """`tool_input` is the extracted tool-use payload (None if the model
    didn't call the tool at all — callers already handle that as a fallback
    case). `raw_content` is kept for callers that need the full content
    block list; today none do beyond finding the tool_use block, which the
    gateway already does."""

    tool_input: dict[str, Any] | None
    raw_content: list[Any]
    trace: GatewayTrace


class AIGateway:
    def __init__(self, client: AsyncAnthropic | None = None) -> None:
        self._client = client or AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def call_tool(
        self,
        *,
        task_name: str,
        prompt_version: str,
        model: str,
        system: str,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
        tool_choice: dict[str, Any],
        max_tokens: int,
    ) -> GatewayResult:
        """Forces a specific tool call and returns its structured input,
        exactly the pattern ScreeningAgent already relied on — this method
        doesn't change that contract, only wraps it."""
        trace_id = str(uuid.uuid4())
        started = time.monotonic()

        response = await self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            tools=tools,
            tool_choice=tool_choice,
            messages=messages,
        )

        latency_ms = (time.monotonic() - started) * 1000
        usage = getattr(response, "usage", None)
        input_tokens = getattr(usage, "input_tokens", 0) or 0
        output_tokens = getattr(usage, "output_tokens", 0) or 0
        stop_reason = getattr(response, "stop_reason", None)

        trace = GatewayTrace(
            trace_id=trace_id,
            task_name=task_name,
            provider="anthropic",
            model=model,
            prompt_version=prompt_version,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            estimated_cost_usd=_estimate_cost_usd(model, input_tokens, output_tokens),
            retry_count=0,
            stop_reason=stop_reason,
        )

        logger.info(
            "ai_gateway_call task=%s prompt_version=%s model=%s trace_id=%s "
            "input_tokens=%d output_tokens=%d latency_ms=%.1f estimated_cost_usd=%s stop_reason=%s",
            task_name,
            prompt_version,
            model,
            trace_id,
            input_tokens,
            output_tokens,
            latency_ms,
            trace.estimated_cost_usd,
            stop_reason,
        )

        content = list(response.content)
        tool_use = next((block for block in content if getattr(block, "type", None) == "tool_use"), None)

        return GatewayResult(
            tool_input=tool_use.input if tool_use is not None else None,
            raw_content=content,
            trace=trace,
        )


def _estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float | None:
    prices = _PRICE_PER_MTOK_USD.get(model)
    if prices is None:
        return None
    in_price, out_price = prices
    return (input_tokens / 1_000_000) * in_price + (output_tokens / 1_000_000) * out_price
