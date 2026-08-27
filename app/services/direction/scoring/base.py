"""Shared types for the four-output scoring engine.

Deliberately decoupled from SQLAlchemy models: a `ScoreContext` is built by
the orchestrator (Slice 2) from `CareerDetails` + mapped claims; Slice 1
tests build it directly. This keeps every scorer a pure function over
plain data.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from app.db.models_direction import OutputFamily, QualitativeBand, ScoreComponentStatus
from app.services.direction.dimension_mapping import MappedClaim

__all__ = [
    "OutputFamily",
    "QualitativeBand",
    "ScoreComponentStatus",
    "CareerSkillRef",
    "CareerRequirementRef",
    "ScoreContext",
    "ScoreComponentResult",
    "insufficient",
    "not_applicable",
]

# Career characteristic keys carried on `Career` (Stage 3A). All nullable:
# an uncurated characteristic is absent, never a fabricated midpoint.
CAREER_CHARACTERISTIC_KEYS = (
    "works_with_people",
    "works_with_data",
    "works_with_technology",
    "creative_component",
    "analytical_component",
    "autonomy_level",
    "structure_routine_level",
)

# Work-context keys carried on `CareerWorkContext` (Stage 3A).
WORK_CONTEXT_KEYS = (
    "setting",
    "indoor_outdoor",
    "travel_required",
    "shift_work",
    "physical_intensity",
    "teamwork_level",
    "customer_interaction_level",
    "client_facing",
    "repetitive_vs_varied",
    "schedule_predictability",
    "responsibility_level",
    "stress_level",
)


@dataclass(frozen=True)
class CareerSkillRef:
    term_key: str
    requirement_type: str  # "required" | "preferred" | "useful"


@dataclass(frozen=True)
class CareerRequirementRef:
    category: str  # RequirementCategory.value
    certainty: str  # RequirementCertainty.value


@dataclass(frozen=True)
class ScoreContext:
    mapped_claims: tuple[MappedClaim, ...]
    career_code: str
    career_domain: str
    career_characteristics: dict[str, float | None] = field(default_factory=dict)
    work_context: dict[str, object | None] = field(default_factory=dict)
    career_skills: tuple[CareerSkillRef, ...] = ()
    career_requirements: tuple[CareerRequirementRef, ...] = ()


@dataclass(frozen=True)
class ScoreComponentResult:
    component_key: str
    family: OutputFamily
    status: ScoreComponentStatus
    raw_score: float | None
    rationale: str
    contributing_claim_ids: tuple[uuid.UUID, ...] = ()
    contributing_career_attributes: dict = field(default_factory=dict)


def insufficient(component_key: str, family: OutputFamily, reason: str, **attrs) -> ScoreComponentResult:
    return ScoreComponentResult(
        component_key=component_key,
        family=family,
        status=ScoreComponentStatus.INSUFFICIENT_DATA,
        raw_score=None,
        rationale=reason,
        contributing_career_attributes=dict(attrs),
    )


def not_applicable(component_key: str, family: OutputFamily, reason: str) -> ScoreComponentResult:
    return ScoreComponentResult(
        component_key=component_key,
        family=family,
        status=ScoreComponentStatus.NOT_APPLICABLE,
        raw_score=None,
        rationale=reason,
    )


def _claims_for(ctx: ScoreContext, canonical_dimension, *, exclude_contradicted: bool = True) -> list[MappedClaim]:
    from app.services.direction.dimension_mapping import MappingStatus

    out = []
    for mc in ctx.mapped_claims:
        if mc.status is not MappingStatus.MAPPED:
            continue
        if mc.canonical_dimension is not canonical_dimension:
            continue
        if exclude_contradicted and mc.claim_status == "contradicted":
            continue
        out.append(mc)
    return out
