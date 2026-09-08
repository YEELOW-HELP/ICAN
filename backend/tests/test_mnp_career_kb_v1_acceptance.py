"""MNP Career KB V1 -- Founder Acceptance guardrails (brief §28 consistency,
§29 language policy, §30 API tests).

ONE Career KB (the production `mnp_*` tables) feeds Matching, API, Website
and Excel. These tests assert the four views never diverge and that every
user-facing field is Ukrainian.
"""

from __future__ import annotations

import re
import uuid

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.api.main import app
from app.db.models_career_kb_mnp import (
    CareerLifecycleStatus,
    MnpCareer,
    MnpCareerPathStep,
    MnpCareerProCon,
    MnpCareerRequirement,
    MnpCareerSkillRequirement,
    MnpCareerTask,
    MnpMarketSnapshot,
    ProConType,
)
from app.db.models_career_card import MnpKnowledge, MnpSkill
from app.db.session import get_session
from app.services.career_kb_mnp.detail import get_career_detail_by_id
from app.services.career_kb_mnp.seed_alpha import ALPHA_CAREER_CODES, seed_alpha_career_kb

_UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
_CYRILLIC = re.compile(r"[А-Яа-яЇїІіЄєҐґ]")
# underscore-joined enum tokens must never appear verbatim in a display string
_RAW_ENUM_SUBSTRINGS = (
    "must_have", "high_value", "ready_now", "near_ready", "long_transition",
    "common_transition", "same_family", "career_change", "d0_same", "d4_career",
)
# a display string that is EXACTLY one of these (case-insensitive, trimmed) is a raw enum leak
_RAW_ENUM_EXACT = {
    "must_have", "high_value", "differentiator", "optional", "critical", "medium", "high", "low",
    "challenging", "moderate", "easy", "hard", "limited", "yes", "no", "unknown",
    "advantage", "disadvantage", "entry", "core", "senior", "lead", "executive", "junior",
}


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


