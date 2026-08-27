"""Deterministic minimum-profile gate (Founder decision H, Evidence
Standard v0.1 section 5).

Direction Intelligence does not produce directions from an under-evidenced
profile. Below threshold, the run is `INSUFFICIENT_INFORMATION` and
clarification requests are emitted -- TOP 3 + Alternative 3 is NEVER
manufactured to have something to show.

All thresholds come from the versioned `ScoringConfig` -- nothing here is
a hard-coded number.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from app.services.direction.dimension_mapping import MappedClaim, MappingStatus
from app.services.direction.dimensions import CanonicalDimension

__all__ = ["ThresholdReason", "ThresholdResult", "evaluate_minimum_profile"]

_SUPPORTED = "supported"  # ProfileClaim status value that counts toward the threshold


class ThresholdReason:
    PROFILE_NOT_READY = "profile_not_ready"
    INSUFFICIENT_SUPPORTED_CLAIMS = "insufficient_supported_claims"
    INSUFFICIENT_DIMENSION_COVERAGE = "insufficient_dimension_coverage"


@dataclass(frozen=True)
class ThresholdResult:
    passed: bool
    reason: str | None
    supported_claim_count: int
    canonical_dimensions_covered: frozenset[CanonicalDimension]
    required_supported_claims: int
    required_canonical_dimensions: int
    missing_dimension_hint: tuple[str, ...] = field(default_factory=tuple)


def evaluate_minimum_profile(
    *,
    profile_status: str,
    profile_is_current: bool,
    mapped_claims: Sequence[MappedClaim],
    thresholds: dict,
) -> ThresholdResult:
    min_supported = int(thresholds.get("min_supported_claims", 4))
    min_dimensions = int(thresholds.get("min_canonical_dimensions", 3))

    supported = [
        mc
        for mc in mapped_claims
        if mc.claim_status == _SUPPORTED
    ]
    covered: set[CanonicalDimension] = {
        mc.canonical_dimension
        for mc in supported
        if mc.status is MappingStatus.MAPPED and mc.canonical_dimension is not None
    }

    base = dict(
        supported_claim_count=len(supported),
        canonical_dimensions_covered=frozenset(covered),
        required_supported_claims=min_supported,
        required_canonical_dimensions=min_dimensions,
    )

    if profile_status != "ready" or not profile_is_current:
        return ThresholdResult(passed=False, reason=ThresholdReason.PROFILE_NOT_READY, **base)

    if len(supported) < min_supported:
        return ThresholdResult(
            passed=False, reason=ThresholdReason.INSUFFICIENT_SUPPORTED_CLAIMS, **base
        )

    if len(covered) < min_dimensions:
        missing = tuple(
            d.value for d in CanonicalDimension if d not in covered
        )
        return ThresholdResult(
            passed=False,
            reason=ThresholdReason.INSUFFICIENT_DIMENSION_COVERAGE,
            missing_dimension_hint=missing,
            **base,
        )

    return ThresholdResult(passed=True, reason=None, **base)
