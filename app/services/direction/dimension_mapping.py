"""Legacy `ProfileClaim` -> canonical MNP dimension/subdimension adapter
(Founder decision B / MDR-2).

This is a READ-ONLY, VERSIONED adapter. It:
- never writes or rewrites a `ProfileClaim` (historical Stage 2 claims are
  immutable);
- always preserves the original legacy dimension on the result;
- returns one of MAPPED / UNMAPPED / NEEDS_CLARIFICATION;
- never invents a claim to satisfy the 12-dimension model.

The mapping table is
`methodology_lab/02_HUMAN_POTENTIAL_MODEL/MNP_HUMAN_POTENTIAL_MODEL_V0.1.md`
section 4. `DIMENSION_MAPPING_VERSION` bumps whenever that table changes.
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass

from app.db.models_profile import ProfileClaim, ProfileDimension
from app.services.direction.dimensions import CanonicalDimension
from app.services.direction.versions import DIMENSION_MAPPING_VERSION

__all__ = [
    "MappingStatus",
    "MappedClaim",
    "map_claim",
    "map_claims",
    "DIMENSION_MAPPING_VERSION",
]


class MappingStatus(str, enum.Enum):
    MAPPED = "mapped"
    UNMAPPED = "unmapped"
    NEEDS_CLARIFICATION = "needs_clarification"


@dataclass(frozen=True)
class MappedClaim:
    """The adapter's output for one legacy claim. `source_claim_id` and
    `legacy_dimension` are always populated so provenance to the original
    Stage 2 claim is never lost."""

    source_claim_id: uuid.UUID | None
    legacy_dimension: str
    legacy_term_key: str | None
    status: MappingStatus
    canonical_dimension: CanonicalDimension | None
    canonical_subdimension: str | None
    mapping_version: str
    # carried through for downstream fit/confidence use, never modified
    label: str
    normalized_value: str
    claim_status: str
    claim_confidence: float


# Direct 1:1 dimension mappings (MNP-HPM section 4.1).
_DIRECT: dict[ProfileDimension, CanonicalDimension] = {
    ProfileDimension.INTEREST: CanonicalDimension.INTERESTS,
    ProfileDimension.STRENGTH: CanonicalDimension.STRENGTHS,
    ProfileDimension.SKILL: CanonicalDimension.SKILLS,
    ProfileDimension.VALUE: CanonicalDimension.VALUES,
    ProfileDimension.MOTIVATION: CanonicalDimension.MOTIVATION,
    ProfileDimension.GOAL: CanonicalDimension.GOALS,
    ProfileDimension.EXPERIENCE: CanonicalDimension.EXPERIENCE,
    ProfileDimension.CONSTRAINT: CanonicalDimension.CONSTRAINTS,
}

# Term-specific mappings (MNP-HPM section 4.2). Key: (legacy_dimension, term_key).
# Value: (canonical_dimension | None, subdimension | None, status).
_TERM_SPECIFIC: dict[tuple[ProfileDimension, str], tuple[CanonicalDimension | None, str | None, MappingStatus]] = {
    (ProfileDimension.WORK_PREFERENCE, "remote_work"): (
        CanonicalDimension.WORK_ENVIRONMENT,
        "setting",
        MappingStatus.MAPPED,
    ),
    (ProfileDimension.WORK_PREFERENCE, "team_environment"): (
        CanonicalDimension.WORK_ENVIRONMENT,
        "collaboration_context",
        MappingStatus.MAPPED,
    ),
    (ProfileDimension.WORK_PREFERENCE, "structured_environment"): (
        CanonicalDimension.WORK_STYLE,
        "structure_preference",
        MappingStatus.MAPPED,
    ),
    (ProfileDimension.TRAIT, "adaptability"): (
        CanonicalDimension.CAREER_ADAPTABILITY,
        None,
        MappingStatus.MAPPED,
    ),
    (ProfileDimension.CONTEXTUAL_FACTOR, "family_responsibilities"): (
        CanonicalDimension.CONSTRAINTS,
        "family_logistics",
        MappingStatus.MAPPED,
    ),
}

# Per-dimension fallback when no term-specific rule matched (MNP-HPM 4.2).
_DIMENSION_FALLBACK: dict[ProfileDimension, MappingStatus] = {
    ProfileDimension.WORK_PREFERENCE: MappingStatus.NEEDS_CLARIFICATION,
    ProfileDimension.TRAIT: MappingStatus.NEEDS_CLARIFICATION,
    ProfileDimension.CONTEXTUAL_FACTOR: MappingStatus.UNMAPPED,
}


def map_claim(claim: ProfileClaim) -> MappedClaim:
    legacy_dim: ProfileDimension = claim.dimension
    term_key = claim.term_key or None

    common = dict(
        source_claim_id=claim.id,
        legacy_dimension=legacy_dim.value,
        legacy_term_key=term_key,
        mapping_version=DIMENSION_MAPPING_VERSION,
        label=claim.label,
        normalized_value=claim.normalized_value,
        claim_status=claim.status.value if hasattr(claim.status, "value") else str(claim.status),
        claim_confidence=claim.confidence,
    )

    # 1. term-specific rule wins
    if term_key is not None and (legacy_dim, term_key) in _TERM_SPECIFIC:
        canonical, subdim, status = _TERM_SPECIFIC[(legacy_dim, term_key)]
        return MappedClaim(status=status, canonical_dimension=canonical, canonical_subdimension=subdim, **common)

    # 2. direct dimension mapping
    if legacy_dim in _DIRECT:
        return MappedClaim(
            status=MappingStatus.MAPPED,
            canonical_dimension=_DIRECT[legacy_dim],
            canonical_subdimension=None,
            **common,
        )

    # 3. ambiguous / unmapped legacy dimension (work_preference/trait/contextual_factor
    #    that had no matching term-specific rule)
    fallback = _DIMENSION_FALLBACK.get(legacy_dim, MappingStatus.UNMAPPED)
    return MappedClaim(status=fallback, canonical_dimension=None, canonical_subdimension=None, **common)


def map_claims(claims: list[ProfileClaim]) -> list[MappedClaim]:
    return [map_claim(c) for c in claims]
