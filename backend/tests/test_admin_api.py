import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api.main import app
from app.core.security import hash_password
from app.db.models import AdminRole, AdminUser
from app.db.session import get_session
from app.services import profile_service
from app.schemas.profile import ProfileDraft


@pytest_asyncio.fixture
async def client(session_factory):
    async def override_get_session():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def _create_admin(session_factory, email="admin@ican.dev", password="hunter2", role=AdminRole.ADMIN):
    async with session_factory() as session:
        admin = AdminUser(email=email, password_hash=hash_password(password), role=role)
        session.add(admin)
        await session.commit()


async def test_login_succeeds_with_correct_credentials(client, session_factory):
    await _create_admin(session_factory, password="hunter2")

    resp = await client.post("/admin/auth/login", json={"email": "admin@ican.dev", "password": "hunter2"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["role"] == "admin"
    assert body["access_token"]


async def test_login_rejects_wrong_password(client, session_factory):
    await _create_admin(session_factory, password="hunter2")

    resp = await client.post("/admin/auth/login", json={"email": "admin@ican.dev", "password": "wrong"})

    assert resp.status_code == 401


async def test_users_list_requires_authentication(client):
    resp = await client.get("/admin/users")
    assert resp.status_code == 401


async def test_users_list_returns_data_with_valid_token(client, session_factory):
    await _create_admin(session_factory, password="hunter2")
    async with session_factory() as session:
        await profile_service.get_or_create_user(session, telegram_id=555)

    login = await client.post("/admin/auth/login", json={"email": "admin@ican.dev", "password": "hunter2"})
    token = login.json()["access_token"]

    resp = await client.get("/admin/users", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["telegram_id"] == 555


async def test_patch_status_blocked_field_requires_admin_role(client, session_factory):
    await _create_admin(session_factory, email="manager@ican.dev", password="pw", role=AdminRole.MANAGER)
    async with session_factory() as session:
        user = await profile_service.get_or_create_user(session, telegram_id=777)
        user_id = user.id

    login = await client.post("/admin/auth/login", json={"email": "manager@ican.dev", "password": "pw"})
    token = login.json()["access_token"]

    resp = await client.patch(
        f"/admin/users/{user_id}/status",
        json={"is_blocked": True},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 403


async def test_patch_profile_updates_fields(client, session_factory):
    await _create_admin(session_factory, password="hunter2")
    async with session_factory() as session:
        user = await profile_service.get_or_create_user(session, telegram_id=888)
        await profile_service.apply_profile_draft(session, user, ProfileDraft(city="Одеса"))
        user_id = user.id

    login = await client.post("/admin/auth/login", json={"email": "admin@ican.dev", "password": "hunter2"})
    token = login.json()["access_token"]

    resp = await client.patch(
        f"/admin/users/{user_id}/profile",
        json={"city": "Львів"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200
    assert resp.json()["profile"]["city"] == "Львів"
