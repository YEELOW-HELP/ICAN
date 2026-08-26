from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Enum, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ScreeningState(str, enum.Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    CONFIRMED = "confirmed"


class MessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"


class AdminRole(str, enum.Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    MANAGER = "manager"
    CAREER_CONSULTANT = "career_consultant"
    REVIEWER = "reviewer"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    telegram_username: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(64))
    email: Mapped[str | None] = mapped_column(String(255))
    screening_state: Mapped[ScreeningState] = mapped_column(
        Enum(ScreeningState, native_enum=False), default=ScreeningState.NOT_STARTED
    )
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Bridge to the new canonical identity (app/db/models_identity.py),
    # populated opportunistically when a Telegram id already known here is
    # first resolved through the V1 AuthIdentity flow -- never backfilled
    # in bulk (Migration Map #1's additive-adapter approach; a full
    # production cutover is a separate, explicitly reviewed step).
    canonical_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("identity_users.id")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    profile: Mapped["Profile | None"] = relationship(back_populates="user", uselist=False)
    messages: Mapped[list["Message"]] = relationship(back_populates="user", order_by="Message.created_at")


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)

    name: Mapped[str | None] = mapped_column(String(255))
    country: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str | None] = mapped_column(String(64))  # working / not_working / studying / other
    education: Mapped[str | None] = mapped_column(Text)
    total_experience: Mapped[str | None] = mapped_column(String(128))
    previous_positions: Mapped[list | None] = mapped_column(JSON)
    skills: Mapped[list | None] = mapped_column(JSON)
    languages: Mapped[list | None] = mapped_column(JSON)
    desired_role: Mapped[str | None] = mapped_column(String(255))
    desired_min_income: Mapped[str | None] = mapped_column(String(64))
    desired_currency: Mapped[str | None] = mapped_column(String(16))
    employment_format: Mapped[str | None] = mapped_column(String(64))  # full-time / part-time / other
    work_format: Mapped[str | None] = mapped_column(String(64))  # onsite / hybrid / remote / flexible
    schedule: Mapped[str | None] = mapped_column(String(255))
    constraints: Mapped[str | None] = mapped_column(Text)
    other_notes: Mapped[str | None] = mapped_column(Text)

    # Free-form bucket for additional facts not covered by the fixed columns above
    # (ТЗ п.11: "Profile Facts / аналогічна структура").
    extra_facts: Mapped[dict | None] = mapped_column(JSON)

    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="profile")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[MessageRole] = mapped_column(Enum(MessageRole, native_enum=False))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="messages")


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[AdminRole] = mapped_column(Enum(AdminRole, native_enum=False))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProfileEditLog(Base):
    """Audit trail for manual profile edits made from the admin dashboard —
    keeps the previous value instead of silently overwriting it (ТЗ п.6.3, п.15)."""

    __tablename__ = "profile_edit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    field_name: Mapped[str] = mapped_column(String(64))
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    edited_by: Mapped[str] = mapped_column(String(255))
    edited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
