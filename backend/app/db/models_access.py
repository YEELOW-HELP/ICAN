"""Minimal V1 Product Access / Entitlement layer (Stage 1 --
docs/product/14_MIY_NAPRYAM_V1_PRODUCT_DEFINITION.md §5,
15_MIY_NAPRYAM_V1_IMPLEMENTATION_ROADMAP.md §27.2). Deliberately not a
billing platform: no invoicing, no subscriptions, no real payment
provider (that's Stage 4) -- just enough to answer
`can_user_start_assessment(user_id, plan_code)` and to support
organization-purchased promo-code distribution with attribution.

Model: Organization -> PackageAllocation -> PromoCode -> PromoRedemption
-> Entitlement. `ProductPlan` holds price as configuration data, never as
authorization logic -- nothing here branches on a hard-coded price.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Uuid, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class EntitlementSource(str, enum.Enum):
    MANUAL = "manual"  # admin/test fixture grant
    PROMO = "promo"  # redeemed from an organization-issued promo code
    PAYMENT = "payment"  # Stage 4: real payment provider (not wired yet)


class ProductPlan(Base):
    """Configuration, not business logic: BASIC/PREMIUM and their
    indicative price live here as data. A price change is a data update,
    never a code deploy."""

    __tablename__ = "product_plans"

    plan_code: Mapped[str] = mapped_column(String(32), primary_key=True)  # "BASIC" | "PREMIUM"
    display_name: Mapped[str] = mapped_column(String(128))
    price_amount_minor: Mapped[int] = mapped_column(Integer)  # e.g. 50000 = 500.00 UAH
    price_currency: Mapped[str] = mapped_column(String(8), default="UAH")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Organization(Base):
    """A charitable foundation, school, NGO, coach, or partner that
    purchases assessment packages for its own users."""

    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    contact_info: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PackageAllocation(Base):
    """A purchased (or admin-granted) batch of N entitlements for one plan,
    optionally attributed to an Organization. `total_quantity` is the hard
    ceiling promo codes issued from this allocation may redeem in total --
    enforced with a row lock at redemption time (see
    app/services/product_access.py), not just checked-then-inserted."""

    __tablename__ = "package_allocations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id"), index=True)
    plan_code: Mapped[str] = mapped_column(ForeignKey("product_plans.plan_code"))
    total_quantity: Mapped[int] = mapped_column(Integer)
    created_by_admin_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id"))
    note: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    promo_codes: Mapped[list["PromoCode"]] = relationship(back_populates="allocation")


class PromoCode(Base):
    """One redeemable code drawn from an allocation.
    `max_redemptions` defaults to 1 (one code, one user) but is not hard-1
    in the schema, since a coach handing one code to a small cohort is a
    realistic V1 case."""

    __tablename__ = "promo_codes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    allocation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("package_allocations.id"), index=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    max_redemptions: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    allocation: Mapped["PackageAllocation"] = relationship(back_populates="promo_codes")
    redemptions: Mapped[list["PromoRedemption"]] = relationship(back_populates="promo_code")


class PromoRedemption(Base):
    """One user's redemption of one promo code. `UNIQUE(promo_code_id,
    user_id)` makes the same user redeeming the same code twice a no-op at
    the database level, not just a service-layer check."""

    __tablename__ = "promo_redemptions"
    __table_args__ = (UniqueConstraint("promo_code_id", "user_id", name="uq_promo_redemption_code_user"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    promo_code_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("promo_codes.id"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("identity_users.id"), index=True)
    redeemed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    promo_code: Mapped["PromoCode"] = relationship(back_populates="redemptions")


class Entitlement(Base):
    """The actual "has access" grant a user holds for a plan --
    `can_user_start_assessment` (app/services/product_access.py) queries
    this, nothing else. `redemption_id` is unique: one entitlement per
    redemption, so a redemption can never silently grant access twice."""

    __tablename__ = "entitlements"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("identity_users.id"), index=True)
    plan_code: Mapped[str] = mapped_column(ForeignKey("product_plans.plan_code"))
    source: Mapped[EntitlementSource] = mapped_column(Enum(EntitlementSource, native_enum=False))
    granted_by_admin_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id"))
    redemption_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("promo_redemptions.id"), unique=True)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
