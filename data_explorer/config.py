"""Paths, dataset version pins, provenance constants, and the O*NET
element-id / scale-id maps the loaders need.

Every O*NET element id / scale id below is taken verbatim from that
release's own `Content Model Reference.txt` / `Scales Reference.txt` and
is asserted at build time — never inferred from the data values.
"""

from __future__ import annotations

from pathlib import Path

# --------------------------------------------------------------------------
# Paths — everything under data/ is gitignored and rebuilt from the scripts
# --------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data" / "data_explorer"
VENDOR_DIR = DATA_DIR / "vendor"
ONET_VENDOR_DIR = REPO_ROOT / "data" / "onet" / "vendor"      # reused from commit 6d27bf3
ESCO_VENDOR_DIR = VENDOR_DIR / "esco"
CROSSWALK_VENDOR_DIR = VENDOR_DIR / "crosswalk"
REFERENCE_DB = DATA_DIR / "reference.sqlite"
EXPORT_DIR = DATA_DIR / "exports"
HUMAN_LAB_DIR = DATA_DIR / "human_lab"                        # hand-authored YAML inputs (gitignored working copies)
HUMAN_LAB_EXAMPLES_DIR = REPO_ROOT / "data_explorer" / "human_lab" / "examples"  # committed worked examples
# kept OUTSIDE evals/golden/ so the existing AI-task schema test never sees it
GOLDEN_OUT_DIR = REPO_ROOT / "evals" / "golden_data_explorer"

DOCS_DIR = REPO_ROOT / "docs" / "data_explorer"

# --------------------------------------------------------------------------
# Dataset version pins (checkpoint decision, MNP DATA EXPLORER V1)
# --------------------------------------------------------------------------
ONET_RELEASE = "31_0"                 # -> data/onet/vendor/db_31_0_text/
ONET_RELEASE_LABEL = "onet_31.0"
ONET_WORK_VALUES_RELEASE = "30_2"     # last release that shipped Work Values.txt
ONET_WORK_VALUES_LABEL = "onet_30.2"
ONET_URL = "https://www.onetcenter.org/dl_files/database/db_{release}_text.zip"

ESCO_VERSION = "v1.2.1"
ESCO_LABEL = "esco_v1.2.1"
ESCO_LANGUAGES = ("en", "uk")         # uk = ETF-produced Ukrainian translation
ESCO_URL = (
    "https://ec.europa.eu/esco/download/"
    "ESCO%20dataset%20-%20{version}%20-%20classification%20-%20{lang}%20-%20csv.zip"
)

CROSSWALK_LABEL = "esco_onet_crosswalk_onetcenter"
CROSSWALK_URL = "https://www.onetcenter.org/crosswalks/esco/ESCO_to_ONET-SOC.xlsx"

# --------------------------------------------------------------------------
# Attribution (must be shown wherever this data reaches an end user)
# --------------------------------------------------------------------------
ATTRIBUTION = {
    ONET_RELEASE_LABEL: (
        "This product incorporates information from the O*NET 31.0 Database, used under "
        "the CC BY 4.0 license. O*NET is a trademark of the U.S. Department of Labor, "
        "Employment and Training Administration, National Center for O*NET Development."
    ),
    ONET_WORK_VALUES_LABEL: (
        "Work Values data from the O*NET 30.2 Database (the last release to include it), "
        "used under the CC BY 4.0 license."
    ),
    ESCO_LABEL: (
        "This product uses the ESCO classification of the European Union, ESCO v1.2.1, "
        "https://esco.ec.europa.eu . The Ukrainian version of ESCO was produced by the "
        "European Training Foundation (ETF). ESCO is available free of charge."
    ),
    CROSSWALK_LABEL: (
        "ESCO<->O*NET crosswalk published by the National Center for O*NET Development "
        "and the European Commission (built with AI techniques + human validation)."
    ),
}

# --------------------------------------------------------------------------
# O*NET scale ids -> official (min, max) from Scales Reference.txt.
# Asserted against the shipped file at build time.
# --------------------------------------------------------------------------
ONET_SCALE_RANGES: dict[str, tuple[float, float]] = {
    "OI": (1.0, 7.0),    # Occupational Interests (RIASEC)
    "WI": (-3.0, 3.0),   # Work Styles Impact (signed)
    "IM": (1.0, 5.0),    # Importance (Skills / Knowledge / Abilities / Work Activities)
    "LV": (0.0, 7.0),    # Level
    "CX": (1.0, 5.0),    # Work Context (most elements)
    "CT": (1.0, 3.0),    # Work Context ("Work Schedules")
    "EX": (1.0, 7.0),    # Work Values Extent (30.2)
}
# Category-percentage / rank scales we keep raw but do NOT [0,1]-normalise.
ONET_CATEGORY_SCALES = {"RL", "RW", "RQ", "OJ", "PT", "CXP", "CTP", "FT", "DR", "DS", "IH", "VH"}

