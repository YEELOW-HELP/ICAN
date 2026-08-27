"""Skill-state classification -- `PRESENT` / `CONFIRMED_MISSING` /
`UNKNOWN` (Founder decision P).

`UNKNOWN != NEGATIVE`. A required `CareerSkill` absent from all profile
claims is `UNKNOWN`, never `CONFIRMED_MISSING`. Only `CONFIRMED_MISSING`
skills are true Skill Gaps. `UNKNOWN` required skills become
`skills_to_verify` -- information gaps, not penalties. Lack of competence
is never inferred from missing profile data.
"""

from __future__ import annotations

import enum
from collections.abc import Sequence
from dataclasses import dataclass

from app.services.direction.dimension_mapping import MappedClaim, MappingStatus

__all__ = ["SkillState", "SkillClassification", "classify_required_skills"]

# Explicit-negation phrases that turn a matching claim into CONFIRMED_MISSING.
_NEGATION_MARKERS = (
    "no experience",
    "never used",
    "don't know",
    "do not know",
    "cannot",
    "not familiar",
    "lack ",
    "insufficient level",
    "beginner only",
    "не вмію",
    "не знаю",
    "немає досвіду",
    "не працював",
    "не використовував",
    "не умею",
    "нет опыта",
)


class SkillState(str, enum.Enum):
    PRESENT = "present"
    CONFIRMED_MISSING = "confirmed_missing"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SkillClassification:
    term_key: str
    state: SkillState
    rationale: str


def _skill_claims_by_term(mapped_claims: Sequence[MappedClaim]) -> dict[str, list[MappedClaim]]:
    from app.services.direction.dimensions import CanonicalDimension

    by_term: dict[str, list[MappedClaim]] = {}
    for mc in mapped_claims:
        if mc.status is not MappingStatus.MAPPED:
            continue
        if mc.canonical_dimension is not CanonicalDimension.SKILLS:
            continue
        if not mc.legacy_term_key:
            continue
        by_term.setdefault(mc.legacy_term_key, []).append(mc)
    return by_term


def classify_required_skills(
    required_skill_term_keys: Sequence[str],
    mapped_claims: Sequence[MappedClaim],
) -> list[SkillClassification]:
    """One classification per required skill. A skill with no matching
    profile claim at all is `UNKNOWN` (Founder decision P)."""
    by_term = _skill_claims_by_term(mapped_claims)
    out: list[SkillClassification] = []
    for term_key in required_skill_term_keys:
        claims = by_term.get(term_key, [])
        if not claims:
            out.append(
                SkillClassification(term_key, SkillState.UNKNOWN, "no profile claim mentions this skill")
            )
            continue

        # CONFIRMED_MISSING: a CONTRADICTED matching claim, or an explicit negation.
        contradicted = any(c.claim_status == "contradicted" for c in claims)
        negated = any(
            any(marker in (c.normalized_value or "").lower() for marker in _NEGATION_MARKERS) for c in claims
        )
        if contradicted or negated:
            out.append(
                SkillClassification(
                    term_key,
                    SkillState.CONFIRMED_MISSING,
                    "explicit evidence the user lacks this skill or has an insufficient level",
                )
            )
            continue

        # PRESENT: a SUPPORTED matching claim.
        if any(c.claim_status == "supported" for c in claims):
            out.append(SkillClassification(term_key, SkillState.PRESENT, "supported matching skill claim"))
            continue

        # A matching claim exists but is only a hypothesis / insufficient -> still UNKNOWN.
        out.append(
            SkillClassification(
                term_key, SkillState.UNKNOWN, "a matching claim exists but is not strong enough to confirm presence"
            )
        )
    return out
