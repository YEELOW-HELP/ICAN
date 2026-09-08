"""Channel-agnostic identity resolution (Stage 1). This is the only place
allowed to create an `IdentityUser`/`AuthIdentity` pair -- callers (the
Telegram adapter today, a future web/API adapter) never construct these
rows themselves.

`resolve_identity` is safe under concurrent calls for the same
(provider, provider_subject): it optimistically inserts, and falls back to
re-reading on a unique-constraint conflict, rather than doing a
non-atomic "check then insert" that would race under concurrent first
contact from the same channel identity.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User as LegacyUser
from app.db.models_identity import AuthIdentity, IdentityUser
from app.services.events import emit_event


async def resolve_identity(
    session: AsyncSession,
    *,
    provider: str,
    provider_subject: str,
    provider_username: str | None = None,
) -> IdentityUser:
    """Resolve-or-create the canonical `IdentityUser` behind one
    (provider, provider_subject) pair. Updates `last_seen_at`/
    `provider_username` on every call, since this is the natural place to
    track "last active" per channel without a separate table."""
    existing = await _get_auth_identity(session, provider, provider_subject)
    if existing is not None:
        existing.last_seen_at = datetime.now(timezone.utc)
        if provider_username and existing.provider_username != provider_username:
            existing.provider_username = provider_username
        await session.commit()
        return await session.get(IdentityUser, existing.user_id)

    user = IdentityUser()
    session.add(user)
    await session.flush()

    identity = AuthIdentity(
        user_id=user.id,
        provider=provider,
        provider_subject=provider_subject,
        provider_username=provider_username,
        last_seen_at=datetime.now(timezone.utc),
    )
    session.add(identity)
    try:
        await session.commit()
    except IntegrityError:
        # Lost a race with a concurrent first-contact request for the same
        # (provider, provider_subject) -- the other request's row won, use it.
        await session.rollback()
        existing = await _get_auth_identity(session, provider, provider_subject)
        assert existing is not None, "unique-constraint conflict implies a concurrent row now exists"
        return await session.get(IdentityUser, existing.user_id)

    if provider == "telegram":
        await _link_legacy_telegram_user(session, provider_subject, user.id)

    emit_event("identity_created", user_id=str(user.id), source=provider)
    return user


async def _get_auth_identity(session: AsyncSession, provider: str, provider_subject: str) -> AuthIdentity | None:
    result = await session.execute(
        select(AuthIdentity).where(AuthIdentity.provider == provider, AuthIdentity.provider_subject == provider_subject)
    )
    return result.scalar_one_or_none()


async def _link_legacy_telegram_user(session: AsyncSession, provider_subject: str, canonical_user_id) -> None:
    """Opportunistic bridge (Migration Map #1): if this Telegram id already
    has a legacy ICAN 1.1 `users` row, link it to the new canonical
    identity. Never runs a bulk backfill -- only links rows encountered
    through real traffic, and only sets the bridge column, never touches
    any other legacy field or behavior."""
    try:
        telegram_id = int(provider_subject)
    except ValueError:
        return

    result = await session.execute(select(LegacyUser).where(LegacyUser.telegram_id == telegram_id))
    legacy_user = result.scalar_one_or_none()
    if legacy_user is not None and legacy_user.canonical_user_id is None:
        legacy_user.canonical_user_id = canonical_user_id
        await session.commit()
