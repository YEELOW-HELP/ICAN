from app.core.security import hash_password
from app.db.models import AdminRole, AdminUser, ScreeningState
from app.schemas.profile import ProfileDraft
from app.services import admin_service, profile_service


async def _make_admin(session, email="admin@ican.dev", password="hunter2", role=AdminRole.ADMIN) -> AdminUser:
    admin = AdminUser(email=email, password_hash=hash_password(password), role=role)
    session.add(admin)
    await session.commit()
    await session.refresh(admin)
    return admin


async def test_authenticate_admin_accepts_correct_password(session):
    await _make_admin(session, password="correct-horse")
    admin = await admin_service.authenticate_admin(session, "admin@ican.dev", "correct-horse")
    assert admin is not None
    assert admin.email == "admin@ican.dev"


async def test_authenticate_admin_rejects_wrong_password(session):
    await _make_admin(session, password="correct-horse")
    admin = await admin_service.authenticate_admin(session, "admin@ican.dev", "wrong")
    assert admin is None


async def test_authenticate_admin_rejects_unknown_email(session):
    admin = await admin_service.authenticate_admin(session, "nobody@ican.dev", "whatever")
    assert admin is None


async def test_profile_completion_counts_filled_fields(session):
    user = await profile_service.get_or_create_user(session, telegram_id=1)
    profile = await profile_service.apply_profile_draft(session, user, ProfileDraft(name="Олена", city="Київ"))
    pct = admin_service.profile_completion(profile)
    assert 0 < pct < 100


async def test_profile_completion_is_zero_for_empty_profile(session):
    user = await profile_service.get_or_create_user(session, telegram_id=2)
    profile = await profile_service.get_profile(session, user)
    assert admin_service.profile_completion(profile) == 0


async def test_list_users_filters_by_status(session):
    u1 = await profile_service.get_or_create_user(session, telegram_id=10)
    await profile_service.set_state(session, u1, ScreeningState.CONFIRMED)
    u2 = await profile_service.get_or_create_user(session, telegram_id=11)
    await profile_service.set_state(session, u2, ScreeningState.IN_PROGRESS)

    rows, total = await admin_service.list_users(session, status_filter="confirmed")

    assert total == 1
    assert rows[0][0].telegram_id == 10


async def test_list_users_search_matches_telegram_id(session):
    await profile_service.get_or_create_user(session, telegram_id=999888777)

    rows, total = await admin_service.list_users(session, search="999888777")

    assert total == 1


async def test_update_profile_logs_changed_fields_only(session):
    user = await profile_service.get_or_create_user(session, telegram_id=20)
    profile = await profile_service.apply_profile_draft(session, user, ProfileDraft(city="Харків"))

    logs = await admin_service.update_profile(
        session, profile, {"city": "Харків", "desired_role": "бухгалтер"}, edited_by="admin@ican.dev"
    )

    # "city" unchanged (same value) must not be logged; only the real change is
    assert len(logs) == 1
    assert logs[0].field_name == "desired_role"
    assert logs[0].old_value is None
    assert logs[0].new_value == "бухгалтер"
    assert logs[0].edited_by == "admin@ican.dev"


async def test_update_status_changes_screening_state_and_block_flag(session):
    user = await profile_service.get_or_create_user(session, telegram_id=30)

    updated = await admin_service.update_status(session, user, "paused", True)

    assert updated.screening_state == ScreeningState.PAUSED
    assert updated.is_blocked is True


async def test_dashboard_summary_counts_users_by_bucket(session):
    u1 = await profile_service.get_or_create_user(session, telegram_id=40)
    await profile_service.set_state(session, u1, ScreeningState.CONFIRMED)
    u2 = await profile_service.get_or_create_user(session, telegram_id=41)
    await profile_service.set_state(session, u2, ScreeningState.IN_PROGRESS)
    u3 = await profile_service.get_or_create_user(session, telegram_id=42)  # NOT_STARTED

    summary = await admin_service.get_dashboard_summary(session)

    assert summary["total_users"] == 3
    assert summary["completed"] == 1
    assert summary["in_progress"] == 1
    assert summary["not_completed"] == 1
