"""Minimal V1 Product Access / Entitlement layer (Stage 1 --
docs/product/14_MIY_NAPRYAM_V1_PRODUCT_DEFINITION.md §5). Deliberately not
a billing platform: no real payment provider here (Stage 4), no
invoicing, no subscriptions -- just enough to answer
`can_user_start_assessment` and to support organization promo-code
distribution with attribution and DB-enforced redemption limits.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AdminRole, AdminUser
from app.db.models_access import (
    Entitlement,
    EntitlementSource,
    Organization,
    PackageAllocation,
    PromoCode,
    PromoRedemption,
)
from app.services.audit import record_audit
from app.services.events import emit_event
from app.services.exceptions import InsufficientRoleError, PromoAllocationExhaustedError, PromoCodeInvalidError

_GRANT_ROLES = {AdminRole.SUPER_ADMIN, AdminRole.ADMIN, AdminRole.MANAGER}


def _require_grant_role(admin: AdminUser) -> None:
    if admin.role not in _GRANT_ROLES:
        raise InsufficientRoleError(f"role {admin.role.value} may not grant product access")


async def can_user_start_assessment(session: AsyncSession, *, user_id: uuid.UUID, plan_code: str | None = None) -> bool:
    """True if the user holds at least one active (non-revoked)
    entitlement -- for a specific plan if `plan_code` is given, for any
    plan otherwise. This is the single function every access-gated flow
    must call; nothing else decides "does this user have access"."""
    return await get_any_active_entitlement(session, user_id=user_id, plan_code=plan_code) is not None


async def get_any_active_entitlement(
    session: AsyncSession, *, user_id: uuid.UUID, plan_code: str | None = None
) -> Entitlement | None:
    """Which entitlement backs `can_user_start_assessment`'s True answer --
    callers that need to actually start an assessment (which requires a
    concrete plan_code, not just a yes/no) use this instead."""
    query = select(Entitlement).where(Entitlement.user_id == user_id, Entitlement.revoked_at.is_(None))
    if plan_code is not None:
        query = query.where(Entitlement.plan_code == plan_code)
    result = await session.execute(query.order_by(Entitlement.granted_at.desc()).limit(1))
    return result.scalar_one_or_none()


async def grant_manual_access(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    plan_code: str,
    granted_by_admin: AdminUser,
) -> Entitlement:
    """Admin/test-fixture grant (requirement 6.A). Server-side role check
    happens here, not only at whatever API boundary calls this -- defense
    in depth, since this function may eventually be called from more than
    one place."""
    _require_grant_role(granted_by_admin)

    entitlement = Entitlement(
        user_id=user_id,
        plan_code=plan_code,
        source=EntitlementSource.MANUAL,
        granted_by_admin_id=granted_by_admin.id,
    )
    session.add(entitlement)
    await session.commit()
    await session.refresh(entitlement)
    await record_audit(
        session,
        entity_type="entitlement",
        entity_id=str(entitlement.id),
        action="manual_grant",
        actor_admin_id=granted_by_admin.id,
        actor_user_id=user_id,
        after={"plan_code": plan_code, "source": EntitlementSource.MANUAL.value},
    )
    emit_event("product_access_granted", user_id=str(user_id), plan_code=plan_code, source="manual")
    return entitlement


async def create_package_allocation(
    session: AsyncSession,
    *,
    plan_code: str,
    total_quantity: int,
    created_by_admin: AdminUser,
    organization_id: uuid.UUID | None = None,
    note: str | None = None,
) -> PackageAllocation:
    _require_grant_role(created_by_admin)
    allocation = PackageAllocation(
        organization_id=organization_id,
        plan_code=plan_code,
        total_quantity=total_quantity,
        created_by_admin_id=created_by_admin.id,
        note=note,
    )
    session.add(allocation)
    await session.commit()
    await session.refresh(allocation)
    await record_audit(
        session,
        entity_type="package_allocation",
        entity_id=str(allocation.id),
        action="create",
        actor_admin_id=created_by_admin.id,
        after={"plan_code": plan_code, "total_quantity": total_quantity, "organization_id": str(organization_id) if organization_id else None},
    )
    return allocation


async def issue_promo_code(
    session: AsyncSession, *, allocation_id: uuid.UUID, max_redemptions: int = 1
) -> PromoCode:
    code = PromoCode(allocation_id=allocation_id, code=_generate_code(), max_redemptions=max_redemptions)
    session.add(code)
    await session.commit()
    await session.refresh(code)
    return code


def _generate_code() -> str:
    return secrets.token_hex(4).upper()


async def redeem_promo_code(session: AsyncSession, *, code: str, user_id: uuid.UUID) -> Entitlement:
    """Idempotent: redeeming the same code as the same user twice returns
    the entitlement created the first time, never a second one
    (`UNIQUE(promo_code_id, user_id)` on `PromoRedemption` is the ultimate
    guarantee, not just this early-return check). Allocation overspend is
    prevented by locking the `PackageAllocation` row
    (`with_for_update()`) before counting existing redemptions across all
    of its codes -- a plain check-then-insert would race under concurrent
    redemption near the limit; the row lock serializes it. `with_for_update`
    is a documented no-op on SQLite (used by the test suite) since SQLite
    already serializes writes at the whole-database level -- the real
    protection this buys is on PostgreSQL, where Stage 1 actually runs."""
    result = await session.execute(select(PromoCode).where(PromoCode.code == code))
    promo = result.scalar_one_or_none()
    if promo is None or promo.revoked_at is not None:
        raise PromoCodeInvalidError(f"promo code {code!r} is invalid or revoked")

    existing = await _find_redemption(session, promo.id, user_id)
    if existing is not None:
        return await _entitlement_for_redemption(session, existing.id)

    allocation = (
        await session.execute(select(PackageAllocation).where(PackageAllocation.id == promo.allocation_id).with_for_update())
    ).scalar_one()

    total_redeemed = (
        await session.execute(
            select(func.count())
            .select_from(PromoRedemption)
            .join(PromoCode, PromoRedemption.promo_code_id == PromoCode.id)
            .where(PromoCode.allocation_id == allocation.id)
        )
    ).scalar_one()
    if total_redeemed >= allocation.total_quantity:
        raise PromoAllocationExhaustedError(f"allocation {allocation.id} has no remaining seats")

    code_redeemed = (
        await session.execute(select(func.count()).select_from(PromoRedemption).where(PromoRedemption.promo_code_id == promo.id))
    ).scalar_one()
    if code_redeemed >= promo.max_redemptions:
        raise PromoCodeInvalidError(f"promo code {code!r} has reached its redemption limit")

    redemption = PromoRedemption(promo_code_id=promo.id, user_id=user_id)
    session.add(redemption)
    try:
        await session.flush()
    except IntegrityError:
        # Lost a race with a concurrent redemption of the same code by the
        # same user -- the other request's row won, use it (idempotent).
        await session.rollback()
        existing = await _find_redemption(session, promo.id, user_id)
        assert existing is not None
        return await _entitlement_for_redemption(session, existing.id)

    entitlement = Entitlement(
        user_id=user_id,
        plan_code=allocation.plan_code,
        source=EntitlementSource.PROMO,
        redemption_id=redemption.id,
    )
    session.add(entitlement)
    await session.commit()
    await session.refresh(entitlement)
    emit_event("promo_redeemed", user_id=str(user_id), plan_code=allocation.plan_code, promo_code=code)
    emit_event("product_access_granted", user_id=str(user_id), plan_code=allocation.plan_code, source="promo")
    return entitlement


async def _find_redemption(session: AsyncSession, promo_code_id: uuid.UUID, user_id: uuid.UUID) -> PromoRedemption | None:
    result = await session.execute(
        select(PromoRedemption).where(PromoRedemption.promo_code_id == promo_code_id, PromoRedemption.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def _entitlement_for_redemption(session: AsyncSession, redemption_id: uuid.UUID) -> Entitlement:
    result = await session.execute(select(Entitlement).where(Entitlement.redemption_id == redemption_id))
    return result.scalar_one()
