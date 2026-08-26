"""Append-only audit trail (Stage 1 -- privileged operations only, see
docs/engineering/13_FOUNDER_ARCHITECTURE_REVIEW.md Decision 9). Nothing
in this codebase should ever UPDATE or DELETE an `AuditLog` row."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_platform import AuditLog


async def record_audit(
    session: AsyncSession,
    *,
    entity_type: str,
    entity_id: str,
    action: str,
    actor_admin_id: int | None = None,
    actor_user_id: uuid.UUID | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor_admin_id=actor_admin_id,
        actor_user_id=actor_user_id,
        entity_type=entity_type,
        entity_id=str(entity_id),
        action=action,
        before_snapshot=before,
        after_snapshot=after,
    )
    session.add(entry)
    await session.commit()
    return entry
