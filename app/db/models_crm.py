"""ICAN CRM 1.0 data model (see docs/ICAN_CRM_1.0_Final_TZ_UA.docx).

`Client` is the single canonical record for a person the ICAN team works
with, regardless of which channel they arrived through (Telegram bot today;
website/mobile app later). `Client.telegram_user_id` links back to the bot's
own `User` row when the channel is Telegram — the bot's AI screening result
pre-fills the CRM profile instead of the client re-entering everything.

Flexible "pick one, or type your own" fields (ТЗ §9's "Інше → ручне поле"
pattern) are stored as plain strings/JSON, not DB enums — only values the
*system* branches on (status, role, file type, call direction...) are real
enums. This mirrors how `Profile` already works in db/models.py.
"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ClientStatus(str, enum.Enum):
    NEW = "new"
    SCREENING = "screening"
    WAITING_CONSULTANT = "waiting_consultant"
    CAREER_CONSULTATION = "career_consultation"
    READY_FOR_MATCHING = "ready_for_matching"
    IN_WORK = "in_work"
    PAUSED = "paused"
    CLOSED = "closed"


class ClientPriority(str, enum.Enum):
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class SourceChannel(str, enum.Enum):
    TELEGRAM = "telegram"
    PHONE = "phone"
    WEBSITE = "website"
    APP = "app"
    MANAGER = "manager"


class SkillLevel(str, enum.Enum):
    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class CallDirection(str, enum.Enum):
    INCOMING = "incoming"
    OUTGOING = "outgoing"
    MISSED = "missed"


class CallStatus(str, enum.Enum):
    ANSWERED = "answered"
    MISSED = "missed"
    FAILED = "failed"


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    DONE = "done"
    CANCELLED = "cancelled"


class FileType(str, enum.Enum):
    CV = "cv"
    COVER_LETTER = "cover_letter"
    CERTIFICATE = "certificate"
    DIPLOMA = "diploma"
    PORTFOLIO = "portfolio"
    OTHER = "other"


class TimelineEventType(str, enum.Enum):
    CREATED = "created"
    STATUS_CHANGED = "status_changed"
    ASSIGNED = "assigned"
    CALL = "call"
    FILE_UPLOADED = "file_uploaded"
    FILE_DELETED = "file_deleted"
    PROFILE_FIELD_CHANGED = "profile_field_changed"
    SCREENING_COMPLETED = "screening_completed"
    CONSULTATION_COMPLETED = "consultation_completed"
    READY_FOR_MATCHING = "ready_for_matching"
    NOTE = "note"


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Block A — identification & contacts
    first_name: Mapped[str | None] = mapped_column(String(255))
    last_name: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(64), index=True)
    telegram_username: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255))
    birth_date: Mapped[str | None] = mapped_column(String(32))
    country: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(255))
    source_channel: Mapped[SourceChannel] = mapped_column(Enum(SourceChannel, native_enum=False))

    # Channel linkage — set when source_channel == telegram
    telegram_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), unique=True)

    # Block B — CRM ownership & status
    manager_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id"))
    consultant_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id"))
    status: Mapped[ClientStatus] = mapped_column(Enum(ClientStatus, native_enum=False), default=ClientStatus.NEW)
    priority: Mapped[ClientPriority] = mapped_column(
        Enum(ClientPriority, native_enum=False), default=ClientPriority.NORMAL
    )

    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    profile: Mapped["ClientProfile | None"] = relationship(back_populates="client", uselist=False)
    work_experiences: Mapped[list["WorkExperience"]] = relationship(
        back_populates="client", order_by="WorkExperience.id", cascade="all, delete-orphan"
    )
    skills: Mapped[list["ClientSkill"]] = relationship(
        back_populates="client", order_by="ClientSkill.id", cascade="all, delete-orphan"
    )
    languages: Mapped[list["ClientLanguage"]] = relationship(
        back_populates="client", order_by="ClientLanguage.id", cascade="all, delete-orphan"
    )
    consultation: Mapped["CareerConsultation | None"] = relationship(back_populates="client", uselist=False)


class ClientProfile(Base):
    """Blocks C, F, H, I, J plus the consultant's conclusion snapshot — the
    data that isn't a repeatable sub-block and isn't part of Client itself."""

    __tablename__ = "client_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), unique=True, index=True)

    # Block C — current situation
    currently_employed: Mapped[bool | None] = mapped_column(Boolean)
    current_position: Mapped[str | None] = mapped_column(String(255))
    current_fields: Mapped[list | None] = mapped_column(JSON)
    current_income: Mapped[str | None] = mapped_column(String(64))
    current_income_currency: Mapped[str | None] = mapped_column(String(16))
    search_reasons: Mapped[list | None] = mapped_column(JSON)
    readiness_to_start: Mapped[str | None] = mapped_column(String(128))
    readiness_date: Mapped[str | None] = mapped_column(String(32))
    urgency: Mapped[str | None] = mapped_column(String(64))
    nonstandard_info: Mapped[str | None] = mapped_column(Text)
    consultation_consent: Mapped[bool | None] = mapped_column(Boolean)

    # Block F — education & qualification
    education_level: Mapped[str | None] = mapped_column(String(128))
    specialty: Mapped[str | None] = mapped_column(String(255))
    institution: Mapped[str | None] = mapped_column(String(255))
    graduation_year: Mapped[int | None] = mapped_column(Integer)
    courses: Mapped[list | None] = mapped_column(JSON)
    driver_licenses: Mapped[list | None] = mapped_column(JSON)
    other_qualification: Mapped[str | None] = mapped_column(Text)

    # Block H — career target
    primary_target: Mapped[str | None] = mapped_column(String(255))
    alternative_targets: Mapped[list | None] = mapped_column(JSON)
    interesting_fields: Mapped[list | None] = mapped_column(JSON)
    avoid_fields: Mapped[list | None] = mapped_column(JSON)
    open_to_career_change: Mapped[str | None] = mapped_column(String(32))

    # Block I — hard constraints
    min_salary: Mapped[str | None] = mapped_column(String(64))
    desired_salary: Mapped[str | None] = mapped_column(String(64))
    salary_currency: Mapped[str | None] = mapped_column(String(16))
    employment_types: Mapped[list | None] = mapped_column(JSON)
    work_formats: Mapped[list | None] = mapped_column(JSON)
    schedules: Mapped[list | None] = mapped_column(JSON)
    work_cities: Mapped[list | None] = mapped_column(JSON)
    commute_limit: Mapped[str | None] = mapped_column(String(64))
    relocation_ready: Mapped[str | None] = mapped_column(String(32))
    relocation_cities: Mapped[list | None] = mapped_column(JSON)
    business_trips_ok: Mapped[str | None] = mapped_column(String(32))
    start_date: Mapped[str | None] = mapped_column(String(64))

    # Block J — practical constraints
    constraints: Mapped[list | None] = mapped_column(JSON)
    critical_constraint: Mapped[bool] = mapped_column(Boolean, default=False)
    constraints_comment: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    client: Mapped["Client"] = relationship(back_populates="profile")


class WorkExperience(Base):
    """Block D — repeatable."""

    __tablename__ = "work_experiences"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), index=True)

    company: Mapped[str | None] = mapped_column(String(255))
    position: Mapped[str | None] = mapped_column(String(255))
    fields: Mapped[list | None] = mapped_column(JSON)
    start_month_year: Mapped[str | None] = mapped_column(String(16))
    end_month_year: Mapped[str | None] = mapped_column(String(16))  # null/"" = "Дотепер"
    responsibilities: Mapped[str | None] = mapped_column(Text)
    achievements: Mapped[str | None] = mapped_column(Text)
    tools: Mapped[list | None] = mapped_column(JSON)

    client: Mapped["Client"] = relationship(back_populates="work_experiences")


class ClientSkill(Base):
    """Block E — repeatable."""

    __tablename__ = "client_skills"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), index=True)

    skill_name: Mapped[str] = mapped_column(String(255))
    level: Mapped[SkillLevel | None] = mapped_column(Enum(SkillLevel, native_enum=False))
    years_experience: Mapped[int | None] = mapped_column(Integer)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)

    client: Mapped["Client"] = relationship(back_populates="skills")


class ClientLanguage(Base):
    """Block G — repeatable."""

    __tablename__ = "client_languages"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), index=True)

    language: Mapped[str] = mapped_column(String(64))
    level: Mapped[str | None] = mapped_column(String(32))  # A1-C2 / Native / Не знаю
    can_work_in_it: Mapped[str | None] = mapped_column(String(32))  # Так / Частково / Ні

    client: Mapped["Client"] = relationship(back_populates="languages")


class CareerConsultation(Base):
    """The single career consultation (ТЗ §12) — one row per client."""

    __tablename__ = "career_consultations"
    __table_args__ = (UniqueConstraint("client_id", name="uq_career_consultation_client"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), index=True)
    consultant_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id"))

    primary_target: Mapped[str | None] = mapped_column(String(255))
    alternative_targets: Mapped[list | None] = mapped_column(JSON)
    strengths: Mapped[list | None] = mapped_column(JSON)
    skills_gaps: Mapped[list | None] = mapped_column(JSON)
    search_strategy: Mapped[str | None] = mapped_column(Text)
    expectations_realistic: Mapped[str | None] = mapped_column(String(64))
    expectations_comment: Mapped[str | None] = mapped_column(Text)
    conclusion: Mapped[str | None] = mapped_column(Text)

    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    client: Mapped["Client"] = relationship(back_populates="consultation")


class ClientFile(Base):
    __tablename__ = "client_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), index=True)

    file_type: Mapped[FileType] = mapped_column(Enum(FileType, native_enum=False))
    other_description: Mapped[str | None] = mapped_column(String(255))
    filename: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(512))
    content_type: Mapped[str | None] = mapped_column(String(128))
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    is_current_cv: Mapped[bool] = mapped_column(Boolean, default=False)

    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id"))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Call(Base):
    __tablename__ = "calls"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), index=True)

    phonet_call_id: Mapped[str | None] = mapped_column(String(128))
    direction: Mapped[CallDirection] = mapped_column(Enum(CallDirection, native_enum=False))
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[CallStatus] = mapped_column(Enum(CallStatus, native_enum=False))
    recording_url: Mapped[str | None] = mapped_column(String(1024))
    contact_type: Mapped[str | None] = mapped_column(String(64))
    note: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), index=True)

    task_type: Mapped[str] = mapped_column(String(64))  # call / consultation / clarify_data / send_document / other
    other_description: Mapped[str | None] = mapped_column(String(255))
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id"))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus, native_enum=False), default=TaskStatus.PENDING)
    note: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TimelineEvent(Base):
    """Unified timeline + audit feed (ТЗ §16, §21) — every significant client
    event, who did it, and before/after for field-level changes."""

    __tablename__ = "timeline_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), index=True)

    event_type: Mapped[TimelineEventType] = mapped_column(Enum(TimelineEventType, native_enum=False))
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id"))
    description: Mapped[str] = mapped_column(Text)
    before_value: Mapped[str | None] = mapped_column(Text)
    after_value: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
