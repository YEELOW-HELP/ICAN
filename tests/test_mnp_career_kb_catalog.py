"""MNP Career KB -- Work.ua starter-catalog import (Founder brief §23).

Work.ua is a DISCOVERY source only. These tests assert: the inventory
snapshot is coherent, the 145 new careers import as DRAFT, the alpha 5
are preserved, DRAFT careers are invisible to the public API and to
production matching, and no market data / hard blockers / duplicate
canonical skills leak in.
"""

from __future__ import annotations

import csv
import re
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.api.main import app
from app.db.models_career_card import MnpKnowledge, MnpSkill
from app.db.models_career_kb_mnp import (
    CareerLifecycleStatus,
    MnpCareer,
    MnpCareerRequirement,
    MnpMarketSnapshot,
)
from app.db.session import get_session
from app.services.career_kb_mnp.catalog_starter import STARTER_CAREERS, STARTER_FAMILIES, WORKUA_REFERENCE
from app.services.career_kb_mnp.seed_alpha import ALPHA_CAREER_CODES, seed_alpha_career_kb
from app.services.career_kb_mnp.seed_catalog import seed_starter_catalog

_REPO = Path(__file__).resolve().parents[1]
_INVENTORY = _REPO / "data_explorer" / "workua" / "inventory" / "workua_career_inventory_2026-08-31.csv"
_CYRILLIC = re.compile(r"[А-Яа-яЇїІіЄєҐґ]")


# ---------------------------------------------------------------------------
# inventory snapshot
# ---------------------------------------------------------------------------
def _inventory_rows() -> list[dict]:
    with _INVENTORY.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_inventory_snapshot_is_coherent():
    rows = _inventory_rows()
    assert len(rows) >= 100  # a real crawl of the Career Guide
    slugs = [r["workua_slug"] for r in rows]
    urls = [r["workua_url"] for r in rows]
    assert len(slugs) == len(set(slugs)), "duplicate slug in inventory"
    assert len(urls) == len(set(urls)), "duplicate url in inventory"
    assert all(r["workua_title_uk"].strip() for r in rows), "empty title in inventory"
    meta = _INVENTORY.with_suffix(".meta.json")
    assert meta.is_file()


def test_every_workua_profession_is_covered_by_mnp():
    inv_slugs = {r["workua_slug"] for r in _inventory_rows()}
    covered = {s["workua_slug"] for s in STARTER_CAREERS.values() if s.get("workua_slug")}
    covered |= {r["slug"] for r in WORKUA_REFERENCE.values()}
    assert inv_slugs <= covered, f"Work.ua professions with no MNP career: {inv_slugs - covered}"


def test_catalog_codes_and_identity_unique_and_ukrainian():
    codes = list(STARTER_CAREERS)
    assert len(codes) == len(set(codes))
    assert not (set(codes) & set(ALPHA_CAREER_CODES)), "starter catalog collides with an alpha career_code"
    names = [s["name_uk"] for s in STARTER_CAREERS.values()]
    assert len(names) == len(set(names)), "duplicate name_uk in starter catalog"
    for code, s in STARTER_CAREERS.items():
        assert re.fullmatch(r"[a-z0-9_]+", code), code
        assert s["name_uk"].strip() and s["name_en"].strip()
        assert s["family"] in STARTER_FAMILIES
        # descriptions are always genuine Ukrainian prose
        assert _CYRILLIC.search(s["short"]) and _CYRILLIC.search(s["long"])
        assert 3 <= len(s["resp"]) <= 8 and 4 <= len(s["skills"]) <= 15
        assert 3 <= len(s["pros"]) <= 6 and 3 <= len(s["cons"]) <= 6
    # the vast majority of titles are Ukrainian; a few established IT terms
    # (Data Scientist, ...) legitimately stay in Latin as the market uses them.
    n_cyr = sum(1 for s in STARTER_CAREERS.values() if _CYRILLIC.search(s["name_uk"]))
    assert n_cyr >= 0.9 * len(STARTER_CAREERS)


def test_no_workua_prose_markers_in_catalog():
    """A light copyright guard -- our text must not contain obvious
    verbatim-copy tells (Work.ua salary/vacancy phrasing, section
    headers) or literal Work.ua URLs inside human-readable fields."""
    banned = ["work.ua", "середня зарплата", "вакансій на", "зарплата від", "рейтинг професії"]
    for code, s in STARTER_CAREERS.items():
        blob = " ".join([s["short"], s["long"], *s["resp"], *s["pros"], *s["cons"]]).lower()
        for b in banned:
            assert b not in blob, f"{code}: suspicious phrase {b!r}"


