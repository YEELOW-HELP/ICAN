"""Matching V1 M4.5 -- career vector data hardening with official O*NET
30.3 NUMERIC data (Founder Review "M4.5 GO", 2026-08-28). Covers the 18
Founder-specified test items verbatim, plus a BEFORE/AFTER persona report
generator (run with `-s` to capture the printed tables for doc 26).

M3's `seed_alpha_career_matching_profiles` (Holland-code approximation,
`career_vector_v0.1`) and M4.5's `seed_alpha_career_matching_profiles_hardened`
(official O*NET numeric data, `career_vector_v0.2`) are both idempotent,
additive, versioned profiles for the same 24 careers -- calling the
hardened seed does not edit or delete the M3 profile, it only supersedes
`is_current` (Founder Review's existing, unchanged versioning contract).
"""

import ast
import inspect

import pytest
from sqlalchemy import select

from app.db.models_basic_assessment import MatchingUsage, ScaleFamily
from app.db.models_career_kb import CareerMatchingComponent, CareerMatchingProfile
from app.services.basic_assessment.attempts import complete_attempt
from app.services.basic_assessment.seed import seed_alpha_long_form
from app.services.basic_profile.calculation import calculate_basic_profile
from app.services.career_kb import onet_30_3_numeric_fixture, quality, seed_hardened, vectors
from app.services.career_kb.onet_30_3_numeric_fixture import (
    CAREER_VECTOR_VERSION_V2,
    NUMERIC_MAPPING_VERSION,
    ONET_NUMERIC_SOURCE_VERSION,
    load_numeric_source,
)
from app.services.career_kb.queries import get_career_matching_profile
from app.services.career_kb.seed import ALPHA_CAREER_CODES, seed_alpha_career_matching_profiles
from app.services.career_kb.seed_hardened import seed_alpha_career_matching_profiles_hardened
from app.services.career_kb.vectors import (
    RIASEC_TRANSFORMATION_VERSION,
    holland_code_to_riasec_vector,
    oi_to_normalized,
    wi_to_normalized,
)
from app.services.knowledge.retrieval import get_career_by_code
from app.services.matching.engine import match_profile_to_careers
from app.services.matching.ranking import rank_matching_results
from tests.helpers_basic_profile import answer_all_items
from tests.test_basic_profile_personas import PERSONAS


# ---------------------------------------------------------------------------
# 1/2/3 -- real O*NET OI numeric values used for RIASEC; Holland approximation
# not preferred when OI is available; OI normalization exact.

async def test_riasec_uses_real_onet_oi_values_not_holland_approximation(session):
    """#1/#2 -- software_developer's hardened RIASEC vector matches
    `oi_to_normalized(raw_OI)` for every letter, NOT the Holland high-point
    approximation M3 used (which would collapse to 0.90/0.70/0.50/0.20)."""

    await seed_alpha_career_matching_profiles_hardened(session)
    await session.commit()

    career = await get_career_by_code(session, "software_developer")
    view = await get_career_matching_profile(session, career.id)
    by_key = {c.scale_key: c for c in view.interests.components}
    record = onet_30_3_numeric_fixture.get_numeric_source("software_developer")

    assert set(by_key) == {"R", "I", "A", "S", "E", "C"}
    for letter, raw in record.riasec_oi.items():
        assert by_key[letter].normalized_value == pytest.approx(oi_to_normalized(raw))
        assert by_key[letter].mapping_status == "direct"

    # Not the M3 Holland-approximation rank set {0.90, 0.70, 0.50, 0.20}:
    hardened_values = {round(c.normalized_value, 2) for c in view.interests.components}
    assert hardened_values != {0.90, 0.70, 0.50, 0.20}


def test_oi_normalization_exact():
    """#3 -- `oi_to_normalized` is an exact linear rescale of the OFFICIAL
    OI range (1 to 7, Scales Reference.txt)."""

    assert oi_to_normalized(1.0) == pytest.approx(0.0)
    assert oi_to_normalized(7.0) == pytest.approx(1.0)
    assert oi_to_normalized(4.0) == pytest.approx(0.5)
    assert oi_to_normalized(6.05) == pytest.approx((6.05 - 1.0) / 6.0)


