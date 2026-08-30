"""BLOCK 2 tests — MNP snapshot, Explorer views, mapping review, human-lab
schema, golden export. Offline; the reference-DB-dependent tests skip if
it is not built.
"""

from __future__ import annotations

import json
import sqlite3

import pytest

from data_explorer import config
from data_explorer.human_lab import golden_export, schema

_REF = config.REFERENCE_DB
_needs_ref = pytest.mark.skipif(not _REF.exists(), reason="reference.sqlite not built")


# --------------------------------------------------------------------------
# MNP snapshot (read-only, in-memory) — brief §12, §24
# --------------------------------------------------------------------------
def test_mnp_snapshot_reads_the_alpha_kb_without_a_real_db():
    from data_explorer.mnp_snapshot import load_mnp_careers

    careers = load_mnp_careers()
    codes = {c.code for c in careers}
    assert {"sales_manager", "accountant", "software_developer",
            "customer_service_representative", "logistics_coordinator"} <= codes
    for c in careers:
        assert c.status == "active"
        assert c.skill_requirements  # every alpha career has MUST_HAVE skills


# --------------------------------------------------------------------------
# human-lab schema (brief §15–§18) — validated against the real MNP enums
# --------------------------------------------------------------------------
def test_example_person_and_expected_validate():
    base = config.HUMAN_LAB_EXAMPLES_DIR
    person = schema.load_person(base / "csr_to_office.person.yaml")
    expected = schema.load_expected(base / "csr_to_office.expected.yaml")
    assert person.persona_id == expected.persona_id == "csr_to_office"


def test_schema_rejects_a_bad_proficiency():
    with pytest.raises(schema.ValidationError):
        p = schema.PersonProfile(
            persona_id="x", label="x", segment="unemployed", last_role="x", years_experience=1,
            skills=[schema.PersonSkill(name="s", proficiency="expert", evidence="claimed")],
        )
        p.validate()


def test_schema_rejects_top_and_unacceptable_overlap():
    with pytest.raises(schema.ValidationError):
        e = schema.ExpectedResult(
            persona_id="x", expected_top_careers=["a"], acceptable_careers=[],
            unacceptable_careers=["a"], expected_feasibility={}, expected_transition_distance={},
        )
        e.validate()


def test_enum_sets_come_from_the_mnp_models_not_hardcoded():
    from app.db.models_matching_mnp import FeasibilityStatus, TransitionDistance

    assert schema.FEASIBILITY == {e.value for e in FeasibilityStatus}
    assert schema.TRANSITION == {e.value for e in TransitionDistance}
    assert "blocked" in schema.FEASIBILITY
    assert schema.PROFICIENCY == {"basic", "working", "strong"}


# --------------------------------------------------------------------------
# golden export (brief §19)
# --------------------------------------------------------------------------
def test_golden_export_produces_a_schema_valid_case():
    golden_export.run()
    case_path = config.GOLDEN_OUT_DIR / "case_csr_to_office.json"
    assert case_path.exists()
    case = json.loads(case_path.read_text(encoding="utf-8"))

    for key in golden_export.SCHEMA["required"]:
        assert key in case, key
    assert case["case_id"] == "de_csr_to_office"
    assert case["source_data_versions"]["onet"] == config.ONET_RELEASE_LABEL
    assert case["created_by"] and "gpt" not in case["created_by"].lower()
    # the person snapshot is embedded so a runner needs nothing else
    assert case["person_profile_snapshot"]["persona_id"] == "csr_to_office"


def test_golden_output_is_outside_evals_golden(tmp_path):
    # so the existing AI-task schema test never picks it up
    assert config.GOLDEN_OUT_DIR.name == "golden_data_explorer"
    assert "golden_data_explorer" in str(config.GOLDEN_OUT_DIR)
    assert (config.REPO_ROOT / "evals" / "golden") not in config.GOLDEN_OUT_DIR.parents


# --------------------------------------------------------------------------
# Explorer views + mapping review (brief §11, §12, §22) — need the ref DB
# --------------------------------------------------------------------------
@_needs_ref
def test_onet_occupation_view_assembles_all_families():
    from data_explorer.explorer import views

    conn = sqlite3.connect(_REF)
    conn.row_factory = sqlite3.Row
    try:
        v = views.onet_occupation_view(conn, "13-2011.00")  # Accountants and Auditors
        assert v["title"].startswith("Accountant")
        assert {"interest", "work_style", "knowledge", "ability", "work_activity"} <= set(v["ratings"])
        assert len(v["ratings"]["work_style"]) >= 20     # ALL work styles, brief §7
        assert v["tasks"] and v["software"]
    finally:
        conn.close()


@_needs_ref
def test_mnp_used_vs_ignored_shows_all_three_buckets():
    from data_explorer.explorer import views

    conn = sqlite3.connect(_REF)
    try:
        v = views.mnp_used_vs_ignored(conn, "13-2011.00")
        assert v["used"]["work_style"]            # some selected elements present
        assert v["ignored"]["work_style"]         # and many more ignored
        assert len(v["ignored"]["work_style"]) > len(v["used"]["work_style"])
    finally:
        conn.close()


@_needs_ref
def test_mapping_review_has_candidates_and_never_exact():
    conn = sqlite3.connect(_REF)
    try:
        n = conn.execute("SELECT count(*) FROM mapping_review").fetchone()[0]
        assert n > 0
        assert conn.execute(
            "SELECT count(*) FROM mapping_review WHERE proposed_mapping_type = 'exact'"
        ).fetchone()[0] == 0
        assert conn.execute(
            "SELECT count(*) FROM mapping_review WHERE review_state = 'candidate'"
        ).fetchone()[0] > 0
        # every alpha career got at least one row (candidate or review_required)
        assert conn.execute("SELECT count(DISTINCT mnp_code) FROM mapping_review").fetchone()[0] == 5
    finally:
        conn.close()
