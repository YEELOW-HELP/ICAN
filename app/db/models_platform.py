"""Platform-level cross-cutting concerns (Stage 1 -- just what's needed for
privileged-operation audit trail; see
docs/engineering/13_FOUNDER_ARCHITECTURE_REVIEW.md Decision 9). Not a
general-purpose audit framework -- one table, append-only, used only where
Stage 1 actually has a privileged operation to record."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Uuid, func
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


class AITrace(Base):
    """Persistent record of one AI Gateway call (docs/architecture/02_ERD.md's
    `AI_TRACE`; Founder decision M2). Until now the AI Gateway
    structured-logged this data only; this table gives it a durable home so
    "which model/prompt produced this artifact, and when" is answerable
    from the database, not just retained logs.

    NO secrets and NO PII: only call metadata (task, provider, model,
    prompt version, token counts, latency, cost, status). Never
    prompt/message/tool content. `trace_id` is the runtime identifier the
    gateway already generates per call and that generated artifacts
    reference (e.g. `Evidence.trace_id`, `DirectionRun.trace_ids`); `id`
    is the row's own key.

    Slice 1: table + `app/services/ai_trace.py::record_ai_trace` helper
    are created. Wiring `AIGateway` itself to call the helper (it needs a
    DB session plumbed in) is deferred to the slice that introduces
    Direction Intelligence's own LLM tasks -- this keeps a deterministic-
    only slice free of behaviour changes to the Stage 1/2 AI path.
    """

    __tablename__ = "ai_traces"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trace_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    task: Mapped[str] = mapped_column(String(64))
    provider: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(64))
    prompt_version: Mapped[str] = mapped_column(String(64))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    estimated_cost_usd: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(32))  # "ok" | "error"
    error_type: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )
