"""Build data/data_explorer/exports/MNP_CAREER_KB_V1.xlsx from the MNP
Career KB (via data_explorer.mnp_snapshot, read-only).
"""

from __future__ import annotations

import datetime as dt

from openpyxl import Workbook
from openpyxl.styles import Font

from data_explorer import config
from data_explorer.excel._sheet import add_dropdown, add_table
from data_explorer.human_lab import schema as hl
from data_explorer.io import log
from data_explorer.mnp_snapshot import load_mnp_careers

OUT = config.EXPORT_DIR / "MNP_CAREER_KB_V1.xlsx"
DATASET_VERSION = "v1"

# review_status: the alpha KB is 100% editorial; nothing has been through a
# separate curator review workflow yet -> "editorial" everywhere. The
# column exists so a real review lifecycle drops straight in.
_REVIEW_STATES = ["editorial", "reviewed", "needs_review", "rejected", "unknown"]
_SOURCE_TYPES = ["MNP_EDITORIAL", "OFFICIAL_UA", "ESCO", "ONET", "MARKET_SOURCE", "UNKNOWN"]


def _src_type(raw: str | None) -> str:
    if not raw:
        return "UNKNOWN"
    r = raw.lower()
    if "editorial" in r or r.startswith("mnp"):
        return "MNP_EDITORIAL"
    if "esco" in r:
        return "ESCO"
    if "onet" in r or "o*net" in r:
        return "ONET"
    if "official" in r or "classifier" in r or "dsz" in r:
        return "OFFICIAL_UA"
    return "UNKNOWN"


def _review(raw: str | None) -> str:
    return "editorial" if (raw and "editorial" in raw.lower()) else "unknown"


def build(dest=None, careers=None) -> None:
    from pathlib import Path
    dest = Path(dest) if dest else OUT
    if careers is None:
        careers = load_mnp_careers()
    wb = Workbook()
    wb.remove(wb.active)
    generated_at = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")

    _readme(wb, careers, generated_at)
    _careers(wb, careers)
    _skills(wb, careers)
    _requirements(wb, careers)
    _responsibilities(wb, careers)
    _career_paths(wb, careers)
    _pros_cons(wb, careers)
    _market_data(wb, careers)
    _external_refs(wb, careers)
    _provenance(wb, careers)

    dest.parent.mkdir(parents=True, exist_ok=True)
    wb.save(dest)
    log(f"  wrote {dest}  ({len(wb.sheetnames)} sheets, {len(careers)} careers)")


# --------------------------------------------------------------------------
def _readme(wb, careers, generated_at) -> None:
    ws = wb.create_sheet("00_README")
    lines = [
        ("MNP CAREER KNOWLEDGE BASE — V1 EXPORT", True),
        (f"generated_at: {generated_at}    dataset_version: {DATASET_VERSION}    careers: {len(careers)} ACTIVE", False),
        ("", False),
        ("The production MNP Career KB (mnp_* tables) is the SINGLE SOURCE OF TRUTH.", False),
        ("This workbook is a READ / REVIEW / ANALYSIS view. It is NOT a source of truth and there is NO Excel -> DB path.", False),
        ("Rebuild: python -m data_explorer.cli export-careers-excel", False),
        ("", False),
        ("Sheets", True),
        ("10_CAREERS         one row per MNP Career (mnp_careers + mnp_career_families)", False),
        ("20_SKILLS          one row per Career<->Skill (mnp_career_skill_requirements + mnp_skills)", False),
        ("30_REQUIREMENTS    education/experience/language/certification/license/other (mnp_career_requirements)", False),
        ("40_RESPONSIBILITIES  (mnp_career_tasks — MNP_CAREER_PROFILE_SCHEMA_V1 §7)", False),
        ("50_CAREER_PATHS    career<->career prior (mnp_career_relations) — NOT a guaranteed route", False),
        ("60_PROS_CONS       (no dedicated entity in the model yet — see the finding; empty by design)", False),
        ("70_MARKET_DATA     (mnp_market_snapshots + mnp_salary_snapshots) — blank/UNKNOWN until a licensed source; NO fabricated numbers", False),
        ("80_EXTERNAL_REFS   ESCO/O*NET/ISCO/UA_CLASSIFIER references (mnp_external_mappings, entity_type=career)", False),
        ("90_PROVENANCE      why every value is in the KB — flattened source/source_version/confidence per field", False),
        ("", False),
        ("RULES: UNKNOWN != 0 (missing = blank cell). No AI. Skill names are human-readable (never a UUID).", False),
    ]
    for i, (text, bold) in enumerate(lines, start=1):
        c = ws.cell(row=i, column=1, value=text)
        if bold:
            c.font = Font(bold=True, size=12, color="1F3864")
    ws.column_dimensions["A"].width = 120


def _careers(wb, careers) -> None:
    rows = [[
        c.code, c.canonical_name_uk, c.canonical_name_en,
        c.family_name_uk or c.family_code, c.description_short_uk, c.description_long_uk,
        c.catalog_priority, c.status, c.career_profile_version, c.updated_at,
    ] for c in careers]
    add_table(wb, "10_CAREERS",
              ["career_code", "name_uk", "name_en", "category", "short_description", "long_description",
               "difficulty_level", "status", "profile_version", "updated_at"],
              rows, title="MNP Careers (source: mnp_careers / mnp_career_families)",
              note="`difficulty_level` shows catalog_priority — the model has no dedicated difficulty field yet. "
                   "long_description is blank where the KB has none.",
              widths={"short_description": 55, "long_description": 55, "name_uk": 30, "name_en": 28})


def _skills(wb, careers) -> None:
    rows = []
    for c in careers:
        for s in c.skill_requirements:
            rows.append([
                c.code, s.get("skill_code"), s["skill_uk"], s["skill_en"], s["skill_type"],
                s["requirement_level"], s["importance"], s["proficiency_level"],
                _src_type(s["source_type"]), s.get("source_reference"), _review(s["source_type"]),
            ])
    ws = add_table(wb, "20_SKILLS",
              ["career_code", "skill_code", "skill_name_uk", "skill_name_en", "skill_type",
               "requirement_level", "importance", "proficiency_level",
               "source_type", "source_reference", "review_status"],
              rows, title="Career <-> Skill (source: mnp_career_skill_requirements + mnp_skills)",
              note="skill names are human-readable. skill_code = first external reference for that skill, if any "
                   "(the alpha KB has none). UNKNOWN is never 0.",
              widths={"skill_name_uk": 34, "skill_name_en": 30})
    add_dropdown(ws, "K", _REVIEW_STATES, first_row=4)


def _requirements(wb, careers) -> None:
    rows = []
    for c in careers:
        for r in c.requirements:
            rows.append([
                c.code, r["requirement_type"], r["requirement_name"], "yes" if r["required"] else "",
                r["level"], r["description"], "yes" if r["hard_blocker"] else "",
                _src_type(r["source_type"]), r.get("source_reference"), _review(r["source_type"]),
                r.get("country"),
            ])
    ws = add_table(wb, "30_REQUIREMENTS",
              ["career_code", "requirement_type", "requirement_name", "required", "level", "description",
               "hard_blocker", "source_type", "source_reference", "review_status", "country"],
              rows, title="Requirements (source: mnp_career_requirements)",
              note="requirement_type in {education, experience, language, certification, license, other} "
                   "(the model's RequirementCategory: education|experience|credential|language|legal|other — "
                   "credential covers certification+license). hard_blocker=yes only from hardness=HARD.",
              widths={"requirement_name": 45, "description": 45})
    add_dropdown(ws, "J", _REVIEW_STATES, first_row=4)


def _responsibilities(wb, careers) -> None:
    rows = []
    for c in careers:
        for t in c.tasks:
            rows.append([c.code, t["responsibility_id"], t["title_uk"] or t["title_en"],
                         t["importance"], _src_type(t["source"]), _review(t["source"])])
    ws = add_table(wb, "40_RESPONSIBILITIES",
              ["career_code", "responsibility_id", "responsibility", "importance", "source_type", "review_status"],
              rows, title="Responsibilities (source: mnp_career_tasks — MNP_CAREER_PROFILE_SCHEMA_V1 §7)",
              widths={"responsibility": 60})
    add_dropdown(ws, "F", _REVIEW_STATES, first_row=4)


def _career_paths(wb, careers) -> None:
    rows = []
    for c in careers:
        for i, rel in enumerate(sorted(c.relations, key=lambda r: (r["relation_type"], r["to_career_code"] or "")), start=1):
            rows.append([c.code, i, rel["to_career_name_uk"], rel["relation_type"],
                         "", "", _src_type(rel["source"]), _review(rel["source"])])
    add_table(wb, "50_CAREER_PATHS",
              ["career_code", "step_order", "step_name", "step_type", "typical_experience", "description",
               "source_type", "review_status"],
              rows, title="Career paths (source: mnp_career_relations)",
              note="career<->career prior, NOT a guaranteed route. The model stores relations, not an ordered "
                   "step sequence with typical_experience — those columns are present for a future entity and are "
                   f"blank now. {'(no relations in the current KB)' if not rows else ''}",
              widths={"step_name": 35, "description": 40})


def _pros_cons(wb, careers) -> None:
    add_table(wb, "60_PROS_CONS",
              ["career_code", "type", "statement", "source_type", "review_status"],
              [], title="Pros / Cons (ADVANTAGE | DISADVANTAGE)",
              note="EMPTY BY DESIGN — the approved MNP model has no MnpCareerProsCons entity. Creating a "
                   "production table is out of scope (brief §2: do not duplicate/invent). See "
                   "docs/data_explorer/findings/CAREER_KB_ENTITY_COVERAGE_FINDING_V1.md.")