# ---------------------------------------------------------------------------
# 4 -- full six-dimensional career vector retained (never a Top-3 reduction).

async def test_full_six_dimensional_riasec_vector_retained(session):
    """#4."""

    await seed_alpha_career_matching_profiles_hardened(session)
    await session.commit()

    for code in ALPHA_CAREER_CODES:
        if code == "community_outreach_coordinator":
            continue  # UNMAPPED -- legitimately zero components
        career = await get_career_by_code(session, code)
        view = await get_career_matching_profile(session, career.id)
        assert {c.scale_key for c in view.interests.components} == {"R", "I", "A", "S", "E", "C"}


# ---------------------------------------------------------------------------
# 5/7 -- Work Styles sourced from O*NET 30.3; only approved DIRECT/DERIVED
# mappings imported; Work Style normalization exact.

async def test_work_styles_sourced_from_onet_30_3_wi_scale(session):
    """#5/#6 -- sales_manager's Work Style components (leadership,
    initiative, ambiguity_tolerance = DIRECT WI scales; collaboration =
    DERIVED mean of two WI scales) use the real WI raw values, correctly
    rescaled from the -3..+3 signed scale, not the retired 1-5 scale."""

    await seed_alpha_career_matching_profiles_hardened(session)
    await session.commit()

    career = await get_career_by_code(session, "sales_manager")
    view = await get_career_matching_profile(session, career.id)
    by_key = {c.scale_key: c for c in view.work_styles.components}
    record = onet_30_3_numeric_fixture.get_numeric_source("sales_manager")

    assert set(by_key) == {"leadership", "initiative", "ambiguity_tolerance", "collaboration"}
    for key in ("leadership", "initiative", "ambiguity_tolerance"):
        assert by_key[key].normalized_value == pytest.approx(wi_to_normalized(record.work_style_wi[key]))
    expected_collab = (
        wi_to_normalized(record.work_style_wi["collaboration_social"])
        + wi_to_normalized(record.work_style_wi["collaboration_cooperation"])
    ) / 2.0
    assert by_key["collaboration"].normalized_value == pytest.approx(expected_collab)
    # `structure_preference` never populated (no current O*NET element).
    assert "structure_preference" not in by_key


def test_wi_normalization_exact():
    """#7 -- `wi_to_normalized` is an exact linear rescale of the OFFICIAL
    signed WI range (-3 to +3); 0 (neutral) maps to the midpoint 0.5."""

    assert wi_to_normalized(-3.0) == pytest.approx(0.0)
    assert wi_to_normalized(3.0) == pytest.approx(1.0)
    assert wi_to_normalized(0.0) == pytest.approx(0.5)
    assert wi_to_normalized(1.13) == pytest.approx((1.13 + 3.0) / 6.0)


# ---------------------------------------------------------------------------
# 8 -- Work Context imported only for approved mappings.

async def test_work_environment_only_approved_scales_imported(session):
    """#8 -- registered_nurse's Work Environment components are exactly the
    5 approved MATCH_ENABLED scale keys (never a 6th, un-approved one)."""

    await seed_alpha_career_matching_profiles_hardened(session)
    await session.commit()

    career = await get_career_by_code(session, "registered_nurse")
    view = await get_career_matching_profile(session, career.id)
    keys = {c.scale_key for c in view.work_environment.components}
    assert keys == {
        "collaboration_context", "customer_interaction_context", "schedule_predictability",
        "setting", "physical_environment",
    }
    for c in view.work_environment.components:
        assert c.mapping_status in ("direct", "derived")


# ---------------------------------------------------------------------------
# 9 -- missing data remains missing (never fabricated).

async def test_missing_work_context_stays_missing_not_fabricated(session):
    """#9 -- project_manager/financial_analyst (empty work_context in the
    real O*NET 30.3 release) get ZERO Work Environment components, not a
    fabricated placeholder value."""

    await seed_alpha_career_matching_profiles_hardened(session)
    await session.commit()

    for code in ("project_manager", "financial_analyst"):
        career = await get_career_by_code(session, code)
        view = await get_career_matching_profile(session, career.id)
        assert view.work_environment.components == []
        # ...but RIASEC and Work Style data (which DO exist for these SOC
        # codes) are still populated -- confirming this is a genuine,
        # scale-specific gap, not a broken career-level mapping.
        assert view.interests.components != []
        assert view.work_styles.components != []


