"""Evidence Confidence -- the fourth Direction output (Founder decision N;
Career Fit / Direction Evaluation Model v0.1 section 6).

Separate deterministic calculation. NOT Fit. NOT an LLM number. Additive +
bounded (the Stage 2 `compute_claim_confidence` style); every constant
lives in `ScoringConfig.thresholds` and is EXPERIMENTAL.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.db.models_direction import QualitativeBand
from app.services.direction.scoring.aggregate import band_for

__all__ = ["EvidenceConfidenceContext", "EvidenceConfidenceOutcome", "compute_evidence_confidence"]


@dataclass(frozen=True)
class EvidenceConfidenceContext:
    # Claim confidence of the SUPPORTED claims that fed SCORED components.
    supporting_claim_confidences: Sequence[float]
    # Dominant evidence tier across those claims: "E1" | "E2" | "E3" | None.
    dominant_evidence_tier: str | None
    # Distinct `Evidence.source_type` behind the supporting claims.
    distinct_source_type_count: int
    # How many of Potential Fit / Goal Alignment / Transition Feasibility
    # produced a non-None raw (0..3).
    fit_outputs_with_raw: int
    # `CONTRADICTED` claims among the relevant set.
    contradiction_count: int
    # Fraction of compared career attributes that were curated (not null), 0..1.
    kb_completeness: float


@dataclass(frozen=True)
class EvidenceConfidenceOutcome:
    raw_experimental: float | None
    band: QualitativeBand | None
    coverage_note: str


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def compute_evidence_confidence(
    ctx: EvidenceConfidenceContext, *, thresholds: dict
) -> EvidenceConfidenceOutcome:
    confs = list(ctx.supporting_claim_confidences)
    if not confs:
        return EvidenceConfidenceOutcome(
            raw_experimental=None,
            band=None,
            coverage_note="no supporting SUPPORTED claims fed any scored component -- Evidence Confidence unknown (not LOW)",
        )

    base = sum(confs) / len(confs)

    tier_bonus_map = thresholds.get("ec_tier_bonus", {"E1": 0.0, "E2": 0.05, "E3": 0.10})
    base += float(tier_bonus_map.get(ctx.dominant_evidence_tier or "E1", 0.0))

    if ctx.distinct_source_type_count >= 3:
        base += float(thresholds.get("ec_diversity_bonus_3plus", 0.10))
    elif ctx.distinct_source_type_count == 2:
        base += float(thresholds.get("ec_diversity_bonus_2", 0.05))

    extra_outputs = max(0, ctx.fit_outputs_with_raw - 1)
    base += min(
        float(thresholds.get("ec_coverage_bonus_cap", 0.10)),
        extra_outputs * float(thresholds.get("ec_coverage_bonus_per_extra_output", 0.05)),
    )

    base -= min(
        float(thresholds.get("ec_contradiction_penalty_cap", 0.30)),
        ctx.contradiction_count * float(thresholds.get("ec_contradiction_penalty_per_item", 0.10)),
    )

    base -= (1.0 - _clamp01(ctx.kb_completeness)) * float(
        thresholds.get("ec_kb_incompleteness_penalty_factor", 0.15)
    )

    raw = _clamp01(base)
    return EvidenceConfidenceOutcome(
        raw_experimental=raw,
        band=band_for(raw, thresholds),
        coverage_note=(
            f"{len(confs)} supporting claim(s), dominant tier {ctx.dominant_evidence_tier or 'E1'}, "
            f"{ctx.distinct_source_type_count} distinct source type(s), "
            f"{ctx.fit_outputs_with_raw}/3 fit outputs scored, {ctx.contradiction_count} contradiction(s), "
            f"KB completeness {ctx.kb_completeness:.2f}"
        ),
    )