# ---------------------------------------------------------------------------
# import behaviour
# ---------------------------------------------------------------------------
async def test_import_creates_drafts_preserves_alpha(session):
    await seed_alpha_career_kb(session)
    summ = await seed_starter_catalog(session)
    assert summ["created"] == len(STARTER_CAREERS)

    active = (await session.execute(select(MnpCareer).where(
        MnpCareer.status == CareerLifecycleStatus.ACTIVE))).scalars().all()
    draft = (await session.execute(select(MnpCareer).where(
        MnpCareer.status == CareerLifecycleStatus.DRAFT))).scalars().all()
    assert {c.code for c in active} == set(ALPHA_CAREER_CODES)
    assert len(draft) == len(STARTER_CAREERS)
    for c in draft:
        assert c.career_profile_version == 1

    # no fabricated market data, no hard blockers
    assert (await session.execute(select(func.count()).select_from(MnpMarketSnapshot))).scalar() == 0
    assert (await session.execute(select(func.count()).select_from(MnpCareerRequirement).where(
        MnpCareerRequirement.hardness == "hard"))).scalar() == 0
    for c in draft:
        assert c.market_data_limited is True


async def test_import_is_idempotent_and_non_destructive(session):
    await seed_alpha_career_kb(session)
    await seed_starter_catalog(session)
    # an admin edits a freshly imported DRAFT career
    from app.services.career_kb_mnp import editor
    a_code = next(iter(STARTER_CAREERS))
    cid = (await session.execute(select(MnpCareer.id).where(MnpCareer.code == a_code))).scalar_one()
    career = await editor.get_career_or_404(session, cid)
    await editor.update_career_core(session, career, actor_admin_id=1,
                                    short_description_uk="РЕДАГОВАНО КУРАТОРОМ")
    await session.commit()

    summ = await seed_starter_catalog(session)
    assert summ["created"] == 0 and summ["skipped_existing"] == len(STARTER_CAREERS)
    await session.refresh(career)
    assert career.description_short_uk == "РЕДАГОВАНО КУРАТОРОМ"


async def test_no_duplicate_canonical_skills_after_import(session):
    await seed_alpha_career_kb(session)
    await seed_starter_catalog(session)
    names = [n for (n,) in await session.execute(select(MnpSkill.canonical_name_en))]
    assert len(names) == len(set(names)), "duplicate canonical skill after import"
    kn = [n for (n,) in await session.execute(select(MnpKnowledge.canonical_name_en))]
    assert len(kn) == len(set(kn))


def test_reference_mapping_written_and_reference_only():
    ref_csv = _REPO / "data_explorer" / "workua" / "reference_mapping.csv"
    # produced by seed_catalog; regenerated on every import
    if not ref_csv.is_file():
        pytest.skip("reference_mapping.csv not generated yet (run an import)")
    with ref_csv.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert {"mnp_career_code", "workua_title_uk", "workua_slug", "workua_url", "mapping_status"} <= set(rows[0])
    assert any(r["mapping_status"] == "exact" for r in rows)  # accountant / sales_manager


# ---------------------------------------------------------------------------
# public API + matching isolation
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def client(session_factory):
    async def override_get_session():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = override_get_session
    async with session_factory() as s:
        await seed_alpha_career_kb(s)
    async with session_factory() as s:
        await seed_starter_catalog(s)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def test_public_catalog_shows_only_active_after_import(client):
    rows = (await client.get("/v1/mnp/careers")).json()
    assert {c["code"] for c in rows} == set(ALPHA_CAREER_CODES)
    assert len(rows) == 5


async def test_draft_career_detail_is_404(client, session_factory):
    async with session_factory() as s:
        draft_id = (await s.execute(select(MnpCareer.id).where(
            MnpCareer.status == CareerLifecycleStatus.DRAFT))).scalars().first()
    assert (await client.get(f"/v1/mnp/careers/{draft_id}")).status_code == 404


async def test_matching_unaffected_by_draft_catalog(client, session_factory):
    from app.db.models_career_card import EntryMode, SourceMode
    from app.db.models_identity import IdentityUser
    from app.services.career_card_mnp.card import get_or_create_career_card, start_assessment_session
    from app.services.matching_mnp.engine import run_match
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
        assert len(res.ranked_top10) == 5  # only the 5 ACTIVE careers, DRAFT excluded


async def test_admin_can_open_and_publish_an_imported_career(client, session_factory):
    from app.core.security import create_access_token, hash_password
    from app.db.models import AdminRole, AdminUser

    async with session_factory() as s:
        a = AdminUser(email="cat@mnp.dev", password_hash=hash_password("pw"), role=AdminRole.ADMIN, full_name="C")
        s.add(a)
        await s.commit()
        await s.refresh(a)
        token = create_access_token(a.id, a.role.value)
    h = {"Authorization": f"Bearer {token}"}

    admin_rows = (await client.get("/v1/mnp/admin/careers", headers=h)).json()
    assert len(admin_rows) == 150
    draft = next(c for c in admin_rows if c["status"] == "draft")

    view = (await client.get(f"/v1/mnp/admin/careers/{draft['id']}", headers=h)).json()
    assert view["core"]["status"] == "draft"
    assert view["responsibilities"] and view["skills"]

    # imported DRAFT already meets the publish minimum -> can be published, then archived back
    r = await client.post(f"/v1/mnp/admin/careers/{draft['id']}/publish", headers=h)
    assert r.status_code == 200 and r.json()["status"] == "active"
    assert draft["code"] in {c["code"] for c in (await client.get("/v1/mnp/careers")).json()}
    await client.post(f"/v1/mnp/admin/careers/{draft['id']}/archive", headers=h)
