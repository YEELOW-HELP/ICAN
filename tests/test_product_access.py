import pytest

from app.core.security import hash_password
from app.db.models import AdminRole, AdminUser
from app.db.models_identity import IdentityUser
from app.services.exceptions import InsufficientRoleError, PromoAllocationExhaustedError, PromoCodeInvalidError
from app.services.product_access import (
    can_user_start_assessment,
    create_package_allocation,
    grant_manual_access,
    issue_promo_code,
    redeem_promo_code,
)


async def _make_user(session) -> IdentityUser:
    user = IdentityUser()
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def _make_admin(session, role=AdminRole.ADMIN) -> AdminUser:
    admin = AdminUser(email=f"{role.value}@test.dev", password_hash=hash_password("pw"), role=role)
    session.add(admin)
    await session.commit()
    await session.refresh(admin)
    return admin


async def test_manual_grant_gives_basic_entitlement(session_factory):
    async with session_factory() as session:
        user = await _make_user(session)
        admin = await _make_admin(session)

        await grant_manual_access(session, user_id=user.id, plan_code="BASIC", granted_by_admin=admin)

        assert await can_user_start_assessment(session, user_id=user.id, plan_code="BASIC") is True


async def test_manual_grant_for_one_plan_does_not_grant_the_other(session_factory):
    async with session_factory() as session:
        user = await _make_user(session)
        admin = await _make_admin(session)

        await grant_manual_access(session, user_id=user.id, plan_code="PREMIUM", granted_by_admin=admin)

        assert await can_user_start_assessment(session, user_id=user.id, plan_code="PREMIUM") is True
        assert await can_user_start_assessment(session, user_id=user.id, plan_code="BASIC") is False


async def test_unprivileged_role_cannot_grant_manual_access(session_factory):
    async with session_factory() as session:
        user = await _make_user(session)
        consultant = await _make_admin(session, role=AdminRole.CAREER_CONSULTANT)

        with pytest.raises(InsufficientRoleError):
            await grant_manual_access(session, user_id=user.id, plan_code="BASIC", granted_by_admin=consultant)

        assert await can_user_start_assessment(session, user_id=user.id, plan_code="BASIC") is False


async def test_valid_promo_redemption_grants_entitlement_and_attribution(session_factory):
    async with session_factory() as session:
        admin = await _make_admin(session)
        allocation = await create_package_allocation(session, plan_code="BASIC", total_quantity=10, created_by_admin=admin)
        promo = await issue_promo_code(session, allocation_id=allocation.id)

        user = await _make_user(session)
        entitlement = await redeem_promo_code(session, code=promo.code, user_id=user.id)

        assert entitlement.plan_code == "BASIC"
        assert entitlement.redemption_id is not None
        assert await can_user_start_assessment(session, user_id=user.id, plan_code="BASIC") is True


async def test_duplicate_promo_redemption_by_same_user_is_idempotent(session_factory):
    async with session_factory() as session:
        admin = await _make_admin(session)
        allocation = await create_package_allocation(session, plan_code="BASIC", total_quantity=10, created_by_admin=admin)
        promo = await issue_promo_code(session, allocation_id=allocation.id)
        user = await _make_user(session)

        first = await redeem_promo_code(session, code=promo.code, user_id=user.id)
        second = await redeem_promo_code(session, code=promo.code, user_id=user.id)

        assert first.id == second.id


async def test_invalid_promo_code_is_rejected(session_factory):
    async with session_factory() as session:
        user = await _make_user(session)
        with pytest.raises(PromoCodeInvalidError):
            await redeem_promo_code(session, code="DOES-NOT-EXIST", user_id=user.id)


async def test_allocation_cannot_be_overspent(session_factory):
    async with session_factory() as session:
        admin = await _make_admin(session)
        allocation = await create_package_allocation(session, plan_code="BASIC", total_quantity=1, created_by_admin=admin)
        promo_a = await issue_promo_code(session, allocation_id=allocation.id)
        promo_b = await issue_promo_code(session, allocation_id=allocation.id)

        first_user = await _make_user(session)
        await redeem_promo_code(session, code=promo_a.code, user_id=first_user.id)

        second_user = await _make_user(session)
        with pytest.raises(PromoAllocationExhaustedError):
            await redeem_promo_code(session, code=promo_b.code, user_id=second_user.id)


async def test_promo_code_max_redemptions_is_enforced(session_factory):
    async with session_factory() as session:
        admin = await _make_admin(session)
        allocation = await create_package_allocation(session, plan_code="BASIC", total_quantity=10, created_by_admin=admin)
        promo = await issue_promo_code(session, allocation_id=allocation.id, max_redemptions=1)

        first_user = await _make_user(session)
        await redeem_promo_code(session, code=promo.code, user_id=first_user.id)

        second_user = await _make_user(session)
        with pytest.raises(PromoCodeInvalidError):
            await redeem_promo_code(session, code=promo.code, user_id=second_user.id)


async def test_revoked_promo_code_cannot_be_redeemed(session_factory):
    from datetime import datetime, timezone

    async with session_factory() as session:
        admin = await _make_admin(session)
        allocation = await create_package_allocation(session, plan_code="BASIC", total_quantity=10, created_by_admin=admin)
        promo = await issue_promo_code(session, allocation_id=allocation.id)
        promo.revoked_at = datetime.now(timezone.utc)
        await session.commit()

        user = await _make_user(session)
        with pytest.raises(PromoCodeInvalidError):
            await redeem_promo_code(session, code=promo.code, user_id=user.id)


async def test_organization_attribution_is_preserved_through_the_chain(session_factory):
    from app.db.models_access import Organization

    async with session_factory() as session:
        admin = await _make_admin(session)
        org = Organization(name="Charity Fund")
        session.add(org)
        await session.commit()
        await session.refresh(org)

        allocation = await create_package_allocation(
            session, plan_code="BASIC", total_quantity=5, created_by_admin=admin, organization_id=org.id
        )
        promo = await issue_promo_code(session, allocation_id=allocation.id)
        user = await _make_user(session)
        entitlement = await redeem_promo_code(session, code=promo.code, user_id=user.id)

        # Walk the chain back: Entitlement -> Redemption -> PromoCode -> Allocation -> Organization
        from sqlalchemy import select

        from app.db.models_access import PackageAllocation, PromoCode, PromoRedemption

        redemption = await session.get(PromoRedemption, entitlement.redemption_id)
        code_row = await session.get(PromoCode, redemption.promo_code_id)
        alloc_row = await session.get(PackageAllocation, code_row.allocation_id)
        assert alloc_row.organization_id == org.id
