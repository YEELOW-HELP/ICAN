"""MNP web session tokens -- the smallest secure session mechanism for
Person KB Base V1.

`POST /v1/mnp/session` mints a 256-bit URL-safe random token
(`secrets.token_urlsafe(32)`). Only `sha256(token)` is persisted
(`MnpWebSession.token_hash`). Private user routes authenticate with
`Authorization: Bearer <token>`; the server resolves the `IdentityUser`
from the session -- the client can never choose an identity by supplying
a UUID.

The raw token is returned ONCE from `POST /session` and never logged.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_identity import IdentityUser
from app.db.models_person_kb import MnpWebSession

_TOKEN_BYTES = 32  # 256 bits of entropy


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def create_web_session(session: AsyncSession, user: IdentityUser) -> str:
    """Mint a new session token for `user`. Returns the RAW token (shown
    to the client once); only its hash is stored."""
    token = secrets.token_urlsafe(_TOKEN_BYTES)
    session.add(MnpWebSession(user_id=user.id, token_hash=_hash(token)))
    await session.flush()
    return token


async def resolve_web_session(session: AsyncSession, token: str | None) -> IdentityUser | None:
    """Resolve a bearer token to its `IdentityUser`, or None. Constant
    work regardless of validity is not attempted (the lookup is a single
    indexed hash equality) -- the token itself carries the entropy."""
    if not token or not token.strip():
        return None
    row = (await session.execute(
        select(MnpWebSession).where(
            MnpWebSession.token_hash == _hash(token.strip()),
            MnpWebSession.revoked_at.is_(None)))).scalar_one_or_none()
    if row is None:
        return None
    row.last_seen_at = datetime.now(timezone.utc)
    return await session.get(IdentityUser, row.user_id)


def bearer_from_header(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip() or None
    return None
