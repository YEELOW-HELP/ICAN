"""Career Knowledge Base version lifecycle (brief §14): DRAFT -> PUBLISHED
-> SUPERSEDED. Exactly one PUBLISHED version may be `is_current` at a
time (DB-enforced via a partial unique index, same idiom as Stage 1/2's
`uq_one_unfinished_session_per_user` / `uq_one_current_profile_per_user`).
Publishing a new version never edits or deletes the previous one -- it
only flips its status to SUPERSEDED and clears `is_current`.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_knowledge import KnowledgeBaseVersion, KnowledgeBaseVersionStatus
from app.services.exceptions import (
    KnowledgeBaseVersionNotDraftError,
    KnowledgeBaseVersionNotFoundError,
    NoCurrentKnowledgeBaseVersionError,
)


async def create_draft_version(session: AsyncSession, *, notes: str | None = None) -> KnowledgeBaseVersion:
    next_version = (
        await session.execute(select(func.coalesce(func.max(KnowledgeBaseVersion.version), 0)))
    ).scalar_one() + 1

    draft = KnowledgeBaseVersion(
        version=next_version, status=KnowledgeBaseVersionStatus.DRAFT, is_current=False, notes=notes
    )
    session.add(draft)
    await session.commit()
    await session.refresh(draft)
    return draft


async def get_draft_version(session: AsyncSession, version_id: uuid.UUID) -> KnowledgeBaseVersion:
    version = await session.get(KnowledgeBaseVersion, version_id)
    if version is None:
        raise KnowledgeBaseVersionNotFoundError(f"KnowledgeBaseVersion {version_id} does not exist")
    if version.status != KnowledgeBaseVersionStatus.DRAFT:
        raise KnowledgeBaseVersionNotDraftError(
            f"KnowledgeBaseVersion {version_id} is {version.status.value}, not draft -- it is immutable"
        )
    return version


async def publish_version(session: AsyncSession, version_id: uuid.UUID) -> KnowledgeBaseVersion:
    """Publishing is the only way a version becomes `is_current`. The
    previously current (PUBLISHED) version, if any, is superseded in the
    same transaction -- never left ambiguous about which is authoritative."""
    version = await session.get(KnowledgeBaseVersion, version_id)
    if version is None:
        raise KnowledgeBaseVersionNotFoundError(f"KnowledgeBaseVersion {version_id} does not exist")
    if version.status != KnowledgeBaseVersionStatus.DRAFT:
        raise KnowledgeBaseVersionNotDraftError(f"KnowledgeBaseVersion {version_id} is not draft; cannot publish")

    previous_current = (
        await session.execute(select(KnowledgeBaseVersion).where(KnowledgeBaseVersion.is_current.is_(True)))
    ).scalar_one_or_none()
    if previous_current is not None:
        previous_current.status = KnowledgeBaseVersionStatus.SUPERSEDED
        previous_current.is_current = False
        await session.flush()

    version.status = KnowledgeBaseVersionStatus.PUBLISHED
    version.is_current = True
    version.published_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(version)
    return version


async def get_current_knowledge_version(session: AsyncSession) -> KnowledgeBaseVersion:
    result = await session.execute(select(KnowledgeBaseVersion).where(KnowledgeBaseVersion.is_current.is_(True)))
    version = result.scalar_one_or_none()
    if version is None:
        raise NoCurrentKnowledgeBaseVersionError("no KnowledgeBaseVersion has been published yet")
    return version


async def get_knowledge_version(session: AsyncSession, version_id: uuid.UUID) -> KnowledgeBaseVersion:
    version = await session.get(KnowledgeBaseVersion, version_id)
    if version is None:
        raise KnowledgeBaseVersionNotFoundError(f"KnowledgeBaseVersion {version_id} does not exist")
    return version


async def list_knowledge_versions(session: AsyncSession) -> list[KnowledgeBaseVersion]:
    result = await session.execute(select(KnowledgeBaseVersion).order_by(KnowledgeBaseVersion.version))
    return list(result.scalars().all())
