from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Message, MessageRole, Profile, ScreeningState, User
from app.schemas.profile import ProfileDraft


async def get_or_create_user(
    session: AsyncSession, telegram_id: int, telegram_username: str | None = None
) -> User:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user is not None:
        if telegram_username and user.telegram_username != telegram_username:
            user.telegram_username = telegram_username
            await session.commit()
            await session.refresh(user)
        return user

    user = User(
        telegram_id=telegram_id, telegram_username=telegram_username, screening_state=ScreeningState.NOT_STARTED
    )
    session.add(user)
    await session.flush()
    profile = Profile(user_id=user.id)
    session.add(profile)
    await session.commit()
    await session.refresh(user)
    return user


async def get_profile(session: AsyncSession, user: User) -> Profile:
    result = await session.execute(select(Profile).where(Profile.user_id == user.id))
    return result.scalar_one()


async def get_messages(session: AsyncSession, user: User) -> list[Message]:
    result = await session.execute(
        select(Message).where(Message.user_id == user.id).order_by(Message.created_at)
    )
    return list(result.scalars().all())


async def record_message(session: AsyncSession, user: User, role: MessageRole, content: str) -> None:
    session.add(Message(user_id=user.id, role=role, content=content))
    if role == MessageRole.USER:
        user.last_active_at = datetime.now(timezone.utc)
    await session.commit()


async def apply_profile_draft(session: AsyncSession, user: User, draft: ProfileDraft) -> Profile:
    profile = await get_profile(session, user)
    for field, value in draft.model_dump().items():
        setattr(profile, field, value)
    await session.commit()
    await session.refresh(profile)
    return profile


async def confirm_profile(session: AsyncSession, user: User) -> Profile:
    profile = await get_profile(session, user)
    profile.confirmed = True
    user.screening_state = ScreeningState.CONFIRMED
    await session.commit()
    await session.refresh(profile)

    from app.services.crm.bridge import sync_from_bot_confirmation

    await sync_from_bot_confirmation(session, user, profile)

    return profile


async def set_state(session: AsyncSession, user: User, state: ScreeningState) -> None:
    user.screening_state = state
    await session.commit()
