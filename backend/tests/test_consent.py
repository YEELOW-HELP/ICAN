import pytest

from app.core.security import hash_password
from app.db.models import AdminRole, AdminUser
from app.db.models_identity import GrantorRole, IdentityUser
from app.services.consent import ASSESSMENT_PURPOSE, grant_consent, has_active_consent, withdraw_consent
from app.services.exceptions import ConsentOwnershipError, InsufficientRoleError


async def _make_user(session):
    user = IdentityUser()
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def test_grant_consent_records_purpose_and_version(session_factory):
    async with session_factory() as session:
        user = await _make_user(session)
        consent = await grant_consent(session, user_id=user.id, purpose=ASSESSMENT_PURPOSE, source="telegram_bot")

        assert consent.purpose == ASSESSMENT_PURPOSE
        assert consent.policy_version == "v1"
        assert consent.grantor_role == GrantorRole.SELF
        assert consent.granted_by_user_id == user.id
        assert consent.withdrawn_at is None


async def test_has_active_consent_false_before_any_grant(session_factory):
    async with session_factory() as session:
        user = await _make_user(session)
        assert await has_active_consent(session, user_id=user.id, purpose=ASSESSMENT_PURPOSE) is False


async def test_has_active_consent_true_after_grant(session_factory):
    async with session_factory() as session:
        user = await _make_user(session)
        await grant_consent(session, user_id=user.id, purpose=ASSESSMENT_PURPOSE, source="telegram_bot")
        assert await has_active_consent(session, user_id=user.id, purpose=ASSESSMENT_PURPOSE) is True


async def test_withdrawn_consent_is_no_longer_active(session_factory):
    async with session_factory() as session:
        user = await _make_user(session)
        consent = await grant_consent(session, user_id=user.id, purpose=ASSESSMENT_PURPOSE, source="telegram_bot")
        await withdraw_consent(session, consent.id, requested_by_user_id=user.id)

        assert await has_active_consent(session, user_id=user.id, purpose=ASSESSMENT_PURPOSE) is False


async def test_consent_history_is_append_only_regrant_after_withdrawal_creates_new_row(session_factory):
    async with session_factory() as session:
        user = await _make_user(session)
        first = await grant_consent(session, user_id=user.id, purpose=ASSESSMENT_PURPOSE, source="telegram_bot")
        await withdraw_consent(session, first.id, requested_by_user_id=user.id)
        second = await grant_consent(session, user_id=user.id, purpose=ASSESSMENT_PURPOSE, source="telegram_bot")

        assert second.id != first.id
        assert await has_active_consent(session, user_id=user.id, purpose=ASSESSMENT_PURPOSE) is True

        # the original withdrawal is preserved, not overwritten by the new grant
        from sqlalchemy import select

        from app.db.models_identity import Consent

        result = await session.execute(select(Consent).where(Consent.id == first.id))
        preserved = result.scalar_one()
        assert preserved.withdrawn_at is not None


async def test_withdraw_consent_requires_an_actor(session_factory):
    async with session_factory() as session:
        user = await _make_user(session)
        consent = await grant_consent(session, user_id=user.id, purpose=ASSESSMENT_PURPOSE, source="telegram_bot")

        with pytest.raises(ConsentOwnershipError):
            await withdraw_consent(session, consent.id)

        assert await has_active_consent(session, user_id=user.id, purpose=ASSESSMENT_PURPOSE) is True


async def test_user_cannot_withdraw_another_users_consent(session_factory):
    async with session_factory() as session:
        owner = await _make_user(session)
        intruder = await _make_user(session)
        consent = await grant_consent(session, user_id=owner.id, purpose=ASSESSMENT_PURPOSE, source="telegram_bot")

        with pytest.raises(ConsentOwnershipError):
            await withdraw_consent(session, consent.id, requested_by_user_id=intruder.id)

        assert await has_active_consent(session, user_id=owner.id, purpose=ASSESSMENT_PURPOSE) is True


async def test_authorized_admin_can_withdraw_a_users_consent_and_it_is_audited(session_factory):
    from sqlalchemy import select

    from app.db.models_platform import AuditLog

    async with session_factory() as session:
        user = await _make_user(session)
        admin = AdminUser(email="consent-admin@test.dev", password_hash=hash_password("pw"), role=AdminRole.ADMIN)
        session.add(admin)
        await session.commit()
        await session.refresh(admin)
        consent = await grant_consent(session, user_id=user.id, purpose=ASSESSMENT_PURPOSE, source="telegram_bot")

        await withdraw_consent(session, consent.id, requested_by_admin=admin)

        assert await has_active_consent(session, user_id=user.id, purpose=ASSESSMENT_PURPOSE) is False

        result = await session.execute(select(AuditLog).where(AuditLog.entity_id == str(consent.id)))
        entry = result.scalar_one()
        assert entry.action == "withdraw"
        assert entry.actor_admin_id == admin.id


async def test_unprivileged_admin_cannot_withdraw_a_users_consent(session_factory):
    async with session_factory() as session:
        user = await _make_user(session)
        consultant = AdminUser(
            email="consent-consultant@test.dev", password_hash=hash_password("pw"), role=AdminRole.CAREER_CONSULTANT
        )
        session.add(consultant)
        await session.commit()
        await session.refresh(consultant)
        consent = await grant_consent(session, user_id=user.id, purpose=ASSESSMENT_PURPOSE, source="telegram_bot")

        with pytest.raises(InsufficientRoleError):
            await withdraw_consent(session, consent.id, requested_by_admin=consultant)

        assert await has_active_consent(session, user_id=user.id, purpose=ASSESSMENT_PURPOSE) is True


async def test_guardian_can_grant_consent_on_behalf_of_a_minor_user(session_factory):
    async with session_factory() as session:
        minor = await _make_user(session)
        guardian = await _make_user(session)

        consent = await grant_consent(
            session,
            user_id=minor.id,
            purpose=ASSESSMENT_PURPOSE,
            source="telegram_bot",
            granted_by_user_id=guardian.id,
            grantor_role=GrantorRole.GUARDIAN,
        )

        assert consent.user_id == minor.id
        assert consent.granted_by_user_id == guardian.id
        assert consent.grantor_role == GrantorRole.GUARDIAN
        assert await has_active_consent(session, user_id=minor.id, purpose=ASSESSMENT_PURPOSE) is True
