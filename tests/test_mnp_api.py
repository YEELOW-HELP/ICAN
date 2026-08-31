"""MNP V1 BLOCK D -- full HTTP API end-to-end test (real ASGI transport,
not just service-layer calls) -- proves the actual wiring in app/api/main.py
and app/api/mnp.py works, not just the underlying services."""

import io

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api.main import app
from app.core.security import create_access_token, hash_password
from app.db.models import AdminRole, AdminUser
from app.db.session import get_session
from app.services.career_kb_mnp.seed_alpha import seed_alpha_career_kb


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
        admin = AdminUser(email="mnp_admin@ican.dev", password_hash=hash_password("pw"), role=AdminRole.ADMIN, full_name="MNP Admin")
        session.add(admin)
        await session.commit()
        await session.refresh(admin)
        token = create_access_token(admin.id, admin.role.value)
    return {"Authorization": f"Bearer {token}"}


async def test_full_no_cv_flow_end_to_end(client):
    session_resp = await client.post("/v1/mnp/session")
    assert session_resp.status_code == 200
    user_id = session_resp.json()["user_id"]
    headers = {"X-Mnp-User-Id": user_id}

    capital_resp = await client.post(
        "/v1/mnp/questionnaire/career-capital",
        json={
            "current_role": "Менеджер з продажу", "years_of_experience": 3,
            "skill_phrases": ["Переговори", "Робота з запереченнями", "Продажі B2B", "CRM", "Активне слухання"],
        },
        headers=headers,
    )
    assert capital_resp.status_code == 200

    intent_resp = await client.post(
        "/v1/mnp/questionnaire/career-intent",
        json={"goal_type": "change_career", "target_income": 30000},
        headers=headers,
    )
    assert intent_resp.status_code == 200

    missing_resp = await client.get("/v1/mnp/questionnaire/missing", headers=headers)
    assert missing_resp.status_code == 200
    assert "current_role" not in missing_resp.json()["career_capital"]

    match_resp = await client.post("/v1/mnp/match-runs", json={"ranking_mode": "best_for_me"}, headers=headers)
    assert match_resp.status_code == 200
    match_run_id = match_resp.json()["match_run_id"]

    careers_resp = await client.get(f"/v1/mnp/match-runs/{match_run_id}/careers", headers=headers)
    assert careers_resp.status_code == 200
    ranked = careers_resp.json()["ranked_top10"]
    assert len(ranked) == 5
    assert ranked[0]["career_code"] == "sales_manager"

    career_match_id = ranked[0]["career_match_id"]
    detail_resp = await client.get(f"/v1/mnp/career-matches/{career_match_id}", headers=headers)
    assert detail_resp.status_code == 200
    assert detail_resp.json()["career_code"] == "sales_manager"

    route_resp = await client.get(f"/v1/mnp/career-matches/{career_match_id}/route", headers=headers)
    assert route_resp.status_code == 200
    assert len(route_resp.json()["steps"]) > 0

    card_resp = await client.get("/v1/mnp/career-card", headers=headers)
    assert card_resp.status_code == 200
    assert len(card_resp.json()["experiences"]) == 1


async def test_edit_career_card_and_recalculate_end_to_end(client):
    """MNP_DEFINITION_OF_DONE_V1 / DoD end-to-end chain: ... вернуться в
    кабінет -> відредагувати Career Card -> перерахувати результат. V1's
    "edit" mechanism is re-submitting the questionnaire (idempotent
    upsert on Career Intent, additive on Career Capital) -- granular
    per-field editing is a disclosed POST_V1_CANDIDATE, not built here."""

    session_resp = await client.post("/v1/mnp/session")
    headers = {"X-Mnp-User-Id": session_resp.json()["user_id"]}

    await client.post("/v1/mnp/questionnaire/career-capital", json={"current_role": "Бухгалтер", "skill_phrases": ["Excel"]}, headers=headers)
    first_match = await client.post("/v1/mnp/match-runs", json={}, headers=headers)
    first_match_run_id = first_match.json()["match_run_id"]

    card_after_first = await client.get("/v1/mnp/career-card", headers=headers)
    version_after_first = card_after_first.json()["version"]

    # Edit: add more Career Capital (a second, distinct experience entry).
    await client.post(
        "/v1/mnp/questionnaire/career-capital",
        json={"skill_phrases": ["Переговори", "CRM"]},
        headers=headers,
    )
    second_match = await client.post("/v1/mnp/match-runs", json={}, headers=headers)
    second_match_run_id = second_match.json()["match_run_id"]

    card_after_second = await client.get("/v1/mnp/career-card", headers=headers)
    version_after_second = card_after_second.json()["version"]

    assert second_match_run_id != first_match_run_id  # a genuinely new, independent MatchRun
    assert version_after_second > version_after_first  # the recalculation snapshot really bumped the card version
    assert len(card_after_second.json()["person_skills"]) == 3  # Excel + Переговори + CRM, additive not overwritten

    # Both match runs remain independently readable -- editing never
    # deletes history.
    old_results = await client.get(f"/v1/mnp/match-runs/{first_match_run_id}/careers", headers=headers)
    assert old_results.status_code == 200


