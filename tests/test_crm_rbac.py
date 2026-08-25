"""Regression baseline for Issue #12's RBAC checklist items:

- "запрет consultant на доступ к чужому клиенту через прямой API request" —
  covered here for the mutating (PATCH/DELETE) endpoints specifically. GET
  was already covered in test_crm_api.py::test_career_consultant_cannot_see_unassigned_client;
  write endpoints route through the same `_get_client_or_404` helper but are
  verified independently since a regression could plausibly land in only one
  HTTP verb.
- "CRUD критичных клиентских данных" — delete is the one CRUD operation with
  no prior coverage (create/read/update were already exercised elsewhere).
"""

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api.main import app
from app.core.security import hash_password
from app.db.models import AdminRole, AdminUser
from app.db.session import get_session


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


async def _create_staff(session_factory, email, role, password="pw"):
    async with session_factory() as session:
        staff = AdminUser(email=email, password_hash=hash_password(password), role=role, full_name=email.split("@")[0])
        session.add(staff)
        await session.commit()
        await session.refresh(staff)
        return staff.id


async def _login(client, email, password="pw"):
    resp = await client.post("/admin/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _make_unassigned_client_with_data(client, admin_headers):
    """Creates a client (owned by no consultant) with one row in each
    repeatable block, so delete-RBAC can be exercised against real ids."""
    resp = await client.post("/crm/clients", json={"first_name": "Чужий Клієнт"}, headers=admin_headers)
    client_id = resp.json()["id"]

    resp = await client.post(f"/crm/clients/{client_id}/skills", json={"skill_name": "Excel"}, headers=admin_headers)
    skill_id = resp.json()["id"]

    resp = await client.post(f"/crm/clients/{client_id}/languages", json={"language": "англійська"}, headers=admin_headers)
    lang_id = resp.json()["id"]

    resp = await client.post(
        f"/crm/clients/{client_id}/work-experience", json={"position": "Оператор"}, headers=admin_headers
    )
    we_id = resp.json()["id"]

    return client_id, skill_id, lang_id, we_id


async def test_consultant_cannot_patch_unassigned_client(client, session_factory):
    await _create_staff(session_factory, "c1@rbac.dev", AdminRole.CAREER_CONSULTANT)
    admin_headers = await _login(client, await _bootstrap_admin(session_factory, "a1@rbac.dev"))
    consultant_headers = await _login(client, "c1@rbac.dev")

    resp = await client.post("/crm/clients", json={"first_name": "Хтось"}, headers=admin_headers)
    client_id = resp.json()["id"]

    resp = await client.patch(f"/crm/clients/{client_id}", json={"first_name": "Змінено"}, headers=consultant_headers)
    assert resp.status_code == 404


async def test_consultant_cannot_patch_unassigned_client_profile(client, session_factory):
    await _create_staff(session_factory, "c2@rbac.dev", AdminRole.CAREER_CONSULTANT)
    admin_headers = await _login(client, await _bootstrap_admin(session_factory, "a2@rbac.dev"))
    consultant_headers = await _login(client, "c2@rbac.dev")

    resp = await client.post("/crm/clients", json={"first_name": "Хтось"}, headers=admin_headers)
    client_id = resp.json()["id"]

    resp = await client.patch(
        f"/crm/clients/{client_id}/profile", json={"primary_target": "продавець"}, headers=consultant_headers
    )
    assert resp.status_code == 404


async def test_consultant_cannot_delete_skill_or_language_or_work_experience_of_unassigned_client(client, session_factory):
    await _create_staff(session_factory, "c3@rbac.dev", AdminRole.CAREER_CONSULTANT)
    admin_headers = await _login(client, await _bootstrap_admin(session_factory, "a3@rbac.dev"))
    consultant_headers = await _login(client, "c3@rbac.dev")

    client_id, skill_id, lang_id, we_id = await _make_unassigned_client_with_data(client, admin_headers)

    resp = await client.delete(f"/crm/clients/{client_id}/skills/{skill_id}", headers=consultant_headers)
    assert resp.status_code == 404

    resp = await client.delete(f"/crm/clients/{client_id}/languages/{lang_id}", headers=consultant_headers)
    assert resp.status_code == 404

    resp = await client.delete(f"/crm/clients/{client_id}/work-experience/{we_id}", headers=consultant_headers)
    assert resp.status_code == 404

    # Prove the denial was real, not a side effect of a bad test — the rows
    # must still exist for the owning admin.
    resp = await client.get(f"/crm/clients/{client_id}", headers=admin_headers)
    body = resp.json()
    assert len(body["skills"]) == 1
    assert len(body["languages"]) == 1
    assert len(body["work_experiences"]) == 1


async def test_consultant_cannot_delete_file_of_unassigned_client(client, session_factory, tmp_path, monkeypatch):
    from app.services.crm import storage as storage_module

    monkeypatch.setattr(storage_module, "_default_storage", storage_module.LocalFileStorage(tmp_path))

    await _create_staff(session_factory, "c4@rbac.dev", AdminRole.CAREER_CONSULTANT)
    admin_headers = await _login(client, await _bootstrap_admin(session_factory, "a4@rbac.dev"))
    consultant_headers = await _login(client, "c4@rbac.dev")

    resp = await client.post("/crm/clients", json={"first_name": "Хтось"}, headers=admin_headers)
    client_id = resp.json()["id"]

    files = {"upload": ("cv.txt", b"hello", "text/plain")}
    resp = await client.post(
        f"/crm/clients/{client_id}/files", data={"file_type": "cv"}, files=files, headers=admin_headers
    )
    file_id = resp.json()["id"]

    resp = await client.delete(f"/crm/clients/{client_id}/files/{file_id}", headers=consultant_headers)
    assert resp.status_code == 404

    resp = await client.get(f"/crm/clients/{client_id}/files", headers=admin_headers)
    assert len(resp.json()) == 1


async def test_assigned_consultant_can_delete_own_client_skill(client, session_factory):
    consultant_id = await _create_staff(session_factory, "c5@rbac.dev", AdminRole.CAREER_CONSULTANT)
    admin_headers = await _login(client, await _bootstrap_admin(session_factory, "a5@rbac.dev"))
    consultant_headers = await _login(client, "c5@rbac.dev")

    resp = await client.post("/crm/clients", json={"first_name": "Мій Клієнт"}, headers=admin_headers)
    client_id = resp.json()["id"]
    await client.post(
        f"/crm/clients/{client_id}/assign-consultant", json={"staff_id": consultant_id}, headers=admin_headers
    )

    resp = await client.post(f"/crm/clients/{client_id}/skills", json={"skill_name": "Python"}, headers=admin_headers)
    skill_id = resp.json()["id"]

    resp = await client.delete(f"/crm/clients/{client_id}/skills/{skill_id}", headers=consultant_headers)
    assert resp.status_code == 204

    resp = await client.get(f"/crm/clients/{client_id}", headers=admin_headers)
    assert resp.json()["skills"] == []


async def _bootstrap_admin(session_factory, email: str) -> str:
    await _create_staff(session_factory, email, AdminRole.ADMIN)
    return email
