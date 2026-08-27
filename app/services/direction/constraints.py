"""Deterministic Hard Constraint Gate + `ProfileConstraint` derivation
(Founder decisions G + Q, Career Fit / Direction Evaluation Model
section 5).

Non-negotiable properties:
- The gate is PURE and DETERMINISTIC. No LLM decides whether a confirmed
  hard constraint is violated.
- A hard BLOCK requires BOTH (1) an explicit, supported user constraint
  marked hard AND confirmed, and (2) an authoritative, machine-readable
  incompatible career fact -- a `CareerRequirement` with
  `certainty == HARD_FACTUAL`.
- `CareerRequirement.certainty == TYPICAL_RECOMMENDATION` NEVER
  hard-blocks (Founder decision G, Stage 3A write-path contract).
- v0.1 does NOT auto-classify a constraint claim as hard from assessment
  text -- `is_hard` / `is_confirmed` default False and are set only by an
  explicit caller-supplied allow-list. The gate fully supports
  `is_hard=True` (fixtures); on current seed data it never fires.
- 12 constraint subtypes (Founder decision Q). Time/financial are subtypes
  of Constraints, not new dimensions.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from app.db.models_direction import ConstraintCheckResult
from app.db.models_knowledge import CareerRequirement, RequirementCategory, RequirementCertainty
from app.services.direction.dimension_mapping import MappedClaim, MappingStatus
from app.services.direction.dimensions import CanonicalDimension
from app.services.direction.versions import CONSTRAINT_TAXONOMY_VERSION

__all__ = [
    "CONSTRAINT_SUBTYPES",
    "CONSTRAINT_TAXONOMY",
    "CONSTRAINT_TAXONOMY_VERSION",
    "ProfileConstraintSpec",
    "ConstraintCheckOutcome",
    "derive_profile_constraints",
    "run_hard_constraint_gate",
    "gate_blocks",
]

# The 12 v0.1 constraint subtypes (MNP-HPM section 3.3, Founder decision Q).
CONSTRAINT_SUBTYPES: tuple[str, ...] = (
    "time",
    "financial",
    "geography",
    "mobility",
    "work_schedule",
    "work_format",
    "language",
    "education",
    "credential",
    "legal",
    "family_logistics",
    "functional",
)


@dataclass(frozen=True)
class _SubtypeEntry:
    hard_block_capable: bool
    requirement_categories: tuple[RequirementCategory, ...]  # career-side HARD_FACTUAL categories
    soft_work_context_attrs: tuple[str, ...]  # recorded, not gated in Slice 1


CONSTRAINT_TAXONOMY: dict[str, _SubtypeEntry] = {
    "time": _SubtypeEntry(False, (), ("schedule_predictability",)),
    "financial": _SubtypeEntry(False, (), ()),
    "geography": _SubtypeEntry(False, (), ("setting",)),
    "mobility": _SubtypeEntry(False, (), ("travel_required",)),
    "work_schedule": _SubtypeEntry(False, (), ("shift_work", "schedule_predictability")),
    "work_format": _SubtypeEntry(False, (), ("setting",)),
    "language": _SubtypeEntry(True, (RequirementCategory.LANGUAGE,), ()),
    "education": _SubtypeEntry(True, (RequirementCategory.EDUCATION,), ()),
    "credential": _SubtypeEntry(True, (RequirementCategory.CERTIFICATION, RequirementCategory.LICENSE), ()),
    "legal": _SubtypeEntry(True, (RequirementCategory.LEGAL_REGULATORY,), ()),
    "family_logistics": _SubtypeEntry(False, (), ("schedule_predictability", "travel_required")),
    "functional": _SubtypeEntry(True, (RequirementCategory.PHYSICAL_ENVIRONMENTAL,), ()),
}

# Deterministic classification of a constraint claim into a subtype BUCKET.
# Picks the bucket only -- never sets hardness.
_LEGACY_TERM_TO_SUBTYPE: dict[str, str] = {
    "location_constraint": "geography",
    "schedule_constraint": "work_schedule",
    "income_requirement": "financial",
    "family_responsibilities": "family_logistics",
}

# Substring patterns (lowercased) -> subtype, checked when term_key gives nothing.
_KEYWORD_TO_SUBTYPE: tuple[tuple[tuple[str, ...], str], ...] = (
    (("night shift", "нічн", "ночн", "shift work"), "work_schedule"),
    (("relocat", "переїзд", "переезд", "cannot move", "cannot relocate"), "geography"),
    (("remote", "віддален", "удалён", "from home", "office only"), "work_format"),
    (("travel", "відрядж", "командиров"), "mobility"),
    (("licen", "ліценз", "лиценз", "certif", "сертиф"), "credential"),
    (("diploma", "degree", "диплом", "вищу освіт", "высшее образован"), "education"),
    (("language", "мова", "язык", "англійськ", "англ."), "language"),
    (("visa", "permit", "work authorization", "дозвіл на роботу", "громадянств"), "legal"),
    (("lifting", "heavy", "physical", "фізичн", "физическ", "standing all day"), "functional"),
    (("hours", "part-time", "part time", "годин", "часов", "time available"), "time"),
    (("money", "salary floor", "income", "фінанс", "доход", "зарплат"), "financial"),
    (("childcare", "kids", "діт", "дет", "family", "сім'ї", "семьи"), "family_logistics"),
)


@dataclass(frozen=True)
class ProfileConstraintSpec:
    """In-memory result of deriving one `ProfileConstraint` from a
    constraint-dimension claim. Mirrors the `ProfileConstraint` model 1:1
    so the orchestrator (Slice 2) can persist it directly."""

    source_claim_id: uuid.UUID | None
    constraint_subtype: str
    constraint_taxonomy_version: str
    normalized_value: str
    is_hard: bool
    is_confirmed: bool
    confidence: float


@dataclass(frozen=True)
class ConstraintCheckOutcome:
    """One (constraint, career) gate result -- mirrors `DirectionConstraintCheck`."""

    source_claim_id: uuid.UUID | None
    constraint_subtype: str
    career_ref: str
    career_attribute_ref: str | None
    result: ConstraintCheckResult
    is_hard: bool
    explanation: str


def _classify_subtype(term_key: str | None, normalized_value: str) -> str | None:
    if term_key and term_key in CONSTRAINT_SUBTYPES:
        return term_key
    if term_key and term_key in _LEGACY_TERM_TO_SUBTYPE:
        return _LEGACY_TERM_TO_SUBTYPE[term_key]
    haystack = (normalized_value or "").lower()
    for needles, subtype in _KEYWORD_TO_SUBTYPE:
        if any(n in haystack for n in needles):
            return subtype
    return None


def derive_profile_constraints(
    mapped_claims: Sequence[MappedClaim],
    *,
    hard_confirmed_claim_ids: set[uuid.UUID] | None = None,
) -> list[ProfileConstraintSpec]:
    """Derive matchable constraint specs from mapped claims whose canonical
    dimension is CONSTRAINTS.

    `hard_confirmed_claim_ids` is the ONLY way a spec gets
    `is_hard=is_confirmed=True` in v0.1 -- an explicit allow-list supplied
    by the caller (a future consultant confirmation / structured
    assessment field). Absent it, every derived constraint is soft
    (Founder decision G, Career Fit / Direction Evaluation Model 5.4).
    """
    hard_confirmed = hard_confirmed_claim_ids or set()
    specs: list[ProfileConstraintSpec] = []
    for mc in mapped_claims:
        if mc.canonical_dimension is not CanonicalDimension.CONSTRAINTS:
            continue
        if mc.status is MappingStatus.UNMAPPED:
            continue
        subtype = _classify_subtype(mc.legacy_term_key, mc.normalized_value)
        if subtype is None:
            continue  # could not place in the v0.1 taxonomy -- coverage gap, never guessed
        is_hard = mc.source_claim_id in hard_confirmed
        specs.append(
            ProfileConstraintSpec(
                source_claim_id=mc.source_claim_id,
                constraint_subtype=subtype,
                constraint_taxonomy_version=CONSTRAINT_TAXONOMY_VERSION,
                normalized_value=mc.normalized_value,
                is_hard=is_hard,
                is_confirmed=is_hard,
                confidence=mc.claim_confidence,
            )
        )
    return specs


def run_hard_constraint_gate(
    constraints: Sequence[ProfileConstraintSpec],
    *,
    career_ref: str,
    career_requirements: Sequence[CareerRequirement],
) -> list[ConstraintCheckOutcome]:
    """Deterministic. Returns one outcome per hard+confirmed constraint
    considered. Soft (non-hard / non-confirmed) constraints are NOT
    processed here (Career Fit / Direction Evaluation Model 5.3)."""
    outcomes: list[ConstraintCheckOutcome] = []
    hard_factual_by_category: dict[RequirementCategory, list[CareerRequirement]] = {}
    for req in career_requirements:
        if req.certainty == RequirementCertainty.HARD_FACTUAL:
            hard_factual_by_category.setdefault(req.category, []).append(req)

    for spec in constraints:
        if not (spec.is_hard and spec.is_confirmed):
            continue

        entry = CONSTRAINT_TAXONOMY.get(spec.constraint_subtype)
        if entry is None or not entry.hard_block_capable:
            outcomes.append(
                ConstraintCheckOutcome(
                    source_claim_id=spec.source_claim_id,
                    constraint_subtype=spec.constraint_subtype,
                    career_ref=career_ref,
                    career_attribute_ref=(entry.soft_work_context_attrs[0] if entry and entry.soft_work_context_attrs else None),
                    result=ConstraintCheckResult.PASS,
                    is_hard=True,
                    explanation=(
                        f"'{spec.constraint_subtype}' is a soft-only constraint subtype in v0.1 "
                        "(no HARD_FACTUAL career-side counterpart defined); hard block not applicable."
                    ),
                )
            )
            continue

        matching: list[CareerRequirement] = []
        matched_category: RequirementCategory | None = None
        for category in entry.requirement_categories:
            reqs = hard_factual_by_category.get(category, [])
            if reqs:
                matching = reqs
                matched_category = category
                break

        if not matching:
            cats = "/".join(c.value for c in entry.requirement_categories)
            outcomes.append(
                ConstraintCheckOutcome(
                    source_claim_id=spec.source_claim_id,
                    constraint_subtype=spec.constraint_subtype,
                    career_ref=career_ref,
                    career_attribute_ref=f"career_requirement.{cats}",
                    result=ConstraintCheckResult.INSUFFICIENT_DATA,
                    is_hard=True,
                    explanation=(
                        f"User has a confirmed hard constraint '{spec.constraint_subtype}', but the career "
                        f"has no HARD_FACTUAL requirement in category '{cats}'. Unknown is not a violation "
                        "(Evidence Standard section 3)."
                    ),
                )
            )
            continue

        outcomes.append(
            ConstraintCheckOutcome(
                source_claim_id=spec.source_claim_id,
                constraint_subtype=spec.constraint_subtype,
                career_ref=career_ref,
                career_attribute_ref=f"career_requirement.{matched_category.value}",
                result=ConstraintCheckResult.BLOCK,
                is_hard=True,
                explanation=(
                    f"Confirmed hard constraint '{spec.constraint_subtype}' is incompatible with a HARD_FACTUAL "
                    f"career requirement in category '{matched_category.value}' (source-backed): "
                    f"{matching[0].description[:160]}"
                ),
            )
        )
    return outcomes


def gate_blocks(outcomes: Sequence[ConstraintCheckOutcome]) -> bool:
    """True iff at least one confirmed hard constraint produced a BLOCK --
    the direction is then removed from recommendation eligibility
    regardless of any score (Career Fit / Direction Evaluation Model 2)."""
    return any(o.result == ConstraintCheckResult.BLOCK and o.is_hard for o in outcomes)
