"""Founder hardening review, item 2: a started InterviewSession must
persist the concrete entitlement that actually granted access --
`entitlement_id` is never left NULL when a real entitlement exists, and
an explicitly-passed entitlement_id is validated server-side (belongs to
the user, active, matches plan_code) rather than trusted blindly.
"""

from datetime import datetime, timezone

import pytest

from app.core.security import hash_password
from app.db.models import AdminRole, AdminUser
from app.db.models_identity import IdentityUser
from app.services.assessment.sessions import start_assessment
from app.services.exceptions import ProductAccessRequiredError
from app.services.product_access import grant_manual_access


async def _make_admin(session) -> AdminUser:
    admin = AdminUser(email="ent-admin@test.dev", password_hash=hash_password("pw"), role=AdminRole.ADMIN)
    session.add(admin)
    await session.commit()
    await session.refresh(admin)
    return admin


async def _make_user(session) -> IdentityUser:
    user = IdentityUser()
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def test_started_session_persists_the_resolved_entitlement(session_factory):
    async with session_factory() as session:
        admin = await _make_admin(session)
        user = await _make_user(session)
        entitlement = await grant_manual_access(session, user_id=user.id, plan_code="BASIC", granted_by_admin=admin)

        interview_session = await start_assessment(session, user_id=user.id, plan_code="BASIC")

        assert interview_session.entitlement_id == entitlement.id


async def test_explicit_entitlement_id_is_persisted_when_valid(session_factory):
    async with session_factory() as session:
        admin = await _make_admin(session)
        user = await _make_user(session)
        entitlement = await grant_manual_access(session, user_id=user.id, plan_code="BASIC", granted_by_admin=admin)

        interview_session = await start_assessment(
            session, user_id=user.id, plan_code="BASIC", entitlement_id=entitlement.id
        )

        assert interview_session.entitlement_id == entitlement.id


async def test_another_users_entitlement_is_rejected(session_factory):
    async with session_factory() as session:
        admin = await _make_admin(session)
        owner = await _make_user(session)
        intruder = await _make_user(session)
        entitlement = await grant_manual_access(session, user_id=owner.id, plan_code="BASIC", granted_by_admin=admin)

        with pytest.raises(ProductAccessRequiredError):
            await start_assessment(
                session, user_id=intruder.id, plan_code="BASIC", entitlement_id=entitlement.id
            )


async def test_entitlement_for_wrong_plan_is_rejected(session_factory):
    async with session_factory() as session:
        admin = await _make_admin(session)
        user = await _make_user(session)
        entitlement = await grant_manual_access(session, user_id=user.id, plan_code="PREMIUM", granted_by_admin=admin)

        with pytest.raises(ProductAccessRequiredError):
            await start_assessment(
                session, user_id=user.id, plan_code="BASIC", entitlement_id=entitlement.id
            )


async def test_revoked_entitlement_is_rejected(session_factory):
    async with session_factory() as session:
        admin = await _make_admin(session)
        user = await _make_user(session)
        entitlement = await grant_manual_access(session, user_id=user.id, plan_code="BASIC", granted_by_admin=admin)
        entitlement.revoked_at = datetime.now(timezone.utc)
        await session.commit()

        with pytest.raises(ProductAccessRequiredError):
            await start_assessment(
                session, user_id=user.id, plan_code="BASIC", entitlement_id=entitlement.id
            )

        # the implicit-resolution path must also see it as gone, not just
        # the explicit-entitlement-id path
        with pytest.raises(ProductAccessRequiredError):
            await start_assessment(session, user_id=user.id, plan_code="BASIC")
