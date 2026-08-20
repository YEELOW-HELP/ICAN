from app.core.security import hash_password
from app.db.models import AdminRole, AdminUser
from app.db.models_crm import ClientStatus, SourceChannel
from app.services.crm import clients as client_service


async def _make_staff(session, email, role) -> AdminUser:
    staff = AdminUser(email=email, password_hash=hash_password("pw"), role=role)
    session.add(staff)
    await session.commit()
    await session.refresh(staff)
    return staff


async def test_create_client_creates_empty_profile_and_timeline_event(session):
    admin = await _make_staff(session, "admin@ican.dev", AdminRole.ADMIN)

    client = await client_service.create_client(
        session, source_channel=SourceChannel.PHONE, actor=admin, first_name="Олена"
    )

    fetched = await client_service.get_client(session, client.id)
    assert fetched.profile is not None
    assert fetched.status == ClientStatus.NEW


async def test_career_consultant_only_sees_assigned_clients(session):
    admin = await _make_staff(session, "admin@ican.dev", AdminRole.ADMIN)
    consultant = await _make_staff(session, "consultant@ican.dev", AdminRole.CAREER_CONSULTANT)

    c1 = await client_service.create_client(session, source_channel=SourceChannel.PHONE, actor=admin, first_name="A")
    c2 = await client_service.create_client(session, source_channel=SourceChannel.PHONE, actor=admin, first_name="B")
    await client_service.assign_consultant(session, c1, consultant, admin)

    rows, total = await client_service.list_clients(session, viewer=consultant)

    assert total == 1
    assert rows[0].id == c1.id


async def test_admin_sees_all_clients(session):
    admin = await _make_staff(session, "admin@ican.dev", AdminRole.ADMIN)
    await client_service.create_client(session, source_channel=SourceChannel.PHONE, actor=admin, first_name="A")
    await client_service.create_client(session, source_channel=SourceChannel.PHONE, actor=admin, first_name="B")

    rows, total = await client_service.list_clients(session, viewer=admin)

    assert total == 2


async def test_assign_consultant_advances_status_from_waiting_consultant(session):
    admin = await _make_staff(session, "admin@ican.dev", AdminRole.ADMIN)
    consultant = await _make_staff(session, "consultant@ican.dev", AdminRole.CAREER_CONSULTANT)
    client = await client_service.create_client(session, source_channel=SourceChannel.PHONE, actor=admin)
    await client_service.set_status(session, client, ClientStatus.WAITING_CONSULTANT, admin)

    updated = await client_service.assign_consultant(session, client, consultant, admin)

    assert updated.consultant_id == consultant.id
    assert updated.status == ClientStatus.CAREER_CONSULTATION


async def test_update_client_fields_only_logs_actual_changes(session):
    admin = await _make_staff(session, "admin@ican.dev", AdminRole.ADMIN)
    client = await client_service.create_client(
        session, source_channel=SourceChannel.PHONE, actor=admin, city="Харків"
    )

    changed = await client_service.update_client_fields(
        session, client, {"city": "Харків", "phone": "+380501234567"}, admin
    )

    assert changed == ["phone"]
    assert client.phone == "+380501234567"


async def test_try_complete_screening_blocks_when_fields_missing(session):
    admin = await _make_staff(session, "admin@ican.dev", AdminRole.ADMIN)
    client = await client_service.create_client(session, source_channel=SourceChannel.PHONE, actor=admin)

    check = await client_service.try_complete_screening(session, client, admin)

    assert check.ready is False
    assert client.status == ClientStatus.NEW  # unchanged