async def test_unmapped_career_gets_zero_components_of_any_kind(session):
    """#9 (continued) -- community_outreach_coordinator (UNMAPPED)."""

    await seed_alpha_career_matching_profiles_hardened(session)
    await session.commit()

    career = await get_career_by_code(session, "community_outreach_coordinator")
    view = await get_career_matching_profile(session, career.id)
    assert view.interests.components == []
    assert view.work_styles.components == []
    assert view.work_environment.components == []
    assert view.work_values.components == []


# ---------------------------------------------------------------------------
# 10 -- Work Values remain insufficient without an approved current source.

async def test_work_values_remain_unavailable_for_every_alpha_career(session):
    """#10 -- zero Work Values components for ANY of the 24 careers, since
    no current O*NET Work Values source exists (disclosed finding)."""

    await seed_alpha_career_matching_profiles_hardened(session)
    await session.commit()

    for code in ALPHA_CAREER_CODES:
        career = await get_career_by_code(session, code)
        view = await get_career_matching_profile(session, career.id)
        assert view.work_values.components == []


def test_no_legacy_onet_work_values_v30_0_implemented():
    """#10 (continued) -- the future option is documented, not implemented,
    in this pass; no such transformation function/constant exists yet."""

    source = inspect.getsource(vectors) + inspect.getsource(onet_30_3_numeric_fixture)
    assert "LEGACY_ONET_WORK_VALUES_V30_0" not in source or "not implement" in source.lower()
    assert not hasattr(vectors, "work_values_to_normalized")


# ---------------------------------------------------------------------------
# 11/12 -- zero AI calls; no Work.ua data import.

def test_no_ai_gateway_imports_in_m45_modules():
    """#11."""

    forbidden_module_prefixes = ("app.ai_gateway",)
    forbidden_names = {"AIGateway", "AnswerExtractor", "EvidenceExtractor", "ClaimSynthesizer", "Summarizer"}
    for module in (onet_30_3_numeric_fixture, vectors, quality, seed_hardened):
        tree = ast.parse(inspect.getsource(module))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not any(
                    node.module == p or node.module.startswith(p + ".") for p in forbidden_module_prefixes
                ), f"{module.__name__} imports forbidden module {node.module!r}"
        referenced = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        assert referenced.isdisjoint(forbidden_names)


def test_no_workua_import_in_m45_modules():
    """#12."""

    forbidden = ("workua.com", "requests.get(", "requests.post(", "beautifulsoup", "scrapy", "selenium", "bs4")
    for module in (onet_30_3_numeric_fixture, vectors, quality, seed_hardened):
        source = inspect.getsource(module).lower()
        for token in forbidden:
            assert token not in source, f"{module.__name__} contains forbidden artifact {token!r}"


# ---------------------------------------------------------------------------
# 13 -- offline fixture deterministic.

def test_offline_fixture_deterministic_and_no_network():
    """#13."""

    source = inspect.getsource(onet_30_3_numeric_fixture)
    for forbidden in ("requests.", "httpx.", "urllib.request", "aiohttp.", "curl"):
        assert forbidden not in source

    a = load_numeric_source()
    b = load_numeric_source()
    assert a == b
    assert len(a) == 24


# ---------------------------------------------------------------------------
# 14 -- source provenance preserved (source system/element id/name/raw
# value/normalization/mapping version all persisted per component).

async def test_source_provenance_preserved_per_component(session):
    """#14."""

    await seed_alpha_career_matching_profiles_hardened(session)
    await session.commit()

    career = await get_career_by_code(session, "software_developer")
    profile_result = await session.execute(
        select(CareerMatchingProfile).where(
            CareerMatchingProfile.career_id == career.id,
            CareerMatchingProfile.career_vector_version == CAREER_VECTOR_VERSION_V2,
        )
    )
    profile = profile_result.scalar_one()
    assert profile.source_version == ONET_NUMERIC_SOURCE_VERSION
    assert profile.mapping_version == NUMERIC_MAPPING_VERSION

    components = (
        (
            await session.execute(
                select(CareerMatchingComponent).where(CareerMatchingComponent.profile_id == profile.id)
            )
        )
        .scalars()
        .all()
    )
    assert components
    for c in components:
        assert c.source_system == "onet"
        assert c.source_element_id is not None
        assert c.source_element_name is not None
        assert c.source_raw_value is not None
        assert c.transformation_version is not None


