import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api.main import app
from app.db.session import get_session
from app.services import profile_service


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


async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_get_profile_404_for_unknown_user(client):
    resp = await client.get("/users/999/profile")
    assert resp.status_code == 404


async def test_get_profile_returns_saved_data(client, session_factory):
    async with session_factory() as session:
        user = await profile_service.get_or_create_user(session, telegram_id=777)

    resp = await client.get(f"/users/777/profile")
    assert resp.status_code == 200
    body = resp.json()
    assert body["user_id"] == user.id
    assert body["confirmed"] is False
