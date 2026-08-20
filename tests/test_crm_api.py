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


async def test_full_client_workflow_end_to_end(client, session_factory):
    admin_id = await _create_staff(session_factory, "admin@ican.dev", AdminRole.ADMIN)
    consultant_id = await _create_staff(session_factory, "consultant@ican.dev", AdminRole.CAREER_CONSULTANT)
    admin_headers = await _login(client, "admin@ican.dev")

    # Create a phone-sourced client
    resp = await client.post(
        "/crm/clients",
        json={"first_name": "Марія", "phone": "+380671112233", "city": "Одеса", "country": "Україна"},
        headers=admin_headers,
    )
    assert resp.status_code == 201
    client_id = resp.json()["id"]
    assert resp.json()["status"] == "new"

    # Fill in profile fields required for screening completion
    resp = await client.patch(
        f"/crm/clients/{client_id}/profile",
        json={
            "currently_employed": False,
            "primary_target": "продавець-консультант",
            "min_salary": "18000",
            "employment_types": ["full-time"],
            "work_formats": ["office"],
            "schedules": ["5/2"],
            "constraints_comment": "немає обмежень",
        },
        headers=admin_headers,
    )
    assert resp.status_code == 200

    resp = await client.post(f"/crm/clients/{client_id}/skills", json={"skill_name": "Продажі"}, headers=admin_headers)
    assert resp.status_code == 200

    # Screening not complete yet (missing salary currency isn't checked at screening stage — but let's verify readiness gate works)
    resp = await client.post(f"/crm/clients/{client_id}/screening/complete", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ready"] is True
    assert body["status"] == "waiting_consultant"

    # Assign a career consultant — should advance status to career_consultation
    resp = await client.post(
        f"/crm/clients/{client_id}/assign-consultant", json={"staff_id": consultant_id}, headers=admin_headers
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "career_consultation"
    assert resp.json()["consultant_id"] == consultant_id

    # Consultant fills remaining critical fields for READY_FOR_MATCHING
    consultant_headers = await _login(client, "consultant@ican.dev")
    await client.patch(
        f"/crm/clients/{client_id}/profile",
        json={"salary_currency": "грн", "work_cities": ["Одеса"]},
        headers=consultant_headers,
    )
    await client.post(f"/crm/clients/{client_id}/work-experience", json={"position": "Продавець"}, headers=consultant_headers)
    await client.post(f"/crm/clients/{client_id}/languages", json={"language": "українська"}, headers=consultant_headers)

    resp = await client.post(
        f"/crm/clients/{client_id}/career-consultation/complete",
        json={"conclusion": "Готова до підбору вакансій продавця-консультанта"},
        headers=consultant_headers,
    )
    assert resp.status_code == 200

    resp = await client.post(f"/crm/clients/{client_id}/ready-for-matching", headers=consultant_headers)
    assert resp.status_code == 200
    assert resp.json()["ready"] is True
    assert resp.json()["status"] == "ready_for_matching"

    # Timeline recorded the whole story
    resp = await client.get(f"/crm/clients/{client_id}/timeline", headers=admin_headers)
    event_types = {e["event_type"] for e in resp.json()}
    assert {"created", "screening_completed", "assigned", "consultation_completed", "ready_for_matching"} <= event_types


async def test_career_consultant_cannot_see_unassigned_client(client, session_factory):
    admin_id = await _create_staff(session_factory, "admin2@ican.dev", AdminRole.ADMIN)
    consultant_id = await _create_staff(session_factory, "c2@ican.dev", AdminRole.CAREER_CONSULTANT)
    admin_headers = await _login(client, "admin2@ican.dev")
    consultant_headers = await _login(client, "c2@ican.dev")

    resp = await client.post("/crm/clients", json={"first_name": "Хтось Інший"}, headers=admin_headers)
    other_client_id = resp.json()["id"]

    resp = await client.get(f"/crm/clients/{other_client_id}", headers=consultant_headers)
    assert resp.status_code == 404

    resp = await client.get("/crm/clients", headers=consultant_headers)
    assert resp.json()["total"] == 0


async def test_manager_cannot_assign_consultant(client, session_factory):
    await _create_staff(session_factory, "manager@ican.dev", AdminRole.MANAGER)
    admin_id = await _create_staff(session_factory, "admin3@ican.dev", AdminRole.ADMIN)
    consultant_id = await _create_staff(session_factory, "c3@ican.dev", AdminRole.CAREER_CONSULTANT)

    manager_headers = await _login(client, "manager@ican.dev")
    admin_headers = await _login(client, "admin3@ican.dev")

    resp = await client.post("/crm/clients", json={"first_name": "Клієнт"}, headers=admin_headers)
    client_id = resp.json()["id"]

    resp = await client.post(
        f"/crm/clients/{client_id}/assign-consultant", json={"staff_id": consultant_id}, headers=manager_headers
    )
    assert resp.status_code == 403


async def test_manager_cannot_create_career_consultant_account(client, session_factory):
    await _create_staff(session_factory, "manager2@ican.dev", AdminRole.MANAGER)
    manager_headers = await _login(client, "manager2@ican.dev")

    resp = await client.post(
        "/crm/users",
        json={"email": "new@ican.dev", "password": "pw12345", "role": "career_consultant"},
        headers=manager_headers,
    )
    assert resp.status_code == 403


async def test_file_upload_and_download_roundtrip(client, session_factory, tmp_path, monkeypatch):
    from app.services.crm import storage as storage_module

    monkeypatch.setattr(storage_module, "_default_storage", storage_module.LocalFileStorage(tmp_path))

    admin_id = await _create_staff(session_factory, "admin4@ican.dev", AdminRole.ADMIN)
    admin_headers = await _login(client, "admin4@ican.dev")

    resp = await client.post("/crm/clients", json={"first_name": "Тест"}, headers=admin_headers)
    client_id = resp.json()["id"]

    files = {"upload": ("cv.txt", b"hello resume", "text/plain")}
    resp = await client.post(
        f"/crm/clients/{client_id}/files",
        data={"file_type": "cv"},
        files=files,
        headers=admin_headers,
    )
    assert resp.status_code == 200
    file_id = resp.json()["id"]

    resp = await client.get(f"/crm/clients/{client_id}/files/{file_id}/download", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.content == b"hello resume"

    resp = await client.get(f"/crm/clients/{client_id}/files", headers=admin_headers)
    assert len(resp.json()) == 1


async def test_task_lifecycle(client, session_factory):
    admin_id = await _create_staff(session_factory, "admin5@ican.dev", AdminRole.ADMIN)
    admin_headers = await _login(client, "admin5@ican.dev")

    resp = await client.post("/crm/clients", json={"first_name": "Тест"}, headers=admin_headers)
    client_id = resp.json()["id"]

    resp = await client.post(
        f"/crm/clients/{client_id}/tasks", json={"task_type": "call", "note": "Передзвонити"}, headers=admin_headers
    )
    assert resp.status_code == 200
    task_id = resp.json()["id"]
    assert resp.json()["status"] == "pending"

    resp = await client.post(f"/crm/tasks/{task_id}/complete", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "done"