def _market_data(wb, careers) -> None:
    rows = []
    for c in careers:
        if not c.market_snapshots:
            rows.append([c.code, "UA", "", "", "", "", "", "", "", "", "", "MARKET_DATA_LIMITED",
                         "", "", ""])
            continue
        for m in c.market_snapshots:
            rows.append([
                c.code, m["country"], m["region"], "", m["vacancy_count"], m["salary_median"],
                m["salary_p25"], m["salary_p75"], m["currency"], m["demand_trend"], m["demand_trend"],
                m["data_quality"], m["remote_share"], m["source"], m["collected_at"],
            ])
    add_table(wb, "70_MARKET_DATA",
              ["career_code", "country", "region", "city", "vacancy_count", "salary_median",
               "salary_min", "salary_max", "currency", "demand_level", "trend", "data_quality",
               "remote_share", "source", "collected_at"],
              rows, title="Market data (source: mnp_market_snapshots + mnp_salary_snapshots)",
              note="NO fabricated numbers. The alpha KB has zero market snapshots -> every career is "
                   "MARKET_DATA_LIMITED and every metric is blank. `salary_min/max` map to the model's p25/p75; "
                   "`city` / `demand_level` have no model field yet.",
              widths={"source": 22})


def _external_refs(wb, careers) -> None:
    rows = []
    for c in careers:
        for em in c.external_mappings:
            rows.append([c.code, em["source_system"], em["external_id"], em["external_label"],
                         em["mapping_type"], "candidate", em["confidence"], "", ""])
    add_table(wb, "80_EXTERNAL_REFS",
              ["career_code", "external_system", "external_id", "external_label", "mapping_type",
               "mapping_status", "confidence", "reviewed_by", "reviewed_at"],
              rows, title="External references (source: mnp_external_mappings, entity_type=career)",
              note="external_system in {ESCO, ONET, ISCO, UA_CLASSIFIER}. mapping_type in {exact, close, broad, "
                   "narrow}. `mapping_status` / `reviewed_by` / `reviewed_at` have no model field yet — shown as "
                   f"'candidate' / blank. {'(no career external mappings in the current KB)' if not rows else ''}",
              widths={"external_id": 45, "external_label": 30})


def _provenance(wb, careers) -> None:
    """One row per (career, entity_type, entity_id, field) that carries a
    source — 'why is this value in the KB'."""
    rows = []

    def add(code, etype, eid, fields: dict, source, source_version, review):
        for fname, _val in fields.items():
            rows.append([code, etype, eid, fname, _src_type(source), source or "",
                         source_version or "", review])

    for c in careers:
        add(c.code, "career", c.id,
            {"short_description": 1, "long_description": 1, "category": 1},
            "mnp_editorial_v1", None, "editorial")
        for s in c.skill_requirements:
            add(c.code, "career_skill", s["entity_id"],
                {"importance": 1, "required_level": 1, "requirement_type": 1},
                s["source_type"], s["source_reference"], _review(s["source_type"]))
        for r in c.requirements:
            add(c.code, "career_requirement", r["entity_id"],
                {"description": 1, "hardness": 1, "value": 1},
                r["source_type"], r["source_version"], _review(r["source_type"]))
        for t in c.tasks:
            add(c.code, "career_task", t["entity_id"], {"title": 1, "importance": 1},
                t["source"], t["source_version"], _review(t["source"]))
        for at in c.attributes:
            add(c.code, "career_attribute", at["entity_id"], {f"{at['group']}.{at['key']}": 1},
                at["source"], None, _review(at["source"]))
        for em in c.external_mappings:
            add(c.code, "career_external_mapping", em["entity_id"],
                {"mapping_type": 1, "confidence": 1}, em["source_system"], em["source_version"], "candidate")
        for m in c.market_snapshots:
            add(c.code, "market_snapshot", m["entity_id"], {"vacancy_count": 1, "salary_median": 1},
                m["source"], m["source_version"], "market")

    rows.sort()
    add_table(wb, "90_PROVENANCE",
              ["career_code", "entity_type", "entity_id", "field_name", "source_type",
               "source_reference", "source_version", "review_status"],
              rows, title="Provenance — why each value is in the Career KB",
              note="Provenance is NOT a separate table in the model: every KB row carries its own "
                   "source / source_version / confidence. This sheet flattens them per field. "
                   "source_type in {MNP_EDITORIAL, OFFICIAL_UA, ESCO, ONET, MARKET_SOURCE, UNKNOWN}.",
              widths={"entity_id": 38, "source_reference": 20})
