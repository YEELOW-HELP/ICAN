"""Export hand-authored Human Expected Results to machine-readable Golden
fixtures (brief §19).

Fixtures land in `evals/golden_data_explorer/` — a sibling of
`evals/golden/`, deliberately outside it so the existing AI-task schema
test never picks them up. They have their own schema
(`evals/golden_data_explorer/schema.json`) and their own test
(`tests/data_explorer/test_golden_export.py`).

No LLM-generated expected result ever enters this pipeline.
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import asdict
from pathlib import Path

from data_explorer import config
from data_explorer.human_lab import schema
from data_explorer.io import log

SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "MNP DATA EXPLORER Golden case (deterministic Person↔Career expected result)",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "case_id", "dataset_version", "persona_id", "person_profile_snapshot",
        "expected_top_careers", "acceptable_careers", "unacceptable_careers",
        "expected_feasibility", "expected_transition_distance", "expected_gaps",
        "expected_unknowns", "expected_blockers", "methodology_version",
        "career_kb_version", "source_data_versions", "created_by", "created_at",
    ],
    "properties": {
        "case_id": {"type": "string", "pattern": "^[a-z0-9_]+$"},
        "dataset_version": {"type": "string", "pattern": "^v[0-9]+$"},
        "persona_id": {"type": "string"},
        "person_profile_snapshot": {"type": "object"},
        "expected_top_careers": {"type": "array", "items": {"type": "string"}},
        "acceptable_careers": {"type": "array", "items": {"type": "string"}},
        "unacceptable_careers": {"type": "array", "items": {"type": "string"}},
        "expected_feasibility": {"type": "object"},
        "expected_transition_distance": {"type": "object"},
        "expected_gaps": {"type": "array"},
        "expected_unknowns": {"type": "array", "items": {"type": "string"}},
        "expected_blockers": {"type": "array", "items": {"type": "string"}},
        "rationale": {"type": "string"},
        "methodology_version": {"type": "string"},
        "career_kb_version": {"type": "string"},
        "source_data_versions": {"type": "object"},
        "created_by": {"type": "string"},
        "created_at": {"type": "string"},
    },
}


def _source_versions() -> dict:
    return {
        "onet": config.ONET_RELEASE_LABEL,
        "onet_work_values": config.ONET_WORK_VALUES_LABEL,
        "esco": config.ESCO_LABEL,
        "crosswalk": config.CROSSWALK_LABEL,
    }


def export_one(person: schema.PersonProfile, expected: schema.ExpectedResult) -> dict:
    return {
        "case_id": f"de_{person.persona_id}",
        "dataset_version": "v1",
        "persona_id": person.persona_id,
        "person_profile_snapshot": asdict(person),
        "expected_top_careers": expected.expected_top_careers,
        "acceptable_careers": expected.acceptable_careers,
        "unacceptable_careers": expected.unacceptable_careers,
        "expected_feasibility": expected.expected_feasibility,
        "expected_transition_distance": expected.expected_transition_distance,
        "expected_gaps": [asdict(g) for g in expected.expected_gaps],
        "expected_unknowns": expected.expected_unknowns,
        "expected_blockers": expected.expected_blockers,
        "rationale": expected.rationale,
        "methodology_version": expected.methodology_version,
        "career_kb_version": expected.career_kb_version,
        "source_data_versions": _source_versions(),
        "created_by": expected.reviewer or person.reviewer or "unknown",
        "created_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d"),
    }


def _input_dirs() -> list[Path]:
    dirs = [config.HUMAN_LAB_EXAMPLES_DIR]
    if config.HUMAN_LAB_DIR.exists():
        dirs.append(config.HUMAN_LAB_DIR)
    return dirs


def run() -> None:
    config.GOLDEN_OUT_DIR.mkdir(parents=True, exist_ok=True)
    (config.GOLDEN_OUT_DIR / "schema.json").write_text(json.dumps(SCHEMA, indent=2) + "\n", encoding="utf-8")

    n = 0
    for base in _input_dirs():
        for person_path in sorted(base.glob("*.person.yaml")):
            stem = person_path.name[: -len(".person.yaml")]
            expected_path = base / f"{stem}.expected.yaml"
            if not expected_path.exists():
                log(f"  ! {person_path.name}: no matching {expected_path.name} — skipped")
                continue
            person = schema.load_person(person_path)
            expected = schema.load_expected(expected_path)
            if expected.persona_id != person.persona_id:
                raise SystemExit(f"{stem}: persona_id mismatch ({person.persona_id} vs {expected.persona_id})")
            case = export_one(person, expected)
            out = config.GOLDEN_OUT_DIR / f"case_{person.persona_id}.json"
            out.write_text(json.dumps(case, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            log(f"  wrote {out.relative_to(config.REPO_ROOT)}")
            n += 1
    log(f"  {n} golden case(s) exported to evals/golden_data_explorer/")
