"""Persist one AI Gateway call's metadata (Founder decision M2;
docs/architecture/02_ERD.md's `AI_TRACE`).

NO secrets, NO PII -- only call metadata (task, provider, model, prompt
version, token counts, latency, cost, status). Never prompt/message/tool
content.

Slice 1: this helper + the `ai_traces` table exist. Wiring `AIGateway`
itself to call this (it needs a DB session plumbed in) is deferred to the
slice that introduces Direction Intelligence's own LLM tasks -- a
deterministic-only slice must not change the Stage 1/2 AI path.
"""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_gateway import GatewayTrace
from app.db.models_platform import AITrace

__all__ = ["record_ai_trace"]


async def record_ai_trace(
    session: AsyncSession, *, trace: GatewayTrace, status: str = "ok", error_type: str | None = None
) -> AITrace | None:
    """Idempotent by `trace_id` -- a duplicate write is a no-op (the same
    call is never traced twice)."""
    row = AITrace(
        trace_id=trace.trace_id,
        task=trace.task_name,
        provider=trace.provider,
        model=trace.model,
        prompt_version=trace.prompt_version,
        latency_ms=int(trace.latency_ms) if trace.latency_ms is not None else None,
        input_tokens=trace.input_tokens,
        output_tokens=trace.output_tokens,
        estimated_cost_usd=trace.estimated_cost_usd,
        status=status,
        error_type=error_type,
    )
    session.add(row)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        return None
    await session.refresh(row)
    return row
