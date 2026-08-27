"""Platform-level cross-cutting concerns (Stage 1 -- just what's needed for
privileged-operation audit trail; see
docs/engineering/13_FOUNDER_ARCHITECTURE_REVIEW.md Decision 9). Not a
general-purpose audit framework -- one table, append-only, used only where
Stage 1 actually has a privileged operation to record."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditLog(Base):
    """Append-only. A correction is a new row, never an edit to an
    existing one -- nothing in this codebase should ever UPDATE or DELETE
    a row here. `actor_admin_id` covers staff-privileged actions (manual
    access grants, promo/package mutations); `actor_user_id` is reserved
    for a future end-user-privileged action, unused in Stage 1."""

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_admin_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id"))
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("identity_users.id"))
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64))
    before_snapshot: Mapped[dict | None] = mapped_column(JSON)
    after_snapshot: Mapped[dict | None] = mapped_column(JSON)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
