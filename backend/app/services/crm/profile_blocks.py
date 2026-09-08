from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AdminUser
from app.db.models_crm import ClientLanguage, ClientProfile, ClientSkill, SkillLevel, TimelineEventType, WorkExperience
from app.services.crm import timeline

PROFILE_EDITABLE_FIELDS = [
    "currently_employed", "current_position", "current_fields", "current_income", "current_income_currency",
    "search_reasons", "readiness_to_start", "readiness_date", "urgency", "nonstandard_info",
    "consultation_consent",
    "education_level", "specialty", "institution", "graduation_year", "courses", "driver_licenses",
    "other_qualification",
    "primary_target", "alternative_targets", "interesting_fields", "avoid_fields", "open_to_career_change",
    "min_salary", "desired_salary", "salary_currency", "employment_types", "work_formats", "schedules",
    "work_cities", "commute_limit", "relocation_ready", "relocation_cities", "business_trips_ok", "start_date",
    "constraints", "critical_constraint", "constraints_comment",
]


async def update_profile(session: AsyncSession, profile: ClientProfile, changes: dict, actor: AdminUser) -> list[str]:
    changed_fields: list[str] = []
    for field, new_value in changes.items():
        if field not in PROFILE_EDITABLE_FIELDS:
            continue
        old_value = getattr(profile, field, None)
        if old_value == new_value:
            continue
        setattr(profile, field, new_value)
        changed_fields.append(field)
        await timeline.record_event(
            session,
            client_id=profile.client_id,
            event_type=TimelineEventType.PROFILE_FIELD_CHANGED,
            description=f"Змінено поле профілю «{field}»",
            actor_id=actor.id,
            before_value=None if old_value is None else str(old_value),
            after_value=None if new_value is None else str(new_value),
            commit=False,
        )
    if changed_fields:
        await session.commit()
        await session.refresh(profile)
    return changed_fields


# ---- Work experience (Block D) ----

async def add_work_experience(session: AsyncSession, client_id: int, data: dict, actor: AdminUser) -> WorkExperience:
    row = WorkExperience(client_id=client_id, **data)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    await timeline.record_event(
        session, client_id=client_id, event_type=TimelineEventType.PROFILE_FIELD_CHANGED,
        description=f"Додано місце роботи: {data.get('position') or data.get('company') or '(без назви)'}",
        actor_id=actor.id,
    )
    return row


async def update_work_experience(session: AsyncSession, row: WorkExperience, data: dict, actor: AdminUser) -> WorkExperience:
    for field, value in data.items():
        setattr(row, field, value)
    await session.commit()
    await session.refresh(row)
    await timeline.record_event(
        session, client_id=row.client_id, event_type=TimelineEventType.PROFILE_FIELD_CHANGED,
        description=f"Оновлено місце роботи: {row.position or row.company or '(без назви)'}", actor_id=actor.id,
    )
    return row


async def delete_work_experience(session: AsyncSession, row: WorkExperience, actor: AdminUser) -> None:
    client_id = row.client_id
    label = row.position or row.company or "(без назви)"
    await session.delete(row)
    await session.commit()
    await timeline.record_event(
        session, client_id=client_id, event_type=TimelineEventType.PROFILE_FIELD_CHANGED,
        description=f"Видалено місце роботи: {label}", actor_id=actor.id,
    )


# ---- Skills (Block E) ----

async def add_skill(session: AsyncSession, client_id: int, data: dict, actor: AdminUser) -> ClientSkill:
    if data.get("level"):
        data["level"] = SkillLevel(data["level"])
    row = ClientSkill(client_id=client_id, **data)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    await timeline.record_event(
        session, client_id=client_id, event_type=TimelineEventType.PROFILE_FIELD_CHANGED,
        description=f"Додано навичку: {row.skill_name}", actor_id=actor.id,
    )
    return row


async def delete_skill(session: AsyncSession, row: ClientSkill, actor: AdminUser) -> None:
    client_id, name = row.client_id, row.skill_name
    await session.delete(row)
    await session.commit()
    await timeline.record_event(
        session, client_id=client_id, event_type=TimelineEventType.PROFILE_FIELD_CHANGED,
        description=f"Видалено навичку: {name}", actor_id=actor.id,
    )


# ---- Languages (Block G) ----

async def add_language(session: AsyncSession, client_id: int, data: dict, actor: AdminUser) -> ClientLanguage:
    row = ClientLanguage(client_id=client_id, **data)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    await timeline.record_event(
        session, client_id=client_id, event_type=TimelineEventType.PROFILE_FIELD_CHANGED,
        description=f"Додано мову: {row.language}", actor_id=actor.id,
    )
    return row


async def delete_language(session: AsyncSession, row: ClientLanguage, actor: AdminUser) -> None:
    client_id, name = row.client_id, row.language
    await session.delete(row)
    await session.commit()
    await timeline.record_event(
        session, client_id=client_id, event_type=TimelineEventType.PROFILE_FIELD_CHANGED,
        description=f"Видалено мову: {name}", actor_id=actor.id,
    )
