"""Channel-agnostic Assessment Engine foundation (Stage 1 -- Issue #1,
docs/engineering/13_FOUNDER_ARCHITECTURE_REVIEW.md's `INTERVIEW_SESSION`/
`ANSWER`/`INTERVIEW_MESSAGE`, and the Sprint 1 Issue #1 readiness review's
state machine design).

Three concepts are kept deliberately separate, per explicit instruction:
`InterviewSession` (the state machine), `Answer` (structured semantic
response consumed by assessment logic), `InterviewMessage` (raw
conversational transcript, audit/reprocessing only -- never read by the
next-question service). `QuestionSelection` is the first-class record of
*why* a question was chosen, so "traceable reason" is a queryable fact,
not a log line to grep.

None of this is read by the legacy `app/db/models.py` (`User`/`Profile`/
`Message`) tables, and vice versa -- this is purely additive, gated behind
`settings.bot_flow` (see app/bot/main.py) until an explicit, separately
reviewed cutover.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AssessmentStatus(str, enum.Enum):
    """Canonical states (Founder-approved):
    draft -> active -> paused -> complete -> processing -> ready -> failed.
    Allowed transitions are enforced centrally in
    app/services/assessment/state_machine.py -- nothing else may write
    `InterviewSession.status` directly."""

    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETE = "complete"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class SelectionReason(str, enum.Enum):
    """Why the next-question service picked a given question -- recorded
    *before* the question is shown to the candidate, never reconstructed
    after the fact."""

    MISSING = "missing"
    LOW_CONFIDENCE = "low_confidence"
    CONTRADICTION = "contradiction"


class CVExtractionStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    UNSUPPORTED = "unsupported"
    EMPTY = "empty"


class InterviewSession(Base):
    """One assessment attempt. `entitlement_id` ties the session to the
    product-access grant it consumes -- set once, at start, never changed.
    `completeness` is a cached snapshot for fast reads; the source of
    truth for completeness is always recomputed from `Answer` rows (see
    app/services/assessment/next_question.py), never trusted blindly from
    this column alone."""

    __tablename__ = "interview_sessions"
    __table_args__ = (
        # Founder decision (Issue #1 readiness review, item 3): a user may
        # have at most one unfinished (draft/active/paused) session at a
        # time. Enforced at the DB level, not just in start_assessment --
        # a partial unique index so completed/failed history is unbounded.
        Index(
            "uq_one_unfinished_session_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("status IN ('draft', 'active', 'paused')"),
            sqlite_where=text("status IN ('draft', 'active', 'paused')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("identity_users.id"), index=True)
    entitlement_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("entitlements.id"))
    status: Mapped[AssessmentStatus] = mapped_column(
        Enum(AssessmentStatus, native_enum=False), default=AssessmentStatus.DRAFT, index=True
    )
    assessment_version: Mapped[str] = mapped_column(String(32), default="hybrid-v1")
    mode: Mapped[str] = mapped_column(String(32), default="hybrid")
    completeness: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_reason: Mapped[str | None] = mapped_column(String(255))

    answers: Mapped[list["Answer"]] = relationship(back_populates="session", order_by="Answer.created_at")
    messages: Mapped[list["InterviewMessage"]] = relationship(
        back_populates="session", order_by="InterviewMessage.sequence"
    )
    question_selections: Mapped[list["QuestionSelection"]] = relationship(back_populates="session")
    cv_uploads: Mapped[list["CVUpload"]] = relationship(back_populates="session")


class Answer(Base):
    """A structured semantic response. Immutable once created -- a changed
    answer to the same `question_id` is a *new* row, never an edit; "latest
    by created_at wins" is the read convention everywhere (see
    app/services/assessment/next_question.py). `idempotency_key` +
    `UNIQUE(session_id, idempotency_key)` is what makes duplicate
    submission safe regardless of channel (Telegram retry, future web
    retry) -- the key's origin is the caller's concern, not this table's."""

    __tablename__ = "answers"
    __table_args__ = (UniqueConstraint("session_id", "idempotency_key", name="uq_answer_session_idempotency"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("interview_sessions.id"), index=True)
    question_id: Mapped[str] = mapped_column(String(64), index=True)
    answer_text: Mapped[str] = mapped_column(Text)
    extracted_value: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float)
    contradicts_previous: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(String(32))  # "telegram" | "cv" | ...
    idempotency_key: Mapped[str] = mapped_column(String(128))
    # Python-side default (microsecond precision): "latest answer wins" for
    # a question_id is decided by ordering on this column
    # (app/services/assessment/completeness.py, sessions.py) -- server-side
    # CURRENT_TIMESTAMP is only second-granular, not precise enough to
    # break ties between two answers recorded in the same second.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now(), index=True
    )

    session: Mapped["InterviewSession"] = relationship(back_populates="answers")


class InterviewMessage(Base):
    """Raw conversational transcript -- distinct from `Answer` by design
    (a single message may not map 1:1 to one question; CV text is a
    "message" too, in the broad sense). Never read by the next-question
    service. `UNIQUE(session_id, sequence)` keeps ordering race-detectable."""

    __tablename__ = "interview_messages"
    __table_args__ = (UniqueConstraint("session_id", "sequence", name="uq_interview_message_session_sequence"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("interview_sessions.id"), index=True)
    role: Mapped[str] = mapped_column(String(16))  # "user" | "assistant" | "system"
    content: Mapped[str] = mapped_column(Text)
    sequence: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped["InterviewSession"] = relationship(back_populates="messages")


class QuestionSelection(Base):
    """First-class record of one adaptive next-question decision --
    written *before* the question is shown, not reconstructed from logs.
    `answer_id`/`answered_at` are filled in once (if) the candidate
    actually answers it."""

    __tablename__ = "question_selections"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("interview_sessions.id"), index=True)
    question_id: Mapped[str] = mapped_column(String(64))
    reason: Mapped[SelectionReason] = mapped_column(Enum(SelectionReason, native_enum=False))
    # Python-side default -- next_question.py's mark_question_answered()
    # orders by this column to find the most recent unanswered selection
    # for a question_id; same tie-breaking rationale as Answer.created_at.
    selected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    answer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("answers.id"))

    session: Mapped["InterviewSession"] = relationship(back_populates="question_selections")


class CVUpload(Base):
    """One CV/resume upload attempt, with provenance and extraction
    status -- extracted text is never silently trusted as fact; it's fed
    through the same extraction/confidence pipeline as any open answer
    (app/services/assessment/cv.py), tagged `Answer.source="cv"`."""

    __tablename__ = "cv_uploads"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("interview_sessions.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str | None] = mapped_column(String(128))
    extraction_status: Mapped[CVExtractionStatus] = mapped_column(
        Enum(CVExtractionStatus, native_enum=False), default=CVExtractionStatus.PENDING
    )
    extracted_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped["InterviewSession"] = relationship(back_populates="cv_uploads")
