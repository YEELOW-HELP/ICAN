"""Validates the golden-dataset structure introduced in Sprint 0 Part 5
(evals/golden/). This is deliberately the only automated check for that
directory right now -- no eval runner exists yet (out of scope for Part 5).
It just proves every case file is well-formed and internally consistent
before any future runner is built on top of it."""

import json
from pathlib import Path

import jsonschema
import pytest

GOLDEN_DIR = Path(__file__).resolve().parent.parent / "evals" / "golden"
SCHEMA_PATH = GOLDEN_DIR / "schema.json"


def _case_files() -> list[Path]:
    return sorted(p for p in GOLDEN_DIR.rglob("*.json") if p != SCHEMA_PATH)


@pytest.fixture(scope="module")
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def test_schema_file_itself_is_valid_json_schema(schema):
    jsonschema.Draft202012Validator.check_schema(schema)


def test_golden_dataset_has_case_files():
    assert len(_case_files()) > 0, "expected at least the Part 5 example cases under evals/golden/v1/"


@pytest.mark.parametrize("case_path", _case_files(), ids=lambda p: p.stem)
def test_case_matches_schema(case_path: Path, schema):
    case = json.loads(case_path.read_text(encoding="utf-8"))
    jsonschema.validate(instance=case, schema=schema)


@pytest.mark.parametrize("case_path", _case_files(), ids=lambda p: p.stem)
def test_case_id_matches_filename(case_path: Path):
    case = json.loads(case_path.read_text(encoding="utf-8"))
    assert case["case_id"] == case_path.stem, (
        f"{case_path} has case_id={case['case_id']!r}, expected it to match the filename"
    )


@pytest.mark.parametrize("case_path", _case_files(), ids=lambda p: p.stem)
def test_case_dataset_version_matches_its_folder(case_path: Path):
    case = json.loads(case_path.read_text(encoding="utf-8"))
    version_folder = case_path.relative_to(GOLDEN_DIR).parts[0]
    assert case["dataset_version"] == version_folder, (
        f"{case_path} has dataset_version={case['dataset_version']!r} but lives under {version_folder}/"
    )


def test_case_ids_are_unique_across_the_dataset():
    ids = []
    for path in _case_files():
        case = json.loads(path.read_text(encoding="utf-8"))
        ids.append(case["case_id"])
    assert len(ids) == len(set(ids)), "duplicate case_id found across evals/golden/"


def test_no_case_is_marked_approved_without_a_reviewer():
    """A case can't be status=approved with reviewed_by.role still null --
    that would mean nothing actually reviewed it. Catches a real class of
    mistake once cases start getting approved by future contributors."""
    for path in _case_files():
        case = json.loads(path.read_text(encoding="utf-8"))
        if case["status"] == "approved":
            assert case["reviewed_by"]["role"], f"{path} is approved but has no reviewed_by.role"
