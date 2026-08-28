"""Read helpers for deterministic BASIC profiles (Matching V1 M2)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_basic_assessment import ScaleFamily
from app.db.models_basic_profile import DeterministicProfile, ProfileScaleResult
from app.services.exceptions import NoCurrentBasicProfileError


async def get_basic_profile(session: AsyncSession, user_id: uuid.UUID) -> DeterministicProfile:
    """The one `is_current=True` profile for this user -- the DB partial
    unique index guarantees there is never more than one."""

    result = await session.execute(
        select(DeterministicProfile).where(
            DeterministicProfile.user_id == user_id, DeterministicProfile.is_current.is_(True)
        )
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        raise NoCurrentBasicProfileError(f"no current DeterministicProfile for user {user_id}")
    return profile


async def get_profile_scale_results(
    session: AsyncSession, profile: DeterministicProfile, scale_family: ScaleFamily | None = None
) -> list[ProfileScaleResult]:
    query = select(ProfileScaleResult).where(ProfileScaleResult.profile_id == profile.id)
    if scale_family is not None:
        query = query.where(ProfileScaleResult.scale_family == scale_family)
    result = await session.execute(query.order_by(ProfileScaleResult.scale_family, ProfileScaleResult.scale_key))
    return list(result.scalars().all())
