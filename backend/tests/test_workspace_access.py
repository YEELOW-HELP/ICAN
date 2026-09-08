"""Real-token acceptance tests for staff roles and Person KB object access."""
import uuid
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api.main import app
from app.core.security import create_access_token, hash_password
from app.db.models import AdminRole, AdminUser
from app.db.session import get_session


@pytest_asyncio.fixture
async def workspace(session_factory):
    async def override():
        async with session_factory() as session:
            yield session
    app.dependency_overrides[get_session] = override
    staff = {}
    async with session_factory() as session:
        password_hash = hash_password("test-password-long")
        for name, role in [("owner", AdminRole.SUPER_ADMIN), ("admin", AdminRole.ADMIN),
                           ("a", AdminRole.MANAGER), ("b", AdminRole.MANAGER)]:
            account = AdminUser(email=f"{name}@example.com", password_hash=password_hash, role=role, is_active=True)
            session.add(account)
            await session.flush()
            staff[name] = (account.id, {"Authorization": "Bearer " + create_access_token(account.id, role.value)})
        await session.commit()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client, staff
    finally:
        app.dependency_overrides.clear()


async def create_person(client, headers, name):
    response = await client.post("/v1/mnp/admin/persons", headers=headers, json={"first_name": name})
    assert response.status_code == 201, response.text
    return response.json()["id"]


@pytest.mark.asyncio
async def test_manager_scope_grant_revoke_save_reopen(workspace):
    client, staff = workspace
    a_id, a = staff["a"]
    b_id, b = staff["b"]
    _, admin = staff["admin"]
    first = await create_person(client, a, "Клієнт А")
    second = await create_person(client, b, "Клієнт Б")
    for name in ("owner", "admin"):
        assert len((await client.get("/v1/mnp/admin/persons", headers=staff[name][1])).json()) == 2
    assert [p["id"] for p in (await client.get("/v1/mnp/admin/persons", headers=a)).json()] == [first]
    assert (await client.get(f"/v1/mnp/admin/persons/{second}", headers=a)).status_code == 404
    assert (await client.patch(f"/v1/mnp/admin/persons/{second}", headers=a, json={"city":"Втручання"})).status_code == 404
    assert (await client.put(f"/v1/mnp/admin/persons/{second}/access/{a_id}", headers=a)).status_code == 403
    assert (await client.put(f"/v1/mnp/admin/persons/{second}/access/{a_id}", headers=admin)).status_code == 204
    assert (await client.patch(f"/v1/mnp/admin/persons/{second}", headers=a, json={"city":"Харків"})).status_code == 200
    reopened = await client.get(f"/v1/mnp/admin/persons/{second}", headers=b)
    assert reopened.json()["core"]["city"] == "Харків"
    assert (await client.delete(f"/v1/mnp/admin/persons/{second}/access/{a_id}", headers=admin)).status_code == 204
    assert (await client.get(f"/v1/mnp/admin/persons/{second}", headers=a)).status_code == 404
    assert (await client.delete(f"/v1/mnp/admin/persons/{second}/access/{b_id}", headers=admin)).status_code == 409


@pytest.mark.asyncio
async def test_every_person_mutation_is_scoped(workspace):
    client, staff = workspace
    foreign = await create_person(client, staff["b"][1], "Приватний")
    own = await create_person(client, staff["a"][1], "Власний")
    a = staff["a"][1]
    base = f"/v1/mnp/admin/persons/{foreign}"
    for action in ("activate", "archive", "unarchive"):
        assert (await client.post(f"{base}/{action}", headers=a)).status_code == 404
    for block in ("educations", "experiences", "credentials", "activities", "languages", "skills"):
        assert (await client.post(f"{base}/{block}", headers=a, json={})).status_code == 404
        assert (await client.patch(f"{base}/{block}/{uuid.uuid4()}", headers=a, json={})).status_code == 404
        assert (await client.delete(f"{base}/{block}/{uuid.uuid4()}", headers=a)).status_code == 404
    response = await client.post(f"/v1/mnp/admin/persons/{foreign}/languages", headers=staff["b"][1], json={"language":"Українська"})
    row_id = response.json()["languages"][0]["id"]
    assert (await client.patch(f"/v1/mnp/admin/persons/{own}/languages/{row_id}", headers=a, json={"language":"English"})).status_code in (400, 404)


@pytest.mark.asyncio
async def test_staff_hierarchy_and_immediate_deactivation(workspace):
    client, staff = workspace
    payload = {"email":"new@example.com", "full_name":"Працівник", "password":"test-password-long", "role":"super_admin"}
    assert (await client.post("/v1/mnp/admin/staff", headers=staff["admin"][1], json=payload)).status_code == 403
    assert (await client.post("/crm/users", headers=staff["admin"][1], json=payload)).status_code == 403
    assert (await client.get("/v1/mnp/admin/staff", headers=staff["a"][1])).status_code == 403
    payload["role"] = "manager"
    payload["password"] = "Test123"
    assert (await client.post("/v1/mnp/admin/staff", headers=staff["admin"][1], json=payload)).status_code == 422
    payload["password"] = "Test1234"
    assert (await client.post("/v1/mnp/admin/staff", headers=staff["admin"][1], json=payload)).status_code == 201
    assert (await client.post("/v1/mnp/admin/staff", headers=staff["admin"][1], json=payload)).status_code == 409
    response = await client.patch(f"/v1/mnp/admin/staff/{staff['a'][0]}", headers=staff["admin"][1], json={"is_active":False})
    assert response.status_code == 200
    assert (await client.get("/v1/mnp/admin/persons", headers=staff["a"][1])).status_code == 401
    assert (await client.post("/admin/auth/login", json={"email":"a@example.com", "password":"test-password-long"})).status_code == 401
    assert (await client.patch(f"/v1/mnp/admin/staff/{staff['owner'][0]}", headers=staff["owner"][1], json={"is_active":False})).status_code == 409


@pytest.mark.asyncio
async def test_current_role_not_claim_controls_access(workspace):
    client, staff = workspace
    assert (await client.get("/v1/mnp/admin/persons")).status_code == 401
    assert (await client.get("/v1/mnp/admin/careers", headers=staff["a"][1])).status_code == 403
    assert (await client.get("/admin/users", headers=staff["a"][1])).status_code == 403
    downgraded = await client.patch(f"/v1/mnp/admin/staff/{staff['admin'][0]}", headers=staff["owner"][1], json={"role":"manager"})
    assert downgraded.status_code == 200
    assert (await client.get("/v1/mnp/admin/staff", headers=staff["admin"][1])).status_code == 403
    assert (await client.get("/v1/mnp/admin/me", headers=staff["admin"][1])).json()["role"] == "manager"
