"""Canonical identity foundation for Product System v3.1 (Stage 1 of
«МОЖУ: Мій Напрям» V1 — docs/product/15_MIY_NAPRYAM_V1_IMPLEMENTATION_ROADMAP.md,
docs/engineering/13_FOUNDER_ARCHITECTURE_REVIEW.md Decision 1/2).

`IdentityUser` is a channel-agnostic human -- the ERD calls this entity
`USER`, but the class is named `IdentityUser` here (not `User`) because
`app/db/models.py` already has an unrelated legacy `User` class on the same
SQLAlchemy declarative `Base`; two classes named `User` in one registry
make string-based `relationship()` resolution ambiguous
(`InvalidRequestError: Multiple classes found for path "User"`). This is a
naming choice, not a schema difference -- the table is `identity_users`,
matching the ERD exactly.

`AuthIdentity` is a per-channel login record (Telegram today; web/Google/
etc. later) — a Telegram id is an `AuthIdentity.provider_subject`, never
the `IdentityUser` identity itself. This is additive and does not touch
the legacy `users` table (ICAN 1.1's Telegram-only identity) — see
`User.canonical_user_id` there for the opportunistic bridge column linking
a legacy row to its canonical counterpart once one exists.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Uuid, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class GrantorRole(str, enum.Enum):
    """Who a Consent was actually granted by, in what capacity -- not a
    legal determination, just what the app was told (Founder Architecture
    Review Decision 2 follow-up fix). Extensible without a migration to the
    enum shape itself changing (native_enum=False stores the string)."""

    SELF = "self"
    GUARDIAN = "guardian"
    AUTHORIZED_REPRESENTATIVE = "authorized_representative"


class IdentityUser(Base):
    """The canonical, channel-agnostic human (ERD entity `USER`).
    Deliberately minimal in Stage 1 -- profile/potential-profile fields
    belong to Stage 2+."""

    __tablename__ = "identity_users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(64))
    locale: Mapped[str] = mapped_column(String(8), default="uk", server_default="uk")
    timezone: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    auth_identities: Mapped[list["AuthIdentity"]] = relationship(back_populates="user")


class AuthIdentity(Base):
    """One authentication channel for an `IdentityUser`. `UNIQUE(provider,
    provider_subject)` is the mechanism that makes "resolve or create" safe
    under concurrent requests -- see app/services/identity.py. Never store
    provider secrets/tokens here; this table identifies a channel, not
    credentials."""

    __tablename__ = "auth_identities"
    __table_args__ = (UniqueConstraint("provider", "provider_subject", name="uq_auth_identity_provider_subject"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("identity_users.id"), index=True)
    provider: Mapped[str] = mapped_column(String(32))  # "telegram" | "web" | "google" | ... (future)
    provider_subject: Mapped[str] = mapped_column(String(255))  # e.g. the Telegram numeric id, as a string
    provider_username: Mapped[str | None] = mapped_column(String(255))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["IdentityUser"] = relationship(back_populates="auth_identities")


class Consent(Base):
    """Versioned, purpose-specific, withdrawable, traceable consent
    (Founder Architecture Review Decision 2, hardened further by the
    grantor_role follow-up fix). `granted_by_user_id` is normally equal to
    `user_id` (self-consent) but may differ -- the mechanism that makes
    future guardian/minor consent possible without redesigning `IdentityUser`.
    No country-specific legal rules are encoded here, by design."""

    __tablename__ = "consents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("identity_users.id"), index=True)
    granted_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("identity_users.id"))
    grantor_role: Mapped[GrantorRole] = mapped_column(Enum(GrantorRole, native_enum=False), default=GrantorRole.SELF)
    purpose: Mapped[str] = mapped_column(String(64))  # e.g. "assessment_v1"
    policy_version: Mapped[str] = mapped_column(String(32))
    source: Mapped[str] = mapped_column(String(32))  # e.g. "telegram_bot" | "web" | "admin_import"
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
