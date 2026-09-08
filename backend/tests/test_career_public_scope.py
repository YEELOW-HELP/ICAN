"""NAPRIAM Visual Architecture Addendum §2 / §24 / §29 — the three Career KB
scopes must never be confused:

* PUBLIC catalog / detail  -> ACTIVE careers only
* ADMIN catalog            -> every career, every status
* internal Matching dev    -> may use every career (status is NOT a filter
                              baked into the model) — asserted structurally

`Career.status` is a *publication* flag. It must not silently leak a DRAFT
onto the public site, and it must not be repurposed as a hard gate that
would stop an internal 150-career Matching pass later.
"""

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api.main import app
from app.core.security import create_access_token, hash_password
from app.db.models import AdminRole, AdminUser
from app.db.models_career_kb_mnp import CareerLifecycleStatus, MnpCareer
from app.db.session import get_session
from app.services.career_kb_mnp.seed_alpha import seed_alpha_career_kb
from sqlalchemy import select


@pytest_asyncio.fixture
async def client(session_factory):
    async def override_get_session():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = override_get_session
    async with session_factory() as seed_session:
        await seed_alpha_career_kb(seed_session)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def _admin_headers(session_factory) -> dict:
    async with session_factory() as session:
        admin = AdminUser(email="scope_admin@ican.dev", password_hash=hash_password("pw"),
                          role=AdminRole.ADMIN, full_name="Scope Admin")
        session.add(admin)
        await session.commit()
        await session.refresh(admin)
        token = create_access_token(admin.id, admin.role.value)
    return {"Authorization": f"Bearer {token}"}


async def _make_draft(client, headers) -> str:
    resp = await client.post(
        "/v1/mnp/admin/careers",
        json={"career_code": "scope_draft_career", "name_uk": "Чернетка-професія",
              "name_en": "Draft Career", "category_uk": "Тест", "short_description_uk": "d"},
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def test_public_catalog_is_active_only(client, session_factory):
    headers = await _admin_headers(session_factory)
    await _make_draft(client, headers)

    async with session_factory() as s:
        active = (await s.execute(
            select(MnpCareer).where(MnpCareer.status == CareerLifecycleStatus.ACTIVE))).scalars().all()
        active_codes = {c.code for c in active}

    public = (await client.get("/v1/mnp/careers")).json()
    public_codes = {c["code"] for c in public}

    assert public_codes == active_codes                # exactly the ACTIVE set
    assert "scope_draft_career" not in public_codes    # DRAFT never leaks
    assert len(public_codes) == 5                       # the 5 Alpha ACTIVE careers


async def test_public_detail_404s_for_draft(client, session_factory):
    headers = await _admin_headers(session_factory)
    draft_id = await _make_draft(client, headers)

    resp = await client.get(f"/v1/mnp/careers/{draft_id}")
    assert resp.status_code == 404  # not publicly presented as a Career page


async def test_admin_catalog_shows_every_status(client, session_factory):
    headers = await _admin_headers(session_factory)
    draft_id = await _make_draft(client, headers)

    admin_rows = (await client.get("/v1/mnp/admin/careers", headers=headers)).json()
    by_id = {c["id"]: c for c in admin_rows}

    assert draft_id in by_id
    assert by_id[draft_id]["status"] == "draft"
    # the ACTIVE ones are here too — admin sees the union, not a filtered view
    assert sum(1 for c in admin_rows if c["status"] == "active") == 5
    assert len(admin_rows) == 6  # 5 ACTIVE + 1 DRAFT


async def test_status_is_not_a_hard_model_filter(client, session_factory):
    """Internal Matching development must be able to reach every career. A
    plain unfiltered query for all careers returns DRAFT rows alongside
    ACTIVE — status is a publication flag, not a query gate."""
    headers = await _admin_headers(session_factory)
    await _make_draft(client, headers)

    async with session_factory() as s:
        every = (await s.execute(select(MnpCareer))).scalars().all()
        statuses = {c.status for c in every}

    assert CareerLifecycleStatus.DRAFT in statuses
    assert CareerLifecycleStatus.ACTIVE in statuses
    assert len(every) == 6  # 5 ACTIVE + 1 DRAFT, all reachable for internal dev
