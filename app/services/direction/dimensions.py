"""The 12 canonical MNP-HPM v0.1 dimensions + the v0.1 subdimension
taxonomy (Founder decisions B, C).

`CanonicalDimension` is an ARCHITECTURAL enum -- the list of 12 is fixed by
Founder decision B and is not open content, exactly like Stage 2's
`ProfileDimension` or Stage 3A's `CareerDomain`.

Subdimensions ARE content: they live in `_SUBDIMENSIONS` as versioned data
(`SUBDIMENSION_TAXONOMY_VERSION`). Per Founder decision C, engineering
implements ONLY the subdimensions specified in
`methodology_lab/02_HUMAN_POTENTIAL_MODEL/MNP_HUMAN_POTENTIAL_MODEL_V0.1.md`
section 3 -- no new psychological constructs. Dimensions left "top-level
only" in v0.1 have an empty tuple here on purpose.
"""

from __future__ import annotations

import enum

from app.services.direction.versions import SUBDIMENSION_TAXONOMY_VERSION

__all__ = [
    "CanonicalDimension",
    "SUBDIMENSION_TAXONOMY_VERSION",
    "subdimensions_for",
    "is_known_subdimension",
    "CANONICAL_DIMENSION_ORDER",
]


class CanonicalDimension(str, enum.Enum):
    """MNP-HPM v0.1 -- exactly these twelve, in this order (Founder decision B)."""

    INTERESTS = "interests"
    STRENGTHS = "strengths"
    SKILLS = "skills"
    ABILITIES_LEARNING_POTENTIAL = "abilities_learning_potential"
    WORK_STYLE = "work_style"
    WORK_ENVIRONMENT = "work_environment"
    VALUES = "values"
    MOTIVATION = "motivation"
    EXPERIENCE = "experience"
    GOALS = "goals"
    CONSTRAINTS = "constraints"
    CAREER_ADAPTABILITY = "career_adaptability"


CANONICAL_DIMENSION_ORDER: tuple[CanonicalDimension, ...] = tuple(CanonicalDimension)


# v0.1 subdimension taxonomy. Only what MNP-HPM v0.1 section 3 specifies.
# An empty tuple == "top-level only in v0.1" (deliberate, not a TODO).
_SUBDIMENSIONS: dict[CanonicalDimension, tuple[str, ...]] = {
    CanonicalDimension.INTERESTS: (),
    CanonicalDimension.STRENGTHS: (),
    CanonicalDimension.SKILLS: (),
    CanonicalDimension.ABILITIES_LEARNING_POTENTIAL: (),
    CanonicalDimension.WORK_STYLE: (
        "autonomy",
        "structure_preference",
        "ambiguity_tolerance",
        "pace",
        "collaboration",
        "leadership",
        "customer_interaction",
        "decision_responsibility",
        "routine_tolerance",
        "initiative",
    ),
    CanonicalDimension.WORK_ENVIRONMENT: (
        "setting",
        "collaboration_context",
        "schedule_predictability",
        "physical_environment",
        "customer_interaction_context",
    ),
    CanonicalDimension.VALUES: (),
    CanonicalDimension.MOTIVATION: (),
    CanonicalDimension.EXPERIENCE: (),
    CanonicalDimension.GOALS: (),
    CanonicalDimension.CONSTRAINTS: (
        # MNP-HPM section 3.3 -- the 12 constraint subtypes (Founder decision Q)
        # double as this dimension's v0.1 subdimensions.
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
    ),
    CanonicalDimension.CAREER_ADAPTABILITY: (),
}


def subdimensions_for(dimension: CanonicalDimension) -> tuple[str, ...]:
    return _SUBDIMENSIONS[dimension]


def is_known_subdimension(dimension: CanonicalDimension, subdimension: str | None) -> bool:
    if subdimension is None:
        return True
    return subdimension in _SUBDIMENSIONS[dimension]
