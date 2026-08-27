"""Per-output family aggregation (Founder decisions F + N).

For each of Potential Fit / Goal Alignment / Transition Feasibility:
- weighted mean over components with status == SCORED only;
- INSUFFICIENT_DATA / NOT_APPLICABLE excluded from numerator AND
  denominator -- never counted as a mismatch;
- raw = None (band = None) if scored_component_count < min_scored_components
  -- "unknown", which is NOT `LOW`;
- band via config cutoffs.

Nothing here blends families together. Nothing here ranks.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.db.models_direction import OutputFamily, QualitativeBand, ScoreComponentStatus
from app.services.direction.scoring.base import ScoreComponentResult

__all__ = ["FamilyOutcome", "band_for", "aggregate_family"]


@dataclass(frozen=True)
class FamilyOutcome:
    family: OutputFamily
    raw: float | None
    band: QualitativeBand | None
    coverage_ratio: float
    scored_component_count: int
    enabled_component_count: int


def band_for(raw: float | None, thresholds: dict) -> QualitativeBand | None:
    if raw is None:
        return None
    if raw >= float(thresholds.get("band_high_cutoff", 0.66)):
        return QualitativeBand.HIGH
    if raw >= float(thresholds.get("band_medium_cutoff", 0.33)):
        return QualitativeBand.MEDIUM
    return QualitativeBand.LOW


def aggregate_family(
    family: OutputFamily,
    results: Sequence[ScoreComponentResult],
    *,
    weights: dict[str, float],
    thresholds: dict,
) -> FamilyOutcome:
    """`results` must already be the components ENABLED for this family in
    the active ScoringConfig."""
    enabled_count = len(results)
    scored = [r for r in results if r.status is ScoreComponentStatus.SCORED and r.raw_score is not None]
    coverage = (len(scored) / enabled_count) if enabled_count else 0.0

    min_scored = int((thresholds.get("min_scored_components", {}) or {}).get(family.value, 1))
    if len(scored) < min_scored:
        return FamilyOutcome(
            family=family,
            raw=None,
            band=None,
            coverage_ratio=coverage,
            scored_component_count=len(scored),
            enabled_component_count=enabled_count,
        )

    num = sum(float(weights.get(r.component_key, 1.0)) * float(r.raw_score) for r in scored)
    den = sum(float(weights.get(r.component_key, 1.0)) for r in scored)
    raw = (num / den) if den > 0 else None
    return FamilyOutcome(
        family=family,
        raw=raw,
        band=band_for(raw, thresholds),
        coverage_ratio=coverage,
        scored_component_count=len(scored),
        enabled_component_count=enabled_count,
    )
