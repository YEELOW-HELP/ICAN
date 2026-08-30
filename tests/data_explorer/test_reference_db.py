"""BLOCK 1 tests for the DATA EXPLORER reference DB.

Offline: read `data/data_explorer/reference.sqlite` if it exists, skip the
whole module cleanly if it does not (so normal CI, which does not download
~250 MB of source archives, stays green). Build it with:
    pip install -r requirements-datalab.txt
    python -m data_explorer.cli download
    python -m data_explorer.cli build

Row counts are asserted only as *soft ranges tied to the pinned dataset
versions* (brief §25 — "не hardcode row count как вечный invariant").
"""

from __future__ import annotations

import ast
import hashlib
import os
import sqlite3
from pathlib import Path

import pytest

from data_explorer import config

REF = config.REFERENCE_DB
pytestmark = pytest.mark.skipif(
    not REF.exists(),
    reason="data/data_explorer/reference.sqlite not built (run `python -m data_explorer.cli build`)",
)

_DATA_EXPLORER_DIR = Path(__file__).resolve().parents[2] / "data_explorer"


@pytest.fixture(scope="module")
def conn():
    c = sqlite3.connect(REF)
    yield c
    c.close()


def _count(conn, table: str) -> int:
    return conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]  # noqa: S608


# --------------------------------------------------------------------------
# schema present
# --------------------------------------------------------------------------
def test_all_expected_tables_exist(conn):
    have = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    expected = {
        "stg_source",
        "onet_occupation", "onet_occupation_title", "onet_rating", "onet_work_value",
        "onet_task", "onet_task_rating", "onet_software_skill", "onet_related_occupation",
        "onet_dwa", "onet_content_model", "onet_scale", "onet_scale_anchor", "onet_category",
        "esco_occupation", "esco_occupation_label", "esco_skill", "esco_skill_label",
        "esco_isco_group", "esco_occupation_skill", "esco_skill_skill", "esco_broader",
        "esco_skill_hierarchy",
        "xwalk_esco_onet",
    }
    assert expected <= have, expected - have


# --------------------------------------------------------------------------
# provenance / versioning (brief §25)
# --------------------------------------------------------------------------
def test_every_source_has_version_sha_and_attribution(conn):
    rows = conn.execute(
        "SELECT source_label, version, sha256, attribution FROM stg_source"
    ).fetchall()
    assert len(rows) >= 5
    for label, version, sha, attr in rows:
        assert version, label
        assert sha and len(sha) == 64, label
        assert attr and len(attr) > 20, label


def test_source_labels_pin_the_expected_versions(conn):
    labels = {r[0] for r in conn.execute("SELECT source_label FROM stg_source")}
    assert config.ONET_RELEASE_LABEL in labels
    assert config.ONET_WORK_VALUES_LABEL in labels
    assert f"{config.ESCO_LABEL}_uk" in labels
    assert config.CROSSWALK_LABEL in labels


def test_onet_ratings_carry_a_release_label(conn):
    assert conn.execute(
        "SELECT count(*) FROM onet_rating WHERE release_label IS NULL OR release_label = ''"
    ).fetchone()[0] == 0
    assert conn.execute(
        "SELECT count(*) FROM onet_work_value WHERE release_label <> ?", (config.ONET_WORK_VALUES_LABEL,)
    ).fetchone()[0] == 0


# --------------------------------------------------------------------------
# O*NET scale validation + raw/normalized distinction (brief §6)
# --------------------------------------------------------------------------
def test_onet_scale_ranges_match_scales_reference(conn):
    for sid, (lo, hi) in config.ONET_SCALE_RANGES.items():
        row = conn.execute("SELECT minimum, maximum FROM onet_scale WHERE scale_id = ?", (sid,)).fetchone()
        assert row is not None, sid
        assert (row[0], row[1]) == (lo, hi), sid


def test_normalized_values_are_in_unit_interval_or_null(conn):
    bad = conn.execute(
        "SELECT count(*) FROM onet_rating WHERE normalized_value IS NOT NULL "
        "AND (normalized_value < -0.0001 OR normalized_value > 1.0001)"
    ).fetchone()[0]
    assert bad == 0


def test_category_scales_keep_raw_only_bounded_scales_normalise(conn):
    # a bounded scale (IM) must have normalized_value; a category scale (RL) must not
    im_nulls = conn.execute(
        "SELECT count(*) FROM onet_rating WHERE scale_id='IM' AND normalized_value IS NULL"
    ).fetchone()[0]
    rl_nonnull = conn.execute(
        "SELECT count(*) FROM onet_rating WHERE scale_id='RL' AND normalized_value IS NOT NULL"
    ).fetchone()[0]
    assert im_nulls == 0
    assert rl_nonnull == 0


def test_raw_values_within_declared_scale_bounds(conn):
    bad = conn.execute(
        "SELECT count(*) FROM onet_rating r JOIN onet_scale s USING(scale_id) "
        "WHERE r.raw_value < s.minimum - 1e-6 OR r.raw_value > s.maximum + 1e-6"
    ).fetchone()[0]
    assert bad == 0


# --------------------------------------------------------------------------
# missing != zero (brief §23, §27)
# --------------------------------------------------------------------------
def test_missing_is_an_absent_row_never_zero(conn):
    # an occupation with no work-values data must have ZERO rows, not rows of 0.0
    (soc_without,) = conn.execute(
        "SELECT o.soc FROM onet_occupation o WHERE NOT EXISTS "
        "(SELECT 1 FROM onet_work_value w WHERE w.soc = o.soc) LIMIT 1"
    ).fetchone() or (None,)
    if soc_without:
        assert conn.execute(
            "SELECT count(*) FROM onet_work_value WHERE soc = ?", (soc_without,)
        ).fetchone()[0] == 0


