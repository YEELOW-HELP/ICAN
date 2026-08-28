"""Matching V1 M4 -- pure feasibility unit tests, no DB (Founder Review
test items #15-19)."""

from app.services.matching.config import MatchingConfig
from app.services.matching.pure import (
    CareerRequirementInput,
    CareerSkillInput,
    ConstraintAnswer,
    compute_feasibility,
)

CONFIG = MatchingConfig()


def test_hard_feasibility_requirement_can_block():
    """#15 -- explicit user hard constraint (no license) + authoritative
    (HARD_FACTUAL) incompatible career requirement -> BLOCKED."""
    constraints = {"credential_legal": ConstraintAnswer("credential_legal", boolean_value=False)}
    requirements = [CareerRequirementInput(category="license", certainty="hard_factual", description="State nursing license required by law")]
    result = compute_feasibility(
        constraints=constraints, career_requirements=requirements, career_skills=[],
        career_work_format_setting=None, job_zone=None, config=CONFIG,
    )
    assert result.status == "blocked"
    assert result.raw_score is None
    assert len(result.hard_barriers) == 1


def test_soft_requirement_does_not_hard_block():
    """#16."""
    constraints = {"credential_legal": ConstraintAnswer("credential_legal", boolean_value=False)}
    requirements = [CareerRequirementInput(category="license", certainty="typical_recommendation", description="A license is typically expected")]
    result = compute_feasibility(
        constraints=constraints, career_requirements=requirements, career_skills=[],
        career_work_format_setting=None, job_zone=4, config=CONFIG,
    )
    assert result.status != "blocked"
    assert result.hard_barriers == ()
    assert len(result.soft_barriers) == 1


def test_typical_recommendation_never_hard_blocks():
    """#17 -- exhaustively, for every hard-block-eligible category."""
    constraints = {"credential_legal": ConstraintAnswer("credential_legal", boolean_value=False)}
    for category in ("license", "certification", "legal_regulatory"):
        requirements = [CareerRequirementInput(category=category, certainty="typical_recommendation", description="x")]
        result = compute_feasibility(
            constraints=constraints, career_requirements=requirements, career_skills=[],
            career_work_format_setting=None, job_zone=None, config=CONFIG,
        )
        assert result.status != "blocked", f"{category} incorrectly hard-blocked"
        assert result.hard_barriers == ()


def test_missing_user_skill_stays_unknown():
    """#18 -- a required career skill with no comparable user data is
    UNKNOWN, never inferred as CONFIRMED_MISSING."""
    skills = [CareerSkillInput(label="Python programming", requirement_type="required")]
    result = compute_feasibility(
        constraints={}, career_requirements=[], career_skills=skills,
        career_work_format_setting=None, job_zone=None, config=CONFIG,
    )
    assert len(result.skills_to_verify) == 1
    assert result.skills_to_verify[0].status == "unknown"
    assert result.skills_to_verify[0].label == "Python programming"


def test_confirmed_missing_skill_represented_correctly():
    """#19 -- the SkillCheck status vocabulary supports CONFIRMED_MISSING
    even though M4's V1 engine never emits it (no shared user<->career
    skill taxonomy exists yet, per M3's honest limitation) -- the shape
    is reusable once that taxonomy exists, per Founder Review §10's
    "preserve PRESENT/CONFIRMED_MISSING/UNKNOWN where old safe semantics
    remain reusable"."""
    from app.services.matching.pure import SKILL_CONFIRMED_MISSING, SKILL_PRESENT, SKILL_UNKNOWN, SkillCheck

    check = SkillCheck(label="Welding", status=SKILL_CONFIRMED_MISSING)
    assert check.status == SKILL_CONFIRMED_MISSING
    assert {SKILL_PRESENT, SKILL_CONFIRMED_MISSING, SKILL_UNKNOWN} == {"present", "confirmed_missing", "unknown"}


def test_unknown_certainty_never_a_barrier_or_gap():
    """Extra guard: UNKNOWN certainty requirements never produce any
    barrier or information gap -- too uncertain to assert anything from."""
    constraints = {"credential_legal": ConstraintAnswer("credential_legal", boolean_value=False)}
    requirements = [CareerRequirementInput(category="license", certainty="unknown", description="x")]
    result = compute_feasibility(
        constraints=constraints, career_requirements=requirements, career_skills=[],
        career_work_format_setting=None, job_zone=None, config=CONFIG,
    )
    assert result.hard_barriers == ()
    assert result.soft_barriers == ()
    assert result.information_gaps == ()


def test_insufficient_data_when_no_career_data_at_all():
    result = compute_feasibility(
        constraints={}, career_requirements=[], career_skills=[],
        career_work_format_setting=None, job_zone=None, config=CONFIG,
    )
    assert result.status == "insufficient_data"
    assert result.raw_score is None