def _walk_strings(node, path="$"):
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _walk_strings(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _walk_strings(v, f"{path}[{i}]")
    elif isinstance(node, str):
        yield path, node


# ---------------------------------------------------------------------------
# §28  DB  ==  API  ==  (Excel counts covered in tests/data_explorer)
# ---------------------------------------------------------------------------

async def test_five_active_careers_with_ukrainian_names(session):
    await seed_alpha_career_kb(session)
    careers = (await session.execute(select(MnpCareer))).scalars().all()
    active = [c for c in careers if c.status == CareerLifecycleStatus.ACTIVE]
    assert sorted(c.code for c in active) == sorted(ALPHA_CAREER_CODES)
    for c in active:
        assert c.canonical_name_uk and _CYRILLIC.search(c.canonical_name_uk)
        assert c.description_short_uk and c.description_long_uk
        assert c.market_data_limited is True
        assert c.difficulty_level is not None
        assert c.typical_entry_route_uk and _CYRILLIC.search(c.typical_entry_route_uk)


async def test_no_fabricated_market_data(session):
    await seed_alpha_career_kb(session)
    assert (await session.execute(select(func.count()).select_from(MnpMarketSnapshot))).scalar() == 0


async def test_db_api_counts_match(client, session_factory):
    async with session_factory() as session:
        careers = (await session.execute(select(MnpCareer).where(
            MnpCareer.status == CareerLifecycleStatus.ACTIVE))).scalars().all()
        for c in careers:
            n_resp = (await session.execute(select(func.count()).select_from(MnpCareerTask).where(
                MnpCareerTask.career_id == c.id))).scalar()
            n_skill = (await session.execute(select(func.count()).select_from(MnpCareerSkillRequirement).where(
                MnpCareerSkillRequirement.career_id == c.id))).scalar()
            n_req = (await session.execute(select(func.count()).select_from(MnpCareerRequirement).where(
                MnpCareerRequirement.career_id == c.id))).scalar()
            n_step = (await session.execute(select(func.count()).select_from(MnpCareerPathStep).where(
                MnpCareerPathStep.career_id == c.id))).scalar()
            n_adv = (await session.execute(select(func.count()).select_from(MnpCareerProCon).where(
                MnpCareerProCon.career_id == c.id, MnpCareerProCon.type == ProConType.ADVANTAGE))).scalar()
            n_dis = (await session.execute(select(func.count()).select_from(MnpCareerProCon).where(
                MnpCareerProCon.career_id == c.id, MnpCareerProCon.type == ProConType.DISADVANTAGE))).scalar()

            d = (await client.get(f"/v1/mnp/careers/{c.id}")).json()
            assert len(d["responsibilities"]) == n_resp
            assert len(d["skills"]["hard"]) + len(d["skills"]["soft"]) == n_skill
            assert sum(len(sec["items"]) for sec in d["requirements"].values()) == n_req
            assert len(d["career_path"]["steps"]) == n_step
            assert len(d["pros_cons"]["advantages"]) == n_adv >= 4
            assert len(d["pros_cons"]["disadvantages"]) == n_dis >= 4


# ---------------------------------------------------------------------------
# §30  API behaviour
# ---------------------------------------------------------------------------

async def test_career_list_is_ukrainian_and_five(client):
    rows = (await client.get("/v1/mnp/careers")).json()
    assert len(rows) == 5
    for r in rows:
        assert _CYRILLIC.search(r["name_uk"]) and _CYRILLIC.search(r["category_uk"])
        assert r["market_data_limited"] is True


async def test_unknown_career_404(client):
    assert (await client.get(f"/v1/mnp/careers/{uuid.uuid4()}")).status_code == 404


async def test_career_detail_structure_and_language(client):
    rows = (await client.get("/v1/mnp/careers")).json()
    for row in rows:
        d = (await client.get(f"/v1/mnp/careers/{row['id']}")).json()
        # structure
        for key in ("identity", "overview", "responsibilities", "skills", "knowledge",
                    "requirements", "entry", "pros_cons", "career_path", "related_careers",
                    "market", "external_references", "provenance"):
            assert key in d, key
        assert d["skills"]["hard"] and d["skills"]["soft"]
        assert d["career_path"]["label_uk"] == "Типовий кар'єрний шлях"
        assert [s["order"] for s in d["career_path"]["steps"]] == \
            list(range(1, len(d["career_path"]["steps"]) + 1))

        # market: data-limited, never a number
        assert d["market"]["data_limited"] is True
        assert d["market"]["salary"] is None and d["market"]["demand"] is None
        assert d["market"]["status_uk"] == "Недостатньо ринкових даних"

        # requirements: every section present; UNKNOWN stays UNKNOWN
        for key in ("education", "experience", "language", "credential", "legal", "other"):
            assert key in d["requirements"]
            sec = d["requirements"][key]
            if not sec["items"]:
                assert sec["empty_label_uk"] == "Немає підтверджених даних"

        # no raw UUID and no raw enum leak in any display string
        for path, s in _walk_strings(d):
            if path.endswith("_code") or path.endswith(".code") or path == "$.id" \
               or ".external_references" in path or path.endswith(".external_id") \
               or path.endswith(".data_quality"):
                continue
            assert not _UUID_RE.search(s), f"{row['code']} {path}: raw UUID -> {s!r}"
            low = s.strip().lower()
            assert not any(tok in low for tok in _RAW_ENUM_SUBSTRINGS), f"{row['code']} {path}: raw enum -> {s!r}"
            if path.endswith("_uk") or "_uk[" in path or path.endswith(("advantages]", "disadvantages]")):
                assert low not in _RAW_ENUM_EXACT, f"{row['code']} {path}: raw enum -> {s!r}"


# ---------------------------------------------------------------------------
# §29  LANGUAGE POLICY
# ---------------------------------------------------------------------------

async def test_every_user_facing_career_field_is_ukrainian(session):
    await seed_alpha_career_kb(session)
    careers = (await session.execute(select(MnpCareer).where(
        MnpCareer.status == CareerLifecycleStatus.ACTIVE))).scalars().all()

    for c in careers:
        for t in (await session.execute(select(MnpCareerTask).where(MnpCareerTask.career_id == c.id))).scalars():
            assert t.title_uk and _CYRILLIC.search(t.title_uk)
            assert t.description and _CYRILLIC.search(t.description)
        for r in (await session.execute(select(MnpCareerRequirement).where(
                MnpCareerRequirement.career_id == c.id))).scalars():
            assert r.description and _CYRILLIC.search(r.description)
        for p in (await session.execute(select(MnpCareerProCon).where(MnpCareerProCon.career_id == c.id))).scalars():
            assert p.text_uk and _CYRILLIC.search(p.text_uk)
        for s in (await session.execute(select(MnpCareerPathStep).where(
                MnpCareerPathStep.career_id == c.id))).scalars():
            assert s.step_name_uk and _CYRILLIC.search(s.step_name_uk)
            assert s.description_uk and _CYRILLIC.search(s.description_uk)

    # every skill/knowledge referenced by an active career has a populated
    # name_uk; product names (Excel, SQL, Git, 1С) legitimately stay Latin,
    # but anything with lowercase Latin words must be Ukrainian.
    latin_word = re.compile(r"\b[a-z]{4,}\b")
    for c in careers:
        d = await get_career_detail_by_id(session, c.id)
        for grp in ("hard", "soft"):
            for sk in d["skills"][grp]:
                assert sk["name_uk"], sk
                if latin_word.search(sk["name_uk"]):
                    assert _CYRILLIC.search(sk["name_uk"]), sk  # mixed -> must carry Ukrainian
        for kn in d["knowledge"]:
            assert _CYRILLIC.search(kn["name_uk"]), kn


async def test_skill_hard_soft_split_is_stable(session):
    await seed_alpha_career_kb(session)
    dev = (await session.execute(select(MnpCareer).where(MnpCareer.code == "software_developer"))).scalar_one()
    d = await get_career_detail_by_id(session, dev.id)
    hard_names = {s["name_en"] for s in d["skills"]["hard"]}
    soft_names = {s["name_en"] for s in d["skills"]["soft"]}
    assert "Python Programming" in hard_names
    assert "Problem Solving" in soft_names
    assert not (hard_names & soft_names)