# --------------------------------------------------------------------------
# full work-style set present (brief §7, §14)
# --------------------------------------------------------------------------
def test_all_onet_work_styles_loaded_not_just_the_mnp_subset(conn):
    n = conn.execute(
        "SELECT count(DISTINCT element_id) FROM onet_rating WHERE table_key='work_style'"
    ).fetchone()[0]
    assert n >= 20  # O*NET 30.1+ redesign -> 21 elements
    assert len(config.MNP_SELECTED_ONET["work_style"]) < n


# --------------------------------------------------------------------------
# ESCO (brief §8)
# --------------------------------------------------------------------------
def test_esco_has_occupations_skills_relations_and_ukrainian(conn):
    assert 2900 <= _count(conn, "esco_occupation") <= 3300
    assert 12000 <= _count(conn, "esco_skill") <= 16000
    assert _count(conn, "esco_occupation_skill") > 100_000
    uk = conn.execute(
        "SELECT count(*) FROM esco_occupation WHERE preferred_label_uk IS NOT NULL AND preferred_label_uk <> ''"
    ).fetchone()[0]
    assert uk > 2900, "Ukrainian occupation labels missing"


def test_esco_occupation_skill_relation_types_preserved(conn):
    types = {r[0] for r in conn.execute("SELECT DISTINCT relation_type FROM esco_occupation_skill")}
    assert types == {"essential", "optional"}


# --------------------------------------------------------------------------
# crosswalk (brief §10)
# --------------------------------------------------------------------------
def test_crosswalk_never_promotes_to_exact(conn):
    assert conn.execute(
        "SELECT count(*) FROM xwalk_esco_onet WHERE mapping_relation = 'exact'"
    ).fetchone()[0] == 0
    assert conn.execute(
        "SELECT count(DISTINCT mapping_relation) FROM xwalk_esco_onet"
    ).fetchone()[0] == 1  # all 'unspecified'


def test_crosswalk_onet_codes_resolve(conn):
    unresolved = conn.execute(
        "SELECT count(*) FROM xwalk_esco_onet x LEFT JOIN onet_occupation o ON o.soc = x.onet_soc WHERE o.soc IS NULL"
    ).fetchone()[0]
    assert unresolved == 0


def test_crosswalk_partially_resolves_to_esco_uris(conn):
    total = _count(conn, "xwalk_esco_onet")
    resolved = conn.execute(
        "SELECT count(*) FROM xwalk_esco_onet WHERE esco_occupation_uri IS NOT NULL"
    ).fetchone()[0]
    assert total > 5000
    assert resolved / total > 0.7  # ISCO-group-level rows legitimately don't resolve


# --------------------------------------------------------------------------
# row-count sanity as *version metadata* (soft ranges, not eternal invariants)
# --------------------------------------------------------------------------
def test_row_counts_in_expected_range_for_pinned_versions(conn):
    ranges = {
        "onet_occupation": (950, 1100),
        "onet_rating": (350_000, 500_000),
        "onet_task": (17_000, 22_000),
        "esco_occupation": (2900, 3300),
        "xwalk_esco_onet": (7000, 10_000),
    }
    for table, (lo, hi) in ranges.items():
        n = _count(conn, table)
        assert lo <= n <= hi, f"{table}={n} outside [{lo},{hi}] — dataset version changed? update the pin + this range"


# --------------------------------------------------------------------------
# determinism (brief §25) — a full rebuild reproduces byte-identical content.
# Slow (~30-60s: re-parses the source archives). Opt in with
#   DATA_EXPLORER_SLOW=1 pytest tests/data_explorer/
# --------------------------------------------------------------------------
def _content_hash(conn, tables: list[str]) -> str:
    h = hashlib.sha256()
    for t in tables:
        for row in conn.execute(f"SELECT * FROM {t} ORDER BY 1,2,3"):  # noqa: S608
            h.update(repr(row).encode("utf-8"))
    return h.hexdigest()


@pytest.mark.skipif(os.environ.get("DATA_EXPLORER_SLOW") != "1", reason="set DATA_EXPLORER_SLOW=1")
def test_rebuild_is_deterministic():
    from data_explorer import reference

    tables = ["onet_rating", "onet_work_value", "esco_occupation_skill", "xwalk_esco_onet"]
    c1 = sqlite3.connect(REF)
    try:
        before = _content_hash(c1, tables)
    finally:
        c1.close()  # release the Windows file lock before build() unlinks the db

    reference.build()

    c2 = sqlite3.connect(REF)
    try:
        after = _content_hash(c2, tables)
    finally:
        c2.close()
    assert before == after


# --------------------------------------------------------------------------
# zero-AI guarantee (brief §27) — static check over the whole module
# --------------------------------------------------------------------------
def test_data_explorer_never_imports_ai_or_app_runtime():
    banned_substrings = ("ai_gateway", "anthropic", "openai")
    for path in _DATA_EXPLORER_DIR.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        mods: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods += [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                mods.append(node.module)
        for m in mods:
            assert not any(b in m for b in banned_substrings), f"{path.name}: imports {m}"
            # data_explorer may read app.db.models_* but must not import app services/api/bot
            assert not m.startswith(("app.services", "app.api", "app.bot")), f"{path.name}: imports {m}"
