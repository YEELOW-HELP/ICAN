from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AdminUser
from app.db.models_crm import CareerConsultation, Client, TimelineEventType
from app.services.crm import timeline

CONSULTATION_FIELDS = [
    "primary_target", "alternative_targets", "strengths", "skills_gaps",
    "search_strategy", "expectations_realistic", "expectations_comment",
]


async def get_or_create_consultation(session: AsyncSession, client_id: int) -> CareerConsultation:
    result = await session.execute(select(CareerConsultation).where(CareerConsultation.client_id == client_id))
    consultation = result.scalar_one_or_none()
    if consultation is not None:
        return consultation

    consultation = CareerConsultation(client_id=client_id)
    session.add(consultation)
    await session.commit()
    await session.refresh(consultation)
    return consultation


async def save_draft(
    session: AsyncSession, consultation: CareerConsultation, changes: dict, actor: AdminUser
) -> CareerConsultation:
    for field, value in changes.items():
        if field in CONSULTATION_FIELDS:
            setattr(consultation, field, value)
    consultation.consultant_id = actor.id
    await session.commit()
    await session.refresh(consultation)
    return consultation


async def complete_consultation(
    session: AsyncSession, client: Client, consultation: CareerConsultation, conclusion: str, actor: AdminUser
) -> CareerConsultation:
    consultation.conclusion = conclusion
    consultation.consultant_id = actor.id
    consultation.completed_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(consultation)

    await timeline.record_event(
        session,
        client_id=client.id,
        event_type=TimelineEventType.CONSULTATION_COMPLETED,
        description="Кар'єрну консультацію завершено",
        actor_id=actor.id,
    )

    # Deliberately does NOT auto-advance to READY_FOR_MATCHING — that's a
    # separate, explicit, validated action (ТЗ §12/§13).
    return consultation