# ---------------------------------------------------------------------------
# 15 -- all 24 careers processed.

async def test_all_24_alpha_careers_processed_by_hardened_seed(session):
    """#15."""

    profiles = await seed_alpha_career_matching_profiles_hardened(session)
    await session.commit()
    assert len(profiles) == 24
    assert {p.career_vector_version for p in profiles} == {CAREER_VECTOR_VERSION_V2}


# ---------------------------------------------------------------------------
# 16/17 -- existing M4 engine tests remain green; M1-M4 regression remains
# green. (Verified by running the full suite separately -- see Founder
# Report §13. This test only proves the ENGINE MODULE ITSELF was not
# touched by re-importing it and checking its source hash is unchanged
# from before this phase started is out of scope for a unit test; instead
# we prove the engine still produces correctly-shaped results against the
# NEW v0.2 profiles with zero code changes needed.)

async def test_m4_engine_runs_unchanged_against_hardened_profiles(session):
    """#16/#17 -- `match_profile_to_careers`/`calculate_pair_match` (M4,
    frozen) require no code change to consume the new v0.2 profiles."""

    definition = await seed_alpha_long_form(session)
    attempt, _user = await answer_all_items(session, definition, default_likert=3)
    await complete_attempt(session, attempt)
    await session.commit()
    profile = await calculate_basic_profile(session, attempt)
    await session.commit()

    await seed_alpha_career_matching_profiles_hardened(session)
    await session.commit()
    results = await match_profile_to_careers(session, profile_id=profile.id)
    await session.commit()
    assert len(results) == 24
    for r in results:
        assert r.career_vector_version == CAREER_VECTOR_VERSION_V2


# ---------------------------------------------------------------------------
# 18 -- flat persona remains protected (never SCORED under the new data).

async def test_flat_persona_still_protected_under_hardened_data(session):
    """#18."""

    persona = PERSONAS["E_flat_undifferentiated"]
    definition = await seed_alpha_long_form(session)
    attempt, _user = await answer_all_items(session, definition, likert_bias=persona["bias"], default_likert=3)
    await complete_attempt(session, attempt)
    await session.commit()
    profile = await calculate_basic_profile(session, attempt)
    await session.commit()

    await seed_alpha_career_matching_profiles_hardened(session)
    await session.commit()
    results = await match_profile_to_careers(session, profile_id=profile.id)
    await session.commit()
    result_ids = [r.id for r in results]
    ranking = await rank_matching_results(session, result_ids, profile_id=profile.id)

    assert ranking.ranked == []
    assert len(ranking.unranked) + len(ranking.blocked) == 24


# ---------------------------------------------------------------------------
# Sanity: legacy M3 profile is untouched by the hardened seed (never edited).

async def test_legacy_m3_profile_untouched_by_hardened_seed(session):
    """M3's `career_vector_v0.1` profile still exists, unmodified, and is
    simply no longer `is_current` after the hardened seed runs -- the
    Holland-code approximation is preserved as
    `LEGACY_ENGINEERING_FALLBACK`, never deleted, never edited."""

    await seed_alpha_career_matching_profiles(session)
    await session.commit()
    career = await get_career_by_code(session, "software_developer")
    legacy_view = await get_career_matching_profile(session, career.id, version=1)
    legacy_riasec = {c.scale_key: c.normalized_value for c in legacy_view.interests.components}
    # software_developer's M3 Holland code is "IC" (onet_alpha_fixture.py) --
    # the legacy vector must still be the Holland-approximation shape.
    assert legacy_riasec == holland_code_to_riasec_vector("IC")

    await seed_alpha_career_matching_profiles_hardened(session)
    await session.commit()

    legacy_view_after = await get_career_matching_profile(session, career.id, version=1)
    assert legacy_view_after.career_vector_version == "career_vector_v0.1"
    assert legacy_view_after.is_current is False
    for c in legacy_view_after.interests.components:
        assert c.mapping_status == "direct"  # unchanged M3 shape (Holland approx -> RIASEC is always "direct" mapping_status)

    current_view = await get_career_matching_profile(session, career.id)  # version=None -> current
    assert current_view.career_vector_version == CAREER_VECTOR_VERSION_V2


