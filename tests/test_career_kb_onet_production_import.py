"""Matching V1 M4.6 -- production O*NET import (DATA-002).

Offline: reads the committed `app/services/career_kb/onet_source_v3.json`
(no network -- pytest runs with --disable-socket). Proves the v0.3 career
vectors are genuinely sourced, that the M4.5 coverage gaps are closed,
that the versioning contract kept v0.1/v0.2 immutable, and that zero AI is
involved.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from sqlalchemy import select

from app.db.models_basic_assessment import ScaleFamily
from app.db.models_career_kb import CareerMatchingComponent, CareerMatchingProfile
from app.services.basic_assessment.attempts import complete_attempt
from app.services.basic_assessment.seed import seed_alpha_long_form
from app.services.basic_profile.calculation import calculate_basic_profile
from app.services.career_kb.onet_source_v3 import (
    CAREER_VECTOR_VERSION_V3,
    EX_TRANSFORMATION_VERSION,
    ONET_SOURCE_VERSION,
    artifact_meta,
    get_onet_data,
)
from app.services.career_kb.queries import get_career_matching_profile
from app.services.career_kb.seed import ALPHA_CAREER_CODES
from app.services.career_kb.seed_hardened import seed_alpha_career_matching_profiles_hardened
from app.services.career_kb.seed_v3 import seed_career_matching_profiles_v3, _primary_soc
from app.services.knowledge.retrieval import get_career_by_code
from app.services.matching.engine import match_profile_to_careers
from app.services.matching.ranking import rank_matching_results
from tests.helpers_basic_profile import answer_all_items
from tests.test_basic_profile_personas import PERSONAS

_CAREER_KB_DIR = Path(__file__).resolve().parents[1] / "app" / "services" / "career_kb"
_M46_MODULES = ("onet_source_v3.py", "seed_v3.py")
_WORK_VALUES_DIRECT = {"independence_value", "impact_helping", "recognition_status"}
_WORK_VALUES_NON_MAPPABLE = {"income", "stability", "growth", "work_life_balance", "learning"}


# --------------------------------------------------------------------------
# artifact
# --------------------------------------------------------------------------
def test_artifact_meta_declares_the_version_split():
    meta = artifact_meta()
    assert meta["live_scales_source"] == "onet_31.0"
    assert meta["work_values_source"] == "onet_30.2"
    assert meta["soc_count"] >= 23


def test_every_confirmed_alpha_soc_is_in_the_artifact():
    for code in ALPHA_CAREER_CODES:
        soc = _primary_soc(code)
        if soc is None:
            continue
        assert get_onet_data(soc) is not None, f"{code} -> {soc} missing from onet_source_v3.json"


# --------------------------------------------------------------------------
# seed produces v0.3
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_seed_v3_builds_current_profiles_superseding_v2(session):
    profiles = await seed_career_matching_profiles_v3(session)
    assert profiles, "no v0.3 profiles produced"

    accountant = await get_career_by_code(session, "accountant")
    all_for_accountant = (
        await session.execute(
            select(CareerMatchingProfile).where(CareerMatchingProfile.career_id == accountant.id)
        )
    ).scalars().all()
    versions = {p.career_vector_version for p in all_for_accountant}
    assert {"career_vector_v0.1", "career_vector_v0.2", "career_vector_v0.3"} <= versions

    current = [p for p in all_for_accountant if p.is_current]
    assert len(current) == 1
    assert current[0].career_vector_version == CAREER_VECTOR_VERSION_V3
    assert current[0].source_version == ONET_SOURCE_VERSION


@pytest.mark.asyncio
async def test_seed_v3_is_idempotent(session):
    first = await seed_career_matching_profiles_v3(session)
    second = await seed_career_matching_profiles_v3(session)
    assert {p.id for p in first} == {p.id for p in second}

    total = (await session.execute(select(CareerMatchingProfile))).scalars().all()
    v3 = [p for p in total if p.career_vector_version == CAREER_VECTOR_VERSION_V3]
    # one v0.3 profile per mapped career, no duplicates
    assert len(v3) == len({p.career_id for p in v3})


@pytest.mark.asyncio
async def test_unmapped_career_gets_no_v3_profile(session):
    await seed_career_matching_profiles_v3(session)
    outreach = await get_career_by_code(session, "community_outreach_coordinator")
    rows = (
        await session.execute(
            select(CareerMatchingProfile).where(
                CareerMatchingProfile.career_id == outreach.id,
                CareerMatchingProfile.career_vector_version == CAREER_VECTOR_VERSION_V3,
            )
        )
    ).scalars().all()
    assert rows == []


# --------------------------------------------------------------------------
# coverage: the M4.5 gaps are closed
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_work_style_now_populated_for_many_careers(session):
    """M4.5 shipped Work Style for exactly 1 of 24 careers. v0.3 must do far better."""
    await seed_career_matching_profiles_v3(session)
    careers_with_work_style = 0
    for code in ALPHA_CAREER_CODES:
        if _primary_soc(code) is None:
            continue
        career = await get_career_by_code(session, code)
        view = await get_career_matching_profile(session, career.id)
        ws = [c for c in view.work_styles.components if c.normalized_value is not None]
        if len(ws) >= 3:
            careers_with_work_style += 1
    assert careers_with_work_style >= 20


@pytest.mark.asyncio
async def test_work_values_populated_with_only_the_three_direct_keys(session):
    await seed_career_matching_profiles_v3(session)
    career = await get_career_by_code(session, "accountant")
    view = await get_career_matching_profile(session, career.id)
    keys = {c.scale_key for c in view.work_values.components if c.normalized_value is not None}
    assert keys == _WORK_VALUES_DIRECT
    assert keys.isdisjoint(_WORK_VALUES_NON_MAPPABLE)
    for c in view.work_values.components:
        row = (
            await session.execute(
                select(CareerMatchingComponent).where(
                    CareerMatchingComponent.scale_key == c.scale_key,
                    CareerMatchingComponent.scale_family == ScaleFamily.WORK_VALUES,
                )
            )
        ).scalars().first()
        assert row.transformation_version == EX_TRANSFORMATION_VERSION
        assert "30.2" in (row.source_element_name or "")


@pytest.mark.asyncio
async def test_riasec_uses_real_oi_numbers_not_holland_spread(session):
    """M4.5's v0.1 used a 0.90/0.70/0.50/0.20 Holland spread. v0.3 must use
    the rescaled real OI value -- so values are not confined to that set."""
    await seed_career_matching_profiles_v3(session)
    career = await get_career_by_code(session, "accountant")
    view = await get_career_matching_profile(session, career.id)
    values = sorted(c.normalized_value for c in view.interests.components)
    assert len(values) == 6
    holland_set = {0.20, 0.50, 0.70, 0.90}
    assert any(round(v, 2) not in holland_set for v in values)
    # accountant's Conventional interest is the O*NET max (7.0) -> normalizes to 1.0
    c_val = next(c.normalized_value for c in view.interests.components if c.scale_key == "C")
    assert c_val == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_missing_source_stays_null_never_zero(session):
    """financial_analyst's O*NET-SOC (13-2051.00) genuinely lacks Work
    Context + Work Values data in these releases -- those components must
    be absent, not present-with-0."""
    await seed_career_matching_profiles_v3(session)
    career = await get_career_by_code(session, "financial_analyst")
    view = await get_career_matching_profile(session, career.id)
    we_values = [c.normalized_value for c in view.work_environment.components]
    assert all(v is None for v in we_values) or we_values == []
    # RIASEC / Work Style still present for this SOC
    assert [c for c in view.interests.components if c.normalized_value is not None]


# --------------------------------------------------------------------------
# versioning contract: v0.1 / v0.2 untouched
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_legacy_profiles_remain_immutable_and_queryable(session):
    await seed_career_matching_profiles_v3(session)
    career = await get_career_by_code(session, "sales_manager")
    v1 = await get_career_matching_profile(session, career.id, version=1)
    v2 = await get_career_matching_profile(session, career.id, version=2)
    assert v1.career_vector_version == "career_vector_v0.1"
    assert v2.career_vector_version == "career_vector_v0.2"
    assert not v1.is_current and not v2.is_current


# --------------------------------------------------------------------------
# determinism + zero-AI + no Work.ua
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_deterministic(session, session_factory):
    await seed_career_matching_profiles_v3(session)
    career = await get_career_by_code(session, "electrician")
    view_a = await get_career_matching_profile(session, career.id)
    snapshot_a = sorted(
        (c.scale_key, c.normalized_value)
        for fam in (view_a.interests, view_a.work_styles, view_a.work_environment, view_a.work_values)
        for c in fam.components
    )
    async with session_factory() as s2:
        await seed_career_matching_profiles_v3(s2)
        c2 = await get_career_by_code(s2, "electrician")
        view_b = await get_career_matching_profile(s2, c2.id)
        snapshot_b = sorted(
            (c.scale_key, c.normalized_value)
            for fam in (view_b.interests, view_b.work_styles, view_b.work_environment, view_b.work_values)
            for c in fam.components
        )
    assert snapshot_a == snapshot_b


def test_m46_modules_do_not_import_ai_or_workua():
    for name in _M46_MODULES:
        src = (_CAREER_KB_DIR / name).read_text(encoding="utf-8")
        tree = ast.parse(src)
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported += [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
        assert not any("ai_gateway" in m or "anthropic" in m for m in imported), imported
        assert "work.ua" not in src.lower() and "workua" not in src.lower()


def test_onet_source_artifact_has_no_workua_or_ai_provenance():
    meta = artifact_meta()
    blob = str(meta).lower()
    assert "work.ua" not in blob and "gpt" not in blob and "claude" not in blob


# --------------------------------------------------------------------------
# BEFORE (v0.2) / AFTER (v0.3) persona report -- run with `pytest -s` to
# capture the tables for docs/engineering/27_...md. Not a correctness
# assertion beyond the structural invariants.
#
# NB: Work Style / Values Fit still print `low_differentiation` here. That
# is a *test-fixture* limitation (`answer_all_items` applies one literal
# response per scale, so a 2-item scale with one reverse-scored item
# always averages to the flat midpoint -> user_stdev = 0), compounded by
# the O*NET WI vectors' own low within-occupation variance on the 4
# MNP-mapped Work Style elements. The v0.3 *data* is present and correct
# (proven by the coverage tests above); whether the guarded cosine can
# SCORE those families is a separate M5 methodology question. See
# docs/engineering/27_...md §Limitations.
# --------------------------------------------------------------------------
@pytest.mark.parametrize("persona_name", list(PERSONAS.keys()))
@pytest.mark.asyncio
async def test_before_after_persona_report(session, persona_name):
    persona = PERSONAS[persona_name]
    definition = await seed_alpha_long_form(session)
    attempt, _ = await answer_all_items(session, definition, likert_bias=persona["bias"], default_likert=3)
    await complete_attempt(session, attempt)
    await session.commit()
    profile = await calculate_basic_profile(session, attempt)
    await session.commit()

    await seed_alpha_career_matching_profiles_hardened(session)   # v0.2 current
    await session.commit()
    before = await match_profile_to_careers(session, profile_id=profile.id)
    before_rank = await rank_matching_results(session, [r.id for r in before], profile_id=profile.id)
    await session.commit()

    await seed_career_matching_profiles_v3(session)               # v0.3 current
    await session.commit()
    after = await match_profile_to_careers(session, profile_id=profile.id)
    after_rank = await rank_matching_results(session, [r.id for r in after], profile_id=profile.id)
    await session.commit()

    def _fmt(ranking):
        out = []
        for i, e in enumerate(ranking.ranked[:10], 1):
            ws = (f"{e.work_style_band}/{e.work_style_raw_score:.2f}"
                  if e.work_style_raw_score is not None else e.work_style_status)
            vs = (f"{e.values_band}/{e.values_raw_score:.2f}"
                  if e.values_raw_score is not None else e.values_status)
            out.append(f"  {i:2d}. {e.career_code:30s} I={e.interest_band}/{e.interest_raw_score:.3f} "
                       f"WS={ws} V={vs} families={sorted(e.participating_families)}")
        return "\n".join(out) or "  (empty)"

    print(f"\n=== [{persona_name}] BEFORE career_vector_v0.2 (O*NET 30.3, hand fixture) ===")
    print(_fmt(before_rank))
    print(f"=== [{persona_name}] AFTER  career_vector_v0.3 (O*NET 31.0 + 30.2 WV, full import) ===")
    print(_fmt(after_rank))

    assert len(before) == 24 and len(after) == 24
    if persona_name == "E_flat_undifferentiated":
        # the flat persona must never produce a SCORED Interest Fit, under
        # either data version (guard on the user side).
        assert all(e.interest_raw_score is None for e in after_rank.ranked)
