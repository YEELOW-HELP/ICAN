"""Shared builders for Stage 3B (Direction Intelligence) tests.

Everything here builds plain in-memory data -- the Slice 1 deterministic
functions are pure, so most tests need no database.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.db.models_profile import ClaimStatus, ProfileDimension
from app.services.direction.dimension_mapping import MappedClaim, MappingStatus
from app.services.direction.dimensions import CanonicalDimension
from app.services.direction.scoring.aggregate import FamilyOutcome
from app.services.direction.scoring.base import CareerRequirementRef, CareerSkillRef, ScoreContext
from app.services.direction.scoring.evidence_confidence import EvidenceConfidenceOutcome
from app.db.models_direction import OutputFamily, QualitativeBand
from app.services.direction.ranking import DirectionOutcomeBundle


@dataclass
class FakeClaim:
    """Minimal stand-in for a Stage 2 `ProfileClaim` -- enough for
    `map_claim`. Not persisted; the adapter is read-only anyway."""

    dimension: ProfileDimension
    term_key: str | None
    label: str
    normalized_value: str
    status: ClaimStatus
    confidence: float
    id: uuid.UUID = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.id is None:
            self.id = uuid.uuid4()


def fake_claim(
    dimension: ProfileDimension,
    *,
    term_key: str | None = None,
    label: str = "lbl",
    normalized_value: str = "val",
    status: ClaimStatus = ClaimStatus.SUPPORTED,
    confidence: float = 0.8,
) -> FakeClaim:
    return FakeClaim(dimension, term_key, label, normalized_value, status, confidence)


def mapped(
    canonical: CanonicalDimension | None,
    *,
    status: MappingStatus = MappingStatus.MAPPED,
    claim_status: str = "supported",
    term_key: str | None = None,
    label: str = "lbl",
    normalized_value: str = "val",
    confidence: float = 0.8,
    subdimension: str | None = None,
    legacy_dimension: str = "skill",
) -> MappedClaim:
    return MappedClaim(
        source_claim_id=uuid.uuid4(),
        legacy_dimension=legacy_dimension,
        legacy_term_key=term_key,
        status=status,
        canonical_dimension=canonical,
        canonical_subdimension=subdimension,
        mapping_version="legacy-to-mnp:v0.1",
        label=label,
        normalized_value=normalized_value,
        claim_status=claim_status,
        claim_confidence=confidence,
    )


def score_context(
    *,
    mapped_claims=(),
    career_code="test_career",
    career_domain="technology",
    characteristics: dict | None = None,
    work_context: dict | None = None,
    career_skills: tuple[CareerSkillRef, ...] = (),
    career_requirements: tuple[CareerRequirementRef, ...] = (),
) -> ScoreContext:
    return ScoreContext(
        mapped_claims=tuple(mapped_claims),
        career_code=career_code,
        career_domain=career_domain,
        career_characteristics=characteristics or {},
        work_context=work_context or {},
        career_skills=career_skills,
        career_requirements=career_requirements,
    )


def family_outcome(
    family: OutputFamily,
    raw: float | None,
    band: QualitativeBand | None,
    *,
    coverage=1.0,
    scored=1,
    enabled=1,
) -> FamilyOutcome:
    return FamilyOutcome(family, raw, band, coverage, scored, enabled)


def evidence_confidence_outcome(raw: float | None, band: QualitativeBand | None) -> EvidenceConfidenceOutcome:
    return EvidenceConfidenceOutcome(raw, band, "test")


def bundle(
    code: str,
    *,
    hard_blocked=False,
    pf: tuple[float | None, QualitativeBand | None] = (0.8, QualitativeBand.HIGH),
    ga: tuple[float | None, QualitativeBand | None] = (0.6, QualitativeBand.MEDIUM),
    tf: tuple[float | None, QualitativeBand | None] = (0.6, QualitativeBand.MEDIUM),
    ec: tuple[float | None, QualitativeBand | None] = (0.7, QualitativeBand.HIGH),
    domain="technology",
) -> DirectionOutcomeBundle:
    return DirectionOutcomeBundle(
        career_code=code,
        domain=domain,
        hard_blocked=hard_blocked,
        potential_fit=family_outcome(OutputFamily.POTENTIAL_FIT, *pf),
        goal_alignment=family_outcome(OutputFamily.GOAL_ALIGNMENT, *ga),
        transition_feasibility=family_outcome(OutputFamily.TRANSITION_FEASIBILITY, *tf),
        evidence_confidence=evidence_confidence_outcome(*ec),
    )
