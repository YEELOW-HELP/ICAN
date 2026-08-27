"""Founder decisions G + Q: the deterministic Hard Constraint Gate.

- v0.1 derivation classifies subtype only; every derived constraint is
  SOFT unless the caller explicitly allow-lists it as hard+confirmed.
- A BLOCK requires hard+confirmed AND a HARD_FACTUAL career requirement.
- TYPICAL_RECOMMENDATION NEVER hard-blocks.
- Career-side data absent -> INSUFFICIENT_DATA (unknown is not a violation).
"""

import uuid

from app.db.models_knowledge import CareerRequirement, RequirementCategory, RequirementCertainty
from app.db.models_direction import ConstraintCheckResult
from app.services.direction.constraints import (
    CONSTRAINT_SUBTYPES,
    derive_profile_constraints,
    gate_blocks,
    run_hard_constraint_gate,
)
from app.services.direction.dimensions import CanonicalDimension
from tests.direction_test_helpers import mapped


def _req(category, certainty, description="req"):
    return CareerRequirement(
        career_id=uuid.uuid4(), category=category, description=description, certainty=certainty
    )


def _constraint_claim(term_key=None, normalized_value="val"):
    return mapped(
        CanonicalDimension.CONSTRAINTS,
        term_key=term_key,
        normalized_value=normalized_value,
        legacy_dimension="constraint",
    )


def test_taxonomy_has_exactly_twelve_subtypes():
    assert len(CONSTRAINT_SUBTYPES) == 12
    assert set(CONSTRAINT_SUBTYPES) == {
        "time", "financial", "geography", "mobility", "work_schedule", "work_format",
        "language", "education", "credential", "legal", "family_logistics", "functional",
    }


def test_derivation_defaults_every_constraint_to_soft():
    claims = [
        _constraint_claim(term_key="location_constraint"),
        _constraint_claim(normalized_value="I cannot obtain a professional license"),
    ]
    specs = derive_profile_constraints(claims)
    assert len(specs) == 2
    assert all(not s.is_hard and not s.is_confirmed for s in specs)
    assert {s.constraint_subtype for s in specs} == {"geography", "credential"}


def test_derivation_only_marks_hard_when_caller_allow_lists_the_claim():
    claim = _constraint_claim(normalized_value="I cannot obtain the required license")
    specs = derive_profile_constraints([claim], hard_confirmed_claim_ids={claim.source_claim_id})
    assert len(specs) == 1
    assert specs[0].is_hard and specs[0].is_confirmed
    assert specs[0].constraint_subtype == "credential"


def test_hard_confirmed_constraint_blocks_only_with_hard_factual_requirement():
    claim = _constraint_claim(normalized_value="cannot obtain required license")
    specs = derive_profile_constraints([claim], hard_confirmed_claim_ids={claim.source_claim_id})

    outcomes = run_hard_constraint_gate(
        specs,
        career_ref="regulated_job",
        career_requirements=[_req(RequirementCategory.LICENSE, RequirementCertainty.HARD_FACTUAL, "State license required")],
    )
    assert len(outcomes) == 1
    assert outcomes[0].result is ConstraintCheckResult.BLOCK
    assert gate_blocks(outcomes) is True


def test_typical_recommendation_never_blocks():
    claim = _constraint_claim(normalized_value="cannot obtain required license")
    specs = derive_profile_constraints([claim], hard_confirmed_claim_ids={claim.source_claim_id})

    outcomes = run_hard_constraint_gate(
        specs,
        career_ref="soft_job",
        career_requirements=[
            _req(RequirementCategory.LICENSE, RequirementCertainty.TYPICAL_RECOMMENDATION, "a license is typically expected")
        ],
    )
    assert outcomes[0].result is ConstraintCheckResult.INSUFFICIENT_DATA
    assert gate_blocks(outcomes) is False


def test_missing_career_side_data_is_insufficient_not_a_block():
    claim = _constraint_claim(normalized_value="cannot obtain required license")
    specs = derive_profile_constraints([claim], hard_confirmed_claim_ids={claim.source_claim_id})
    outcomes = run_hard_constraint_gate(specs, career_ref="unknown_job", career_requirements=[])
    assert outcomes[0].result is ConstraintCheckResult.INSUFFICIENT_DATA
    assert gate_blocks(outcomes) is False


def test_soft_only_subtype_even_when_hard_confirmed_does_not_block():
    claim = _constraint_claim(term_key="schedule_constraint", normalized_value="fixed hours only")
    specs = derive_profile_constraints([claim], hard_confirmed_claim_ids={claim.source_claim_id})
    assert specs[0].constraint_subtype == "work_schedule"
    outcomes = run_hard_constraint_gate(
        specs,
        career_ref="shift_job",
        career_requirements=[_req(RequirementCategory.PHYSICAL_ENVIRONMENTAL, RequirementCertainty.HARD_FACTUAL)],
    )
    assert outcomes[0].result is ConstraintCheckResult.PASS  # soft-only subtype -> no hard block path
    assert gate_blocks(outcomes) is False


def test_soft_constraints_are_not_processed_by_the_gate():
    claim = _constraint_claim(normalized_value="cannot obtain required license")
    specs = derive_profile_constraints([claim])  # no allow-list -> soft
    outcomes = run_hard_constraint_gate(
        specs,
        career_ref="x",
        career_requirements=[_req(RequirementCategory.LICENSE, RequirementCertainty.HARD_FACTUAL)],
    )
    assert outcomes == []
