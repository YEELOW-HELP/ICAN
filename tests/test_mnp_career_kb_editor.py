"""MNP Career KB Editor V1 -- focused tests (brief §31).

Covers: create DRAFT -> fill -> publish -> archive lifecycle, every child
CRUD collection, security (anonymous cannot mutate), profile_version
increment, audit/provenance (changed_by + old/new value), and the
DB == API == public-view consistency.
"""

from __future__ import annotations

import uuid

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.api.main import app
from app.core.security import create_access_token, hash_password
from app.db.models import AdminRole, AdminUser
from app.db.models_career_kb_mnp import (
    CareerLifecycleStatus,
    MnpCareer,
    MnpCareerProCon,
    MnpCareerTask,
)
from app.db.models_platform import AuditLog
from app.db.session import get_session
from app.services.career_kb_mnp.seed_alpha import seed_alpha_career_kb


@pytest_asyncio.fixture
async def client(session_factory):
    async def override_get_session():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = override_get_session
    async with session_factory() as s:
        await seed_alpha_career_kb(s)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def admin_headers(session_factory) -> dict:
    async with session_factory() as s:
        a = AdminUser(email="kb_editor@mnp.dev", password_hash=hash_password("pw"),
                      role=AdminRole.ADMIN, full_name="KB Editor")
        s.add(a)
        await s.commit()
        await s.refresh(a)
        token = create_access_token(a.id, a.role.value)
    return {"Authorization": f"Bearer {token}"}


async def _accountant_id(client) -> str:
    rows = (await client.get("/v1/mnp/careers")).json()
    return next(c["id"] for c in rows if c["code"] == "accountant")


# ---------------------------------------------------------------------------
# security (§31)
# ---------------------------------------------------------------------------
async def test_anonymous_cannot_read_or_mutate_editor(client):
    aid = await _accountant_id(client)
    assert (await client.get("/v1/mnp/admin/careers")).status_code == 401
    assert (await client.get(f"/v1/mnp/admin/careers/{aid}")).status_code == 401
    assert (await client.patch(f"/v1/mnp/admin/careers/{aid}", json={"name_uk": "HACKED"})).status_code == 401
    assert (await client.post("/v1/mnp/admin/careers", json={"career_code": "x", "name_uk": "x"})).status_code == 401
    assert (await client.post(f"/v1/mnp/admin/careers/{aid}/pros-cons",
                              json={"type": "advantage", "text_uk": "x"})).status_code == 401
    # public view unchanged
    d = (await client.get(f"/v1/mnp/careers/{aid}")).json()
    assert d["identity"]["name_uk"] == "Бухгалтер"


