from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import AdminRole, AdminUser
from app.db.models_crm import Client, ClientPriority, ClientProfile, ClientStatus, SourceChannel, TimelineEventType
from app.services.crm import timeline
from app.services.crm.completeness import ReadinessCheck, check_ready_for_matching, check_screening_complete

CLIENT_EDITABLE_FIELDS = [
    "first_name", "last_name", "phone", "telegram_username", "email", "birth_date",
    "country", "city", "priority",
]

_STATUS_LABELS = {
    ClientStatus.NEW: "Новий клієнт",
    ClientStatus.SCREENING: "Первинний скринінг",
    ClientStatus.WAITING_CONSULTANT: "Очікує консультанта",
    ClientStatus.CAREER_CONSULTATION: "Кар'єрна консультація",
    ClientStatus.READY_FOR_MATCHING: "Готовий до підбору",
    ClientStatus.IN_WORK: "У роботі",
    ClientStatus.PAUSED: "Призупинено",
    ClientStatus.CLOSED: "Закрито",
}


def _client_query():
    return select(Client).options(
        selectinload(Client.profile),
        selectinload(Client.work_experiences),
        selectinload(Client.skills),
        selectinload(Client.languages),
        selectinload(Client.consultation),
    )


async def create_client(
    session: AsyncSession,
    *,
    source_channel: SourceChannel,
    actor: AdminUser | None,
    telegram_user_id: int | None = None,
    **fields,
) -> Client:
    client = Client(source_channel=source_channel, telegram_user_id=telegram_user_id, **fields)
    session.add(client)
    await session.flush()
    session.add(ClientProfile(client_id=client.id))
    await session.commit()
    await session.refresh(client)

    await timeline.record_event(
        session,
        client_id=client.id,
        event_type=TimelineEventType.CREATED,
        description=f"Клієнта створено (канал: {source_channel.value})",
        actor_id=actor.id if actor else None,
    )
    return client


async def get_client(session: AsyncSession, client_id: int) -> Client | None:
    result = await session.execute(_client_query().where(Client.id == client_id, Client.is_deleted.is_(False)))
    return result.scalar_one_or_none()


async def get_client_by_telegram_user(session: AsyncSession, telegram_user_id: int) -> Client | None:
    result = await session.execute(_client_query().where(Client.telegram_user_id == telegram_user_id))
    return result.scalar_one_or_none()


def _scope_to_viewer(query, viewer: AdminUser):
    """RBAC enforced server-side, not just hidden in the UI (ТЗ §20): a
    CAREER_CONSULTANT can only ever see clients assigned to them."""
    if viewer.role == AdminRole.CAREER_CONSULTANT:
        return query.where(Client.consultant_id == viewer.id)
    return query


async def list_clients(
    session: AsyncSession,
    *,
    viewer: AdminUser,
    page: int = 1,
    page_size: int = 25,
    search: str | None = None,
    status_filter: str | None = None,
    city: str | None = None,
    manager_id: int | None = None,
    consultant_id: int | None = None,
    overdue_only: bool = False,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
) -> tuple[list[Client], int]:
    page_size = min(max(page_size, 1), 100)
    page = max(page, 1)

    query = _client_query().where(Client.is_deleted.is_(False))
    query = _scope_to_viewer(query, viewer)

    if search:
        like = f"%{search}%"
        conditions = [
            Client.first_name.ilike(like),
            Client.last_name.ilike(like),
            Client.phone.ilike(like),
            Client.telegram_username.ilike(like),
            Client.email.ilike(like),
        ]
        if search.isdigit():
            conditions.append(Client.id == int(search))
        query = query.where(or_(*conditions))

    if status_filter:
        query = query.where(Client.status == status_filter)
    if city:
        query = query.where(Client.city.ilike(f"%{city}%"))
    if manager_id:
        query = query.where(Client.manager_id == manager_id)
    if consultant_id:
        query = query.where(Client.consultant_id == consultant_id)

    count_query = select(func.count()).select_from(query.with_only_columns(Client.id).subquery())
    total = await session.scalar(count_query)

    sort_column = Client.last_activity_at if sort_by == "last_activity_at" else Client.created_at
    order = sort_column.desc() if sort_dir == "desc" else sort_column.asc()
    query = query.order_by(order).offset((page - 1) * page_size).limit(page_size)

    result = await session.execute(query)
    clients = list(result.scalars().unique().all())
    return clients, total or 0


async def update_client_fields(
    session: AsyncSession, client: Client, changes: dict, actor: AdminUser
) -> list[str]:
    changed_fields: list[str] = []
    for field, new_value in changes.items():
        if field not in CLIENT_EDITABLE_FIELDS:
            continue
        if field == "priority" and new_value is not None:
            new_value = ClientPriority(new_value)
        old_value = getattr(client, field, None)
        old_str = old_value.value if hasattr(old_value, "value") else old_value
        new_str = new_value.value if hasattr(new_value, "value") else new_value
        if old_str == new_str:
            continue
        setattr(client, field, new_value)
        changed_fields.append(field)
        await timeline.record_event(
            session,
            client_id=client.id,
            event_type=TimelineEventType.PROFILE_FIELD_CHANGED,
            description=f"Змінено поле «{field}»",
            actor_id=actor.id,
            before_value=None if old_str is None else str(old_str),
            after_value=None if new_str is None else str(new_str),
            commit=False,
        )
    if changed_fields:
        await session.commit()
    return changed_fields


