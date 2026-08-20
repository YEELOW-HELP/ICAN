from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_crm import TimelineEvent, TimelineEventType


async def record_event(
    session: AsyncSession,
    *,
    client_id: int,
    event_type: TimelineEventType,
    description: str,
    actor_id: int | None = None,
    before_value: str | None = None,
    after_value: str | None = None,
    commit: bool = True,
) -> TimelineEvent:
    """Single write path for both the client's activity timeline (ТЗ §16)
    and the audit trail (ТЗ §21) — they're the same underlying event log,
    just filtered differently depending on who's viewing it."""
    event = TimelineEvent(
        client_id=client_id,
        event_type=event_type,
        actor_id=actor_id,
        description=description,
        before_value=before_value,
        after_value=after_value,
    )
    session.add(event)
    if commit:
        await session.commit()
    return event


async def list_events(session: AsyncSession, client_id: int) -> list[TimelineEvent]:
    result = await session.execute(
        select(TimelineEvent).where(TimelineEvent.client_id == client_id).order_by(TimelineEvent.created_at.desc())
    )
    return list(result.scalars().all())