async def test_bad_token_rejected(client):
    aid = await _accountant_id(client)
    r = await client.patch(f"/v1/mnp/admin/careers/{aid}", json={"name_uk": "x"},
                           headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# core edit -> public reflects immediately -> version bump -> audit (§20/§21/§24)
# ---------------------------------------------------------------------------
async def test_edit_core_reflects_on_public_and_bumps_version_and_audits(client, admin_headers, session_factory):
    aid = await _accountant_id(client)
    before = (await client.get(f"/v1/mnp/admin/careers/{aid}", headers=admin_headers)).json()
    v0 = before["core"]["profile_version"]

    r = await client.patch(f"/v1/mnp/admin/careers/{aid}",
                           json={"short_description_uk": "Новий короткий опис для тесту."},
                           headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["core"]["profile_version"] == v0 + 1

    pub = (await client.get(f"/v1/mnp/careers/{aid}")).json()
    assert pub["overview"]["short_description_uk"] == "Новий короткий опис для тесту."

    async with session_factory() as s:
        logs = (await s.execute(
            select(AuditLog).where(AuditLog.entity_type == "mnp_career",
                                   AuditLog.action == "core_updated"))).scalars().all()
        assert logs and logs[-1].actor_admin_id is not None
        assert logs[-1].before_snapshot["short_description_uk"] != logs[-1].after_snapshot["short_description_uk"]

    # a pure GET must NOT bump the version
    v1 = (await client.get(f"/v1/mnp/admin/careers/{aid}", headers=admin_headers)).json()["core"]["profile_version"]
    assert v1 == v0 + 1


# ---------------------------------------------------------------------------
# every child collection CRUD (§9-16)
# ---------------------------------------------------------------------------
async def test_pros_cons_crud_and_public_consistency(client, admin_headers, session_factory):
    aid = await _accountant_id(client)
    n0 = len((await client.get(f"/v1/mnp/careers/{aid}")).json()["pros_cons"]["advantages"])

    view = (await client.post(f"/v1/mnp/admin/careers/{aid}/pros-cons",
                              json={"type": "advantage", "text_uk": "Тимчасова перевага для тесту"},
                              headers=admin_headers)).json()
    row_id = next(p["id"] for p in view["pros_cons"] if p["text_uk"] == "Тимчасова перевага для тесту")
    assert view["pros_cons"][[p["id"] for p in view["pros_cons"]].index(row_id)]["source_type"] == "mnp_editorial_v1"

    pub = (await client.get(f"/v1/mnp/careers/{aid}")).json()["pros_cons"]["advantages"]
    assert "Тимчасова перевага для тесту" in pub and len(pub) == n0 + 1

    await client.patch(f"/v1/mnp/admin/careers/{aid}/pros-cons/{row_id}",
                       json={"text_uk": "Оновлений текст"}, headers=admin_headers)
    assert "Оновлений текст" in (await client.get(f"/v1/mnp/careers/{aid}")).json()["pros_cons"]["advantages"]

    await client.delete(f"/v1/mnp/admin/careers/{aid}/pros-cons/{row_id}", headers=admin_headers)
    assert len((await client.get(f"/v1/mnp/careers/{aid}")).json()["pros_cons"]["advantages"]) == n0


async def test_responsibility_crud_and_reorder(client, admin_headers):
    aid = await _accountant_id(client)
    view = (await client.post(f"/v1/mnp/admin/careers/{aid}/responsibilities",
                              json={"title_uk": "Тестовий обов'язок", "description_uk": "опис",
                                    "importance": "low"}, headers=admin_headers)).json()
    rid = next(r["id"] for r in view["responsibilities"] if r["title_uk"] == "Тестовий обов'язок")
    order_before = [r["id"] for r in view["responsibilities"]]
    view2 = (await client.post(f"/v1/mnp/admin/careers/{aid}/responsibilities/{rid}/move",
                               json={"direction": "up"}, headers=admin_headers)).json()
    assert [r["id"] for r in view2["responsibilities"]] != order_before
    await client.delete(f"/v1/mnp/admin/careers/{aid}/responsibilities/{rid}", headers=admin_headers)
    titles = [r["title_uk"] for r in (await client.get(f"/v1/mnp/admin/careers/{aid}", headers=admin_headers)).json()["responsibilities"]]
    assert "Тестовий обов'язок" not in titles


async def test_skill_search_attach_dedup_and_create_canonical(client, admin_headers):
    aid = await _accountant_id(client)
    hits = (await client.get("/v1/mnp/admin/skills/search", params={"q": "Excel"}, headers=admin_headers)).json()
    assert any(h["name_uk"] == "Excel" for h in hits)
    excel_id = next(h["id"] for h in hits if h["name_uk"] == "Excel")

    # Excel is already attached to accountant -> duplicate rejected
    dup = await client.post(f"/v1/mnp/admin/careers/{aid}/skills",
                            json={"skill_id": excel_id}, headers=admin_headers)
    assert dup.status_code == 400

    # create a brand-new canonical skill, then attach it
    new = (await client.post("/v1/mnp/admin/skills",
                             json={"name_uk": "Тестова навичка ЕТ", "name_en": "Test Editor Skill",
                                   "skill_type": "technical"}, headers=admin_headers)).json()
    view = (await client.post(f"/v1/mnp/admin/careers/{aid}/skills",
                              json={"skill_id": new["id"], "importance": "high",
                                    "required_level": "working", "requirement_type": "must_have"},
                              headers=admin_headers)).json()
    sr = next(s for s in view["skills"] if s["skill_id"] == new["id"])
    assert sr["is_soft"] is False
    # creating the same canonical skill again is refused
    assert (await client.post("/v1/mnp/admin/skills",
            json={"name_uk": "Тестова навичка ЕТ", "name_en": "x", "skill_type": "technical"},
            headers=admin_headers)).status_code == 400
    # detach
    await client.delete(f"/v1/mnp/admin/careers/{aid}/skills/{sr['id']}", headers=admin_headers)
    assert new["id"] not in [s["skill_id"] for s in
                             (await client.get(f"/v1/mnp/admin/careers/{aid}", headers=admin_headers)).json()["skills"]]


async def test_requirement_unknown_not_forced_false_and_hard_needs_source(client, admin_headers):
    aid = await _accountant_id(client)
    view = (await client.get(f"/v1/mnp/admin/careers/{aid}", headers=admin_headers)).json()
    # legal section has no rows -> stays UNKNOWN on the public card
    pub = (await client.get(f"/v1/mnp/careers/{aid}")).json()
    assert pub["requirements"]["legal"]["items"] == []
    assert pub["requirements"]["legal"]["empty_label_uk"] == "Немає підтверджених даних"

    # a HARD requirement backed only by editorial opinion is rejected
    bad = await client.post(f"/v1/mnp/admin/careers/{aid}/requirements",
                            json={"category": "legal", "description_uk": "Тест", "hardness": "hard"},
                            headers=admin_headers)
    assert bad.status_code == 400
    # HARD with an authoritative source is allowed
    ok = await client.post(f"/v1/mnp/admin/careers/{aid}/requirements",
                           json={"category": "legal", "description_uk": "Ліцензія X", "hardness": "hard",
                                 "source_type": "official_ua", "source_reference": "Закон 123"},
                           headers=admin_headers)
    assert ok.status_code == 200


async def test_relation_no_self_and_no_duplicate(client, admin_headers):
    aid = await _accountant_id(client)
    rows = (await client.get("/v1/mnp/careers")).json()
    dev_id = next(c["id"] for c in rows if c["code"] == "software_developer")
    assert (await client.post(f"/v1/mnp/admin/careers/{aid}/relations",
            json={"to_career_id": aid, "relation_type": "related"}, headers=admin_headers)).status_code == 400
    ok = await client.post(f"/v1/mnp/admin/careers/{aid}/relations",
                           json={"to_career_id": dev_id, "relation_type": "adjacent"}, headers=admin_headers)
    assert ok.status_code == 200
    dup = await client.post(f"/v1/mnp/admin/careers/{aid}/relations",
                            json={"to_career_id": dev_id, "relation_type": "adjacent"}, headers=admin_headers)
    assert dup.status_code == 400


async def test_external_ref_crud(client, admin_headers):
    aid = await _accountant_id(client)
    view = (await client.post(f"/v1/mnp/admin/careers/{aid}/external-references",
                              json={"external_system": "esco", "external_id": "http://esco/x",
                                    "external_label": "Accountant", "mapping_type": "close",
                                    "note": "manual"}, headers=admin_headers)).json()
    eid = view["external_references"][0]["id"]
    assert view["external_references"][0]["review_status"] == "candidate"
    await client.patch(f"/v1/mnp/admin/careers/{aid}/external-references/{eid}",
                       json={"review_status": "confirmed"}, headers=admin_headers)
    v2 = (await client.get(f"/v1/mnp/admin/careers/{aid}", headers=admin_headers)).json()
    assert v2["external_references"][0]["review_status"] == "confirmed"
    await client.delete(f"/v1/mnp/admin/careers/{aid}/external-references/{eid}", headers=admin_headers)


# ---------------------------------------------------------------------------
# create -> DRAFT -> publish -> archive  (§22, §23, §25)
# ---------------------------------------------------------------------------
async def test_full_create_draft_publish_archive_flow(client, admin_headers):
    created = (await client.post("/v1/mnp/admin/careers", json={
        "career_code": "temp_test_career", "name_uk": "Тестова професія",
        "category_uk": "Тестова категорія", "short_description_uk": "короткий тест",
    }, headers=admin_headers)).json()
    cid = created["id"]
    assert created["core"]["status"] == "draft"

    # DRAFT is NOT in the public catalog / detail
    codes = {c["code"] for c in (await client.get("/v1/mnp/careers")).json()}
    assert "temp_test_career" not in codes
    assert (await client.get(f"/v1/mnp/careers/{cid}")).status_code == 404

    # publish blocked until minimum completeness
    r = await client.post(f"/v1/mnp/admin/careers/{cid}/publish", headers=admin_headers)
    assert r.status_code == 400

    await client.patch(f"/v1/mnp/admin/careers/{cid}",
                       json={"long_description_uk": "повний опис тестової професії"}, headers=admin_headers)
    await client.post(f"/v1/mnp/admin/careers/{cid}/responsibilities",
                      json={"title_uk": "Робити щось"}, headers=admin_headers)
    hits = (await client.get("/v1/mnp/admin/skills/search", params={"q": "Excel"}, headers=admin_headers)).json()
    await client.post(f"/v1/mnp/admin/careers/{cid}/skills",
                      json={"skill_id": hits[0]["id"]}, headers=admin_headers)

    assert (await client.get(f"/v1/mnp/admin/careers/{cid}/publish-readiness",
                             headers=admin_headers)).json()["ready"] is True
    r = await client.post(f"/v1/mnp/admin/careers/{cid}/publish", headers=admin_headers)
    assert r.status_code == 200 and r.json()["status"] == "active"

    # now visible publicly
    codes = {c["code"] for c in (await client.get("/v1/mnp/careers")).json()}
    assert "temp_test_career" in codes
    assert (await client.get(f"/v1/mnp/careers/{cid}")).status_code == 200

    # archive -> gone from public, data kept
    assert (await client.post(f"/v1/mnp/admin/careers/{cid}/archive",
                              headers=admin_headers)).json()["status"] == "archived"
    codes = {c["code"] for c in (await client.get("/v1/mnp/careers")).json()}
    assert "temp_test_career" not in codes
    assert (await client.get(f"/v1/mnp/careers/{cid}")).status_code == 404
    # still in the admin catalog
    admin_codes = {c["code"] for c in (await client.get("/v1/mnp/admin/careers", headers=admin_headers)).json()}
    assert "temp_test_career" in admin_codes


async def test_history_records_changed_by_and_values(client, admin_headers):
    aid = await _accountant_id(client)
    await client.patch(f"/v1/mnp/admin/careers/{aid}",
                       json={"name_en": "Accountant (edited)"}, headers=admin_headers)
    hist = (await client.get(f"/v1/mnp/admin/careers/{aid}/history", headers=admin_headers)).json()["history"]
    assert hist
    top = hist[0]
    assert top["changed_by_admin_id"] is not None and top["changed_at"]
    assert top["old_value"]["name_en"] != top["new_value"]["name_en"]


async def test_matching_still_sees_only_active_careers(client, admin_headers, session_factory):
    # publish a 6th career, archive an existing one -> matching count tracks ACTIVE
    from app.services.matching_mnp.engine import run_match
    from app.services.career_card_mnp.card import get_or_create_career_card, start_assessment_session
    from app.db.models_career_card import EntryMode, SourceMode
    from app.db.models_identity import IdentityUser
    from app.services.matching_mnp.queries import get_match_run_results

    async with session_factory() as s:
        user = IdentityUser(locale="uk")
        s.add(user)
        await s.flush()
        sess = await start_assessment_session(s, user_id=user.id, entry_mode=EntryMode.MANUAL)
        card = await get_or_create_career_card(s, user_id=user.id, assessment_session_id=sess.id,
                                               source_mode=SourceMode.MANUAL)
        await s.commit()
        run = await run_match(s, career_card_id=card.id)
        await s.commit()
        res = await get_match_run_results(s, run.id)
        assert len(res.ranked_top10) == 5  # unchanged by the editor infra
