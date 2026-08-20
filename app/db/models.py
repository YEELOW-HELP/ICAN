from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ScreeningState(str, enum.Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    CONFIRMED = "confirmed"


class MessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    screening_state: Mapped[ScreeningState] = mapped_column(
        Enum(ScreeningState, native_enum=False), default=ScreeningState.NOT_STARTED
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
