from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AdminUser
from app.db.models_crm import Call, CallDirection, CallStatus, Client, TimelineEventType
from app.services.crm import clients as client_service
from app.services.crm import timeline


async def log_call(session: AsyncSession, client: Client, data: dict, actor: AdminUser) -> Call:
    """Manual call logging — used until the Phonet integration is wired up
    (ТЗ §15.3 keeps this as a legitimate fallback: `phonet_call_id` stays
    null for manually-logged calls, and a real webhook handler can populate
    it later without changing this table's shape)."""
    call = Call(
        client_id=client.id,
        employee_id=actor.id,
        direction=CallDirection(data["direction"]),
        status=CallStatus(data["status"]),
        duration_seconds=data.get("duration_seconds"),
        contact_type=data.get("contact_type"),
        note=data.get("note"),
    )
    session.add(call)
    await session.commit()
    await session.refresh(call)

    await client_service.touch_activity(session, client)
    await timeline.record_event(
        session,
        client_id=client.id,
        event_type=TimelineEventType.CALL,
        description=f"Дзвінок ({call.direction.value}, {call.status.value})",
        actor_id=actor.id,
    )
    return call


async def list_calls(session: AsyncSession, client_id: int) -> list[Call]:
    result = await session.execute(select(Call).where(Call.client_id == client_id).order_by(Call.started_at.desc()))
    return list(result.scalars().all())
