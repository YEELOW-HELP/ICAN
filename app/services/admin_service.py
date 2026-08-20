from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password
from app.db.models import AdminUser, Message, Profile, ProfileEditLog, ScreeningState, User
from app.schemas.profile import PROFILE_FIELDS


async def authenticate_admin(session: AsyncSession, email: str, password: str) -> AdminUser | None:
    result = await session.execute(select(AdminUser).where(AdminUser.email == email))
    admin = result.scalar_one_or_none()
    if admin is None or not verify_password(password, admin.password_hash):
        return None
    return admin


def profile_completion(profile: Profile | None) -> int:
    if profile is None:
        return 0
    filled = sum(1 for f in PROFILE_FIELDS if getattr(profile, f, None))
    return round(filled / len(PROFILE_FIELDS) * 100)


async def get_dashboard_summary(session: AsyncSession) -> dict:
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)

    total_users = await session.scalar(select(func.count(User.id)))
    new_today = await session.scalar(select(func.count(User.id)).where(User.created_at >= today_start))
    completed = await session.scalar(
        select(func.count(User.id)).where(
            User.screening_state.in_([ScreeningState.AWAITING_CONFIRMATION, ScreeningState.CONFIRMED])
        )
    )
    in_progress = await session.scalar(
        select(func.count(User.id)).where(User.screening_state == ScreeningState.IN_PROGRESS)
    )
    not_completed = await session.scalar(
        select(func.count(User.id)).where(
            User.screening_state.in_([ScreeningState.NOT_STARTED, ScreeningState.PAUSED])
        )
    )
    active_last_7_days = await session.scalar(
        select(func.count(User.id)).where(User.last_active_at >= week_ago)
    )

    return {
        "total_users": total_users or 0,
        "new_today": new_today or 0,
        "completed": completed or 0,
        "in_progress": in_progress or 0,
        "not_completed": not_completed or 0,
        "active_last_7_days": active_last_7_days or 0,
    }


async def list_users(
    session: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 25,
    search: str | None = None,
    status_filter: str | None = None,
    city: str | None = None,
    desired_role: str | None = None,
    registered_after: datetime | None = None,
    registered_before: datetime | None = None,
    active_after: datetime | None = None,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
) -> tuple[list[tuple[User, Profile | None]], int]:
    page_size = 50 if page_size > 25 else 25
    page = max(page, 1)

    query = select(User, Profile).outerjoin(Profile, Profile.user_id == User.id)

    if search:
        like = f"%{search}%"
        conditions = [User.telegram_username.ilike(like), User.phone.ilike(like), Profile.name.ilike(like)]
        if search.isdigit():
            conditions.append(User.telegram_id == int(search))
            conditions.append(User.id == int(search))
        query = query.where(or_(*conditions))

    if status_filter:
        query = query.where(User.screening_state == status_filter)
    if city:
        query = query.where(Profile.city.ilike(f"%{city}%"))
    if desired_role:
        query = query.where(Profile.desired_role.ilike(f"%{desired_role}%"))
    if registered_after:
        query = query.where(User.created_at >= registered_after)
    if registered_before:
        query = query.where(User.created_at <= registered_before)
    if active_after:
        query = query.where(User.last_active_at >= active_after)

    count_query = select(func.count()).select_from(query.subquery())
    total = await session.scalar(count_query)

    sort_column = User.last_active_at if sort_by == "last_active_at" else User.created_at
    order = sort_column.desc() if sort_dir == "desc" else sort_column.asc()
    query = query.order_by(order).offset((page - 1) * page_size).limit(page_size)

    result = await session.execute(query)
    rows = [(row.User, row.Profile) for row in result.all()]
    return rows, total or 0


async def get_user_with_profile(session: AsyncSession, user_id: int) -> tuple[User, Profile] | None:
    result = await session.execute(
        select(User, Profile).join(Profile, Profile.user_id == User.id).where(User.id == user_id)
    )
    row = result.first()
    if row is None:
        return None
    return row.User, row.Profile


async def get_messages(session: AsyncSession, user_id: int) -> list[Message]:
    result = await session.execute(select(Message).where(Message.user_id == user_id).order_by(Message.created_at))
    return list(result.scalars().all())


async def update_profile(
    session: AsyncSession, profile: Profile, changes: dict, edited_by: str
) -> list[ProfileEditLog]:
    logs: list[ProfileEditLog] = []
    for field, new_value in changes.items():
        if field not in PROFILE_FIELDS:
            continue
        old_value = getattr(profile, field, None)
        if old_value == new_value:
            continue
        log = ProfileEditLog(
            user_id=profile.user_id,
            field_name=field,
            old_value=None if old_value is None else str(old_value),
            new_value=None if new_value is None else str(new_value),
            edited_by=edited_by,
        )
        session.add(log)
        logs.append(log)
        setattr(profile, field, new_value)

    if logs:
        await session.commit()
    return logs


async def update_status(
    session: AsyncSession, user: User, screening_state: str | None, is_blocked: bool | None
) -> User:
    if screening_state is not None:
        user.screening_state = ScreeningState(screening_state)
    if is_blocked is not None:
        user.is_blocked = is_blocked
    await session.commit()
    await session.refresh(user)
    return user


async def get_edit_logs(session: AsyncSession, user_id: int) -> list[ProfileEditLog]:
    result = await session.execute(
        select(ProfileEditLog).where(ProfileEditLog.user_id == user_id).order_by(ProfileEditLog.edited_at.desc())
    )
    return list(result.scalars().all())