async def test_resume_upload_flow_end_to_end(client):
    session_resp = await client.post("/v1/mnp/session")
    user_id = session_resp.json()["user_id"]
    headers = {"X-Mnp-User-Id": user_id}

    cv_bytes = (
        "Досвід роботи\n01.2020 - теперішній час\nМенеджер з продажу\n"
        "Веде переговори з клієнтами\n\nНавички\nПереговори, CRM\n"
    ).encode("utf-8")
    upload_resp = await client.post(
        "/v1/mnp/documents", headers=headers, files={"file": ("cv.txt", io.BytesIO(cv_bytes), "text/plain")},
    )
    assert upload_resp.status_code == 200
    assert upload_resp.json()["extraction_status"] == "extracted"

    match_resp = await client.post("/v1/mnp/match-runs", json={}, headers=headers)
    assert match_resp.status_code == 200


async def test_unauthenticated_request_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/v1/mnp/career-card")
        # no session token and no X-Mnp-User-Id -> 401 (get_current_mnp_user
        # now accepts a Bearer session token, with X-Mnp-User-Id as the
        # legacy fallback; neither present here)
        assert resp.status_code == 401


async def test_cannot_access_another_users_match_run(client):
    session_a = (await client.post("/v1/mnp/session")).json()["user_id"]
    session_b = (await client.post("/v1/mnp/session")).json()["user_id"]

    await client.post("/v1/mnp/questionnaire/career-capital", json={"current_role": "Менеджер"}, headers={"X-Mnp-User-Id": session_a})
    match_resp = await client.post("/v1/mnp/match-runs", json={}, headers={"X-Mnp-User-Id": session_a})
    match_run_id = match_resp.json()["match_run_id"]

    forbidden_resp = await client.get(f"/v1/mnp/match-runs/{match_run_id}/careers", headers={"X-Mnp-User-Id": session_b})
    assert forbidden_resp.status_code == 403


async def test_careers_catalog_public_endpoint(client):
    resp = await client.get("/v1/mnp/careers")
    assert resp.status_code == 200
    codes = {c["code"] for c in resp.json()}
    assert "sales_manager" in codes


async def test_upload_rate_limit_enforced(client):
    session_resp = await client.post("/v1/mnp/session")
    headers = {"X-Mnp-User-Id": session_resp.json()["user_id"]}
    cv_bytes = b"Navycku\nExcel\n"

    responses = []
    for _ in range(6):
        resp = await client.post("/v1/mnp/documents", headers=headers, files={"file": ("cv.txt", io.BytesIO(cv_bytes), "text/plain")})
        responses.append(resp.status_code)
    assert 429 in responses


async def test_admin_can_create_career_draft(client, session_factory):
    """Smoke test of the Career KB Editor create endpoint (full CRUD /
    publish / archive coverage lives in test_mnp_career_kb_editor.py)."""
    headers = await _admin_headers(session_factory)
    create_resp = await client.post(
        "/v1/mnp/admin/careers",
        json={
            "career_code": "test_new_career", "name_uk": "Тест", "name_en": "Test",
            "category_uk": "Продажі", "short_description_uk": "desc",
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    body = create_resp.json()
    assert body["core"]["status"] == "draft" and body["core"]["career_code"] == "test_new_career"

    # a fresh DRAFT is not publishable yet and is not in the public catalog
    ready = await client.get(f"/v1/mnp/admin/careers/{body['id']}/publish-readiness", headers=headers)
    assert ready.json()["ready"] is False
    assert "test_new_career" not in {c["code"] for c in (await client.get("/v1/mnp/careers")).json()}


async def test_admin_endpoint_requires_admin_auth(client):
    resp = await client.post(
        "/v1/mnp/admin/careers",
        json={"career_code": "x", "name_uk": "x", "category_uk": "x"},
    )
    assert resp.status_code == 401
    assert (await client.get("/v1/mnp/admin/careers")).status_code == 401