# ---------------------------------------------------------------------------
# Quality classification (Founder Review §13).

def test_classify_component_quality_tiers():
    assert quality.classify_component_quality(
        transformation_version="onet_oi_numeric_v0.1", provisional=False
    ) == quality.CURRENT_OFFICIAL
    assert quality.classify_component_quality(
        transformation_version="onet_holland_to_riasec_v0.1", provisional=False
    ) == quality.LEGACY_SOURCE
    assert quality.classify_component_quality(
        transformation_version="some_other_v0.1", provisional=True
    ) == quality.MNP_DERIVED


def test_classify_mapping_quality_tiers():
    assert quality.classify_mapping_quality(mapping_status="unmapped") == quality.UNMAPPED
    assert quality.classify_mapping_quality(mapping_status="provisional") == quality.PROVISIONAL
    assert quality.classify_mapping_quality(mapping_status="confirmed") == quality.CURRENT_OFFICIAL


# ---------------------------------------------------------------------------
# BEFORE/AFTER persona report generator (not a correctness assertion --
# run with `pytest -s` to capture the printed tables for doc 26).

@pytest.mark.parametrize("persona_name", list(PERSONAS.keys()))
async def test_before_after_persona_report(session, persona_name):
    persona = PERSONAS[persona_name]
    definition = await seed_alpha_long_form(session)
    attempt, _user = await answer_all_items(session, definition, likert_bias=persona["bias"], default_likert=3)
    await complete_attempt(session, attempt)
    await session.commit()
    profile = await calculate_basic_profile(session, attempt)
    await session.commit()

    # BEFORE: M3 legacy profiles only.
    await seed_alpha_career_matching_profiles(session)
    await session.commit()
    before_results = await match_profile_to_careers(session, profile_id=profile.id)
    await session.commit()
    before_ranking = await rank_matching_results(session, [r.id for r in before_results], profile_id=profile.id)

    # AFTER: hardened v0.2 profiles (supersedes is_current; M3 profile
    # remains in the DB, untouched, just no longer current).
    await seed_alpha_career_matching_profiles_hardened(session)
    await session.commit()
    after_results = await match_profile_to_careers(session, profile_id=profile.id)
    await session.commit()
    after_ranking = await rank_matching_results(session, [r.id for r in after_results], profile_id=profile.id)

    def _fmt(ranking):
        lines = []
        for i, entry in enumerate(ranking.ranked[:10], start=1):
            ws = f"{entry.work_style_band}/{entry.work_style_raw_score:.2f}" if entry.work_style_raw_score is not None else entry.work_style_status
            vs = f"{entry.values_band}/{entry.values_raw_score:.2f}" if entry.values_raw_score is not None else entry.values_status
            fs = f"{entry.feasibility_status}/{entry.feasibility_raw_score:.2f}" if entry.feasibility_raw_score is not None else entry.feasibility_status
            lines.append(
                f"  {i:2d}. {entry.career_code:32s} interest={entry.interest_band}/{entry.interest_raw_score:.3f} "
                f"work_style={ws} values={vs} feasibility={fs} families={list(entry.participating_families)}"
            )
        return "\n".join(lines) if lines else "  (empty -- ranked list is empty)"

    print(f"\n=== [{persona_name}] BEFORE (career_vector_v0.1, Holland approx) ===")
    print(_fmt(before_ranking))
    print(f"=== [{persona_name}] AFTER (career_vector_v0.2, O*NET 30.3 numeric) ===")
    print(_fmt(after_ranking))

    # Both runs must process the full Alpha catalog regardless of data version.
    assert len(before_results) == 24
    assert len(after_results) == 24
