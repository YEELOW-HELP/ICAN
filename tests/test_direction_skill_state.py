"""Founder decision P: PRESENT / CONFIRMED_MISSING / UNKNOWN.
`UNKNOWN != NEGATIVE`. A required skill absent from profile claims is
UNKNOWN, never CONFIRMED_MISSING.
"""

from app.services.direction.dimensions import CanonicalDimension
from app.services.direction.scoring.skill_state import (
    SkillState,
    classify_required_skills,
)
from tests.direction_test_helpers import mapped


def _skill(term_key, *, claim_status="supported", normalized_value="val"):
    return mapped(
        CanonicalDimension.SKILLS,
        term_key=term_key,
        claim_status=claim_status,
        normalized_value=normalized_value,
        legacy_dimension="skill",
    )


def test_absent_required_skill_is_unknown_not_confirmed_missing():
    result = {c.term_key: c.state for c in classify_required_skills(["python", "sql"], [])}
    assert result == {"python": SkillState.UNKNOWN, "sql": SkillState.UNKNOWN}


def test_supported_matching_claim_is_present():
    result = classify_required_skills(["python"], [_skill("python")])
    assert result[0].state is SkillState.PRESENT


def test_contradicted_matching_claim_is_confirmed_missing():
    result = classify_required_skills(["python"], [_skill("python", claim_status="contradicted")])
    assert result[0].state is SkillState.CONFIRMED_MISSING


def test_explicit_negation_is_confirmed_missing():
    result = classify_required_skills(
        ["python"], [_skill("python", claim_status="hypothesis", normalized_value="has no experience with Python")]
    )
    assert result[0].state is SkillState.CONFIRMED_MISSING


def test_weak_hypothesis_without_negation_stays_unknown():
    result = classify_required_skills(
        ["python"], [_skill("python", claim_status="hypothesis", normalized_value="maybe knows some Python")]
    )
    assert result[0].state is SkillState.UNKNOWN


def test_mixed_set():
    claims = [
        _skill("python"),
        _skill("sql", claim_status="contradicted"),
    ]
    result = {c.term_key: c.state for c in classify_required_skills(["python", "sql", "docker", "kubernetes"], claims)}
    assert result == {
        "python": SkillState.PRESENT,
        "sql": SkillState.CONFIRMED_MISSING,
        "docker": SkillState.UNKNOWN,
        "kubernetes": SkillState.UNKNOWN,
    }
