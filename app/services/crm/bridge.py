"""Bridges the Telegram bot's AI screening result into the CRM (ТЗ CRM 1.0
§2: Telegram is one intake channel among several; the bot's "first
screening" fast-forwards a client straight past NEW/SCREENING to
WAITING_CONSULTANT, since a manager doesn't need to re-collect what the AI
already captured and the candidate already confirmed).

Cleanly-structured bot fields (contact info, target role, salary, format,
skills) map directly onto CRM fields. Anything the bot captured as loose
text (education, past positions, total experience, constraints) is carried
forward as a readable note in `nonstandard_info` rather than force-fit into
CRM's more granular structure — a human still curates the final CRM profile
during screening/consultation, matching the product's "AI never invents,
humans confirm" principle applied one layer up.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Profile, User
from app.db.models_crm import ClientLanguage, ClientSkill, ClientStatus, SourceChannel
from app.services.crm import clients as client_service


def _guess_employment(status: str | None) -> bool | None:
    if not status:
        return None
    lowered = status.lower()
    if "не" in lowered or "not" in lowered:
        return False
    if "працю" in lowered or "work" in lowered or "навча" in lowered:
        return True
    return None


def _split_name(full_name: str | None) -> tuple[str | None, str | None]:
    if not full_name:
        return None, None
    parts = full_name.strip().split(maxsplit=1)
    return parts[0], parts[1] if len(parts) > 1 else None


def _build_nonstandard_note(profile: Profile) -> str | None:
    lines = []
    if profile.total_experience:
        lines.append(f"Загальний досвід (з боту): {profile.total_experience}")
    if profile.education:
        lines.append(f"Освіта (з боту): {profile.education}")
    if profile.previous_positions:
        lines.append("Попередні посади (з боту): " + "; ".join(profile.previous_positions))
    if profile.constraints:
        lines.append(f"Обмеження (з боту): {profile.constraints}")
    if profile.other_notes:
        lines.append(f"Інше (з боту): {profile.other_notes}")
    return "\n".join(lines) if lines else None


async def sync_from_bot_confirmation(session: AsyncSession, user: User, profile: Profile):
    existing = await client_service.get_client_by_telegram_user(session, user.id)
    first_name, last_name = _split_name(profile.name)

    client_fields = {
        "first_name": first_name,
        "last_name": last_name,
        "phone": user.phone,
        "telegram_username": user.telegram_username,
        "email": user.email,
        "country": profile.country,
        "city": profile.city,
    }

    if existing is None:
        client = await client_service.create_client(
            session,
            source_channel=SourceChannel.TELEGRAM,
            actor=None,
            telegram_user_id=user.id,
            **client_fields,
        )
        # The bot already performed the "first screening" — skip straight to
        # WAITING_CONSULTANT instead of making a manager redo it.
        await client_service.set_status(session, client, ClientStatus.WAITING_CONSULTANT, actor=None)
    else:
        client = existing
        for field, value in client_fields.items():
            if value:
                setattr(client, field, value)
        await session.commit()

    # Re-fetch with relationships eager-loaded regardless of which branch
    # ran above — async SQLAlchemy won't lazy-load `.profile`/`.skills`/
    # `.languages` outside an explicit await context.
    client = await client_service.get_client(session, client.id)

    profile_changes = {
        "currently_employed": _guess_employment(profile.status),
        "primary_target": profile.desired_role,
        "min_salary": profile.desired_min_income,
        "salary_currency": profile.desired_currency,
        "employment_types": [profile.employment_format] if profile.employment_format else None,
        "work_formats": [profile.work_format] if profile.work_format else None,
        "schedules": [profile.schedule] if profile.schedule else None,
        "constraints_comment": profile.constraints,
        "nonstandard_info": _build_nonstandard_note(profile),
    }
    profile_changes = {k: v for k, v in profile_changes.items() if v is not None}

    if profile_changes and client.profile is not None:
        # System-sourced sync, not a human edit — bypass the per-field admin
        # audit log (there's no admin "actor" here) and write directly.
        for field, value in profile_changes.items():
            setattr(client.profile, field, value)
        await session.commit()

    if profile.skills:
        existing_skill_names = {s.skill_name for s in client.skills}
        for skill_name in profile.skills:
            if skill_name not in existing_skill_names:
                session.add(ClientSkill(client_id=client.id, skill_name=skill_name))

    if profile.languages:
        existing_langs = {l.language for l in client.languages}
        for lang in profile.languages:
            if lang not in existing_langs:
                session.add(ClientLanguage(client_id=client.id, language=lang))

    await session.commit()
    return client