# --------------------------------------------------------------------------
# O*NET "ratings file" table plan.
#   key   = table name (onet_<key>)
#   file  = source .txt in the release
#   scales= scale ids to keep (others in the file are ignored)
#   family= Content Model family this belongs to (for the RAW-vs-MNP view)
# All of these share the header shape
#   O*NET-SOC Code | Element ID | Element Name | Scale ID | [Category] | Data Value | ...
# --------------------------------------------------------------------------
ONET_RATING_TABLES: dict[str, dict] = {
    "interest":          dict(file="Career Interest Types.txt", scales={"OI"},           family="1.B Interests"),
    "work_style":        dict(file="Work Styles.txt",           scales={"WI"},           family="1.D Work Styles"),
    "ability":           dict(file="Abilities.txt",             scales={"IM", "LV"},     family="1.A Abilities"),
    "skill_essential":   dict(file="Essential Skills.txt",      scales={"IM", "LV"},     family="2.A Essential (basic/cross-functional) Skills"),
    "skill_transferable":dict(file="Transferable Skills.txt",   scales={"IM", "LV"},     family="2.B Transferable Skills"),
    "knowledge":         dict(file="Knowledge.txt",             scales={"IM", "LV"},     family="2.C Knowledge"),
    "work_activity":     dict(file="Work Activities.txt",       scales={"IM", "LV"},     family="4.A Work Activities (GWA)"),
    "work_context":      dict(file="Work Context.txt",          scales={"CX", "CT"},     family="4.C Work Context", has_category=True, category_keep={"n/a"}),
    "education":         dict(file="Education.txt",              scales={"RL"},           family="2.D Education", has_category=True),
    "training_experience": dict(file="Training and Experience.txt", scales={"RW", "RL", "OJ", "PT"}, family="3.A Training & Experience", has_category=True),
}
# Work Values comes from the 30.2 release, same shape, scale EX.
ONET_WORK_VALUES_TABLE = dict(file="Work Values.txt", scales={"EX"}, family="1.B.2 Work Values (30.2)")

# --------------------------------------------------------------------------
# RIASEC / Work Values element ids -> short key (for readable views only;
# the raw element id/name is always stored too).
# --------------------------------------------------------------------------
RIASEC_ELEMENTS = {
    "1.B.1.a": "R", "1.B.1.b": "I", "1.B.1.c": "A",
    "1.B.1.d": "S", "1.B.1.e": "E", "1.B.1.f": "C",
}
WORK_VALUES_ELEMENTS = {
    "1.B.2.a": "achievement", "1.B.2.b": "working_conditions", "1.B.2.c": "recognition",
    "1.B.2.d": "relationships", "1.B.2.e": "support", "1.B.2.f": "independence",
}

# --------------------------------------------------------------------------
# Which O*NET dimensions the *current* MNP matching engine actually selects
# (so the Explorer can show RAW vs MNP-SELECTED — brief §7). Sourced from
# methodology_lab/05_GOLDEN_TEST/MNP_SCALE_TO_ONET_MAPPING_V0.1.md and the
# prior workstream's onet_source_v3 (commit 6d27bf3). This is descriptive,
# not authoritative — it does not gate anything.
MNP_SELECTED_ONET = {
    "interest": ["1.B.1.a", "1.B.1.b", "1.B.1.c", "1.B.1.d", "1.B.1.e", "1.B.1.f"],  # all 6 RIASEC
    "work_style": ["1.D.1.i", "1.D.1.e", "1.D.1.d", "1.D.2.f", "1.D.2.d"],           # leadership/initiative/ambiguity/social+cooperation
    "work_context": ["4.C.1.b.1.e", "4.C.1.b.1.f", "4.C.3.d.4", "4.C.2.a.1.a", "4.C.2.d.1.b", "4.C.2.d.1.d"],
    "work_values": ["1.B.2.f", "1.B.2.d", "1.B.2.c"],                                # independence/relationships/recognition
}

# --------------------------------------------------------------------------
# ESCO CSV file plan (per language: <name>_<lang>.csv)
# --------------------------------------------------------------------------
ESCO_FILES = {
    "occupations": "occupations",
    "skills": "skills",
    "isco_groups": "ISCOGroups",
    "skill_groups": "skillGroups",
    "occupation_skill_relations": "occupationSkillRelations",
    "skill_skill_relations": "skillSkillRelations",
    "broader_relations_occ": "broaderRelationsOccPillar",
    "broader_relations_skill": "broaderRelationsSkillPillar",
    "skills_hierarchy": "skillsHierarchy",
}

# --------------------------------------------------------------------------
# The MNP-owned external mapping vocabulary (brief §10, §11). Mirrors
# app/db/models_career_kb_mnp.py::ExternalMappingType so the Explorer's
# review artifacts drop straight into MnpExternalMapping.
# --------------------------------------------------------------------------
MNP_MAPPING_TYPES = ("exact", "close", "broad", "narrow")
MNP_MAPPING_REVIEW_STATES = ("candidate", "confirmed", "review_required", "rejected", "unmapped")
MNP_EXTERNAL_SOURCE_SYSTEMS = ("esco", "onet", "isco", "ua_classifier")


def onet_release_dir(release: str = ONET_RELEASE) -> Path:
    """Directory that actually holds the .txt files, tolerating the
    single- vs double-nested layout different unzip tools produce."""
    for c in (
        ONET_VENDOR_DIR / f"db_{release}_text" / f"db_{release}_text",
        ONET_VENDOR_DIR / f"db_{release}_text",
    ):
        if (c / "Occupation Data.txt").exists():
            return c
    raise FileNotFoundError(
        f"O*NET release {release} not found under {ONET_VENDOR_DIR}. "
        "Run: python -m data_explorer.cli download"
    )


def esco_dir(lang: str) -> Path:
    for c in (
        ESCO_VENDOR_DIR / f"esco_{ESCO_VERSION}_classification_{lang}_csv",
        ESCO_VENDOR_DIR / "esco_x" / lang,
    ):
        if (c / f"occupations_{lang}.csv").exists():
            return c
    raise FileNotFoundError(
        f"ESCO {ESCO_VERSION} {lang} not found under {ESCO_VENDOR_DIR}. "
        "Run: python -m data_explorer.cli download"
    )