async def set_status(
    session: AsyncSession, client: Client, new_status: ClientStatus, actor: AdminUser | None
) -> Client:
    if client.status == new_status:
        return client
    old_status = client.status
    client.status = new_status
    await session.commit()
    await session.refresh(client)

    await timeline.record_event(
        session,
        client_id=client.id,
        event_type=TimelineEventType.STATUS_CHANGED,
        description=f"Статус змінено: {_STATUS_LABELS[old_status]} → {_STATUS_LABELS[new_status]}",
        actor_id=actor.id if actor else None,
        before_value=old_status.value,
        after_value=new_status.value,
    )
    return client


async def assign_consultant(
    session: AsyncSession, client: Client, consultant: AdminUser, actor: AdminUser
) -> Client:
    old_consultant_id = client.consultant_id
    client.consultant_id = consultant.id
    if client.status == ClientStatus.WAITING_CONSULTANT:
        client.status = ClientStatus.CAREER_CONSULTATION
    await session.commit()
    await session.refresh(client)

    await timeline.record_event(
        session,
        client_id=client.id,
        event_type=TimelineEventType.ASSIGNED,
        description=f"Призначено Career Consultant: {consultant.email}",
        actor_id=actor.id,
        before_value=str(old_consultant_id) if old_consultant_id else None,
        after_value=str(consultant.id),
    )
    return client


async def assign_manager(session: AsyncSession, client: Client, manager: AdminUser, actor: AdminUser) -> Client:
    client.manager_id = manager.id
    await session.commit()
    await session.refresh(client)

    await timeline.record_event(
        session,
        client_id=client.id,
        event_type=TimelineEventType.ASSIGNED,
        description=f"Призначено Manager: {manager.email}",
        actor_id=actor.id,
    )
    return client


async def soft_delete(session: AsyncSession, client: Client, actor: AdminUser) -> None:
    client.is_deleted = True
    await session.commit()
    await timeline.record_event(
        session,
        client_id=client.id,
        event_type=TimelineEventType.NOTE,
        description="Клієнта видалено (soft delete)",
        actor_id=actor.id,
    )


async def touch_activity(session: AsyncSession, client: Client) -> None:
    client.last_activity_at = datetime.now(timezone.utc)
    await session.commit()


async def dashboard_summary(session: AsyncSession, viewer: AdminUser) -> dict:
    base = _scope_to_viewer(select(Client).where(Client.is_deleted.is_(False)), viewer)
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    async def count(extra_where=None):
        q = select(func.count()).select_from(base.with_only_columns(Client.id).subquery())
        if extra_where is not None:
            q = select(func.count()).select_from(
                _scope_to_viewer(
                    select(Client.id).where(Client.is_deleted.is_(False)).where(extra_where), viewer
                ).subquery()
            )
        return (await session.scalar(q)) or 0

    total = await count()
    new_today = await count(Client.created_at >= today_start)
    screening = await count(Client.status == ClientStatus.SCREENING)
    waiting_consultant = await count(Client.status == ClientStatus.WAITING_CONSULTANT)
    in_consultation = await count(Client.status == ClientStatus.CAREER_CONSULTATION)
    ready = await count(Client.status == ClientStatus.READY_FOR_MATCHING)

    return {
        "total_clients": total,
        "new_today": new_today,
        "in_screening": screening,
        "waiting_consultant": waiting_consultant,
        "in_career_consultation": in_consultation,
        "ready_for_matching": ready,
    }


async def try_complete_screening(session: AsyncSession, client: Client, actor: AdminUser) -> ReadinessCheck:
    # Re-fetch with relationships eager-loaded — the caller's `client` may
    # have been fetched without them (async SQLAlchemy won't lazy-load
    # outside an explicit await context).
    client = await get_client(session, client.id)
    check = check_screening_complete(client, client.profile, client.skills)
    if not check.ready:
        return check

    await set_status(session, client, ClientStatus.WAITING_CONSULTANT, actor)
    await timeline.record_event(
        session,
        client_id=client.id,
        event_type=TimelineEventType.SCREENING_COMPLETED,
        description="Первинний скринінг завершено",
        actor_id=actor.id,
    )
    return check


async def try_mark_ready_for_matching(session: AsyncSession, client: Client, actor: AdminUser) -> ReadinessCheck:
    client = await get_client(session, client.id)
    check = check_ready_for_matching(
        client, client.profile, client.work_experiences, client.skills, client.languages, client.consultation
    )
    if not check.ready:
        return check

    await set_status(session, client, ClientStatus.READY_FOR_MATCHING, actor)
    await timeline.record_event(
        session,
        client_id=client.id,
        event_type=TimelineEventType.READY_FOR_MATCHING,
        description="Клієнт готовий до підбору (READY_FOR_MATCHING)",
        actor_id=actor.id,
    )
    return check
