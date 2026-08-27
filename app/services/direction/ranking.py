"""RankingPolicy execution -- the SEPARATE versioned decision layer
(Founder decisions A + O + G; methodology_lab/04_CAREER_FIT_MODEL/
MNP_RANKING_POLICY_V0.1.md).

`rank_directions` is a PURE function of (per-career four-output bundles,
policy dict). It never:
- computes a blended/composite career score;
- mutates any output;
- pads a pool to a target size;
- blocks a career (only the hard gate does);
- overrides the hard gate.

Slice 1 delivers this interface + the deterministic rule. The orchestrator
that persists `Direction`/`DirectionRun` rows is a later slice.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from app.db.models_direction import DirectionPlacement, QualitativeBand
from app.services.direction.scoring.aggregate import FamilyOutcome
from app.services.direction.scoring.evidence_confidence import EvidenceConfidenceOutcome

__all__ = ["DirectionOutcomeBundle", "RankedDirection", "rank_directions"]

_BAND_RANK = {None: -1, QualitativeBand.LOW: 0, QualitativeBand.MEDIUM: 1, QualitativeBand.HIGH: 2}


@dataclass(frozen=True)
class DirectionOutcomeBundle:
    career_code: str
    domain: str
    hard_blocked: bool
    potential_fit: FamilyOutcome
    goal_alignment: FamilyOutcome
    transition_feasibility: FamilyOutcome
    evidence_confidence: EvidenceConfidenceOutcome


@dataclass(frozen=True)
class RankedDirection:
    career_code: str
    placement: DirectionPlacement
    rank_within_placement: int | None
    trade_off_notes: str | None = None
    coverage_warnings: tuple[str, ...] = field(default_factory=tuple)


def _band_at_least(band: QualitativeBand | None, minimum: str) -> bool:
    return _BAND_RANK.get(band, -1) >= _BAND_RANK[QualitativeBand(minimum)]


def _norm(raw: float | None) -> float:
    # None sorts LAST on a descending key -> map to a value below any real 0..1 raw.
    return raw if raw is not None else -1.0


def _sort_key(b: DirectionOutcomeBundle):
    return (
        -_norm(b.potential_fit.raw),
        -_norm(b.goal_alignment.raw),
        -_norm(b.transition_feasibility.raw),
        -_norm(b.evidence_confidence.raw_experimental),
        b.career_code,
    )


def _coverage_warnings(b: DirectionOutcomeBundle) -> tuple[str, ...]:
    w: list[str] = []
    if b.goal_alignment.raw is None:
        w.append("goal_alignment_unknown")
    if b.transition_feasibility.raw is None:
        w.append("transition_feasibility_unknown")
    if b.evidence_confidence.raw_experimental is None:
        w.append("evidence_confidence_unknown")
    return tuple(w)


def _trade_offs(b: DirectionOutcomeBundle) -> str | None:
    parts = []
    if b.goal_alignment.band is QualitativeBand.LOW:
        parts.append("LOW Goal Alignment")
    if b.transition_feasibility.band is QualitativeBand.LOW:
        parts.append("LOW Transition Feasibility")
    return "; ".join(parts) if parts else None


def rank_directions(
    bundles: Sequence[DirectionOutcomeBundle], *, policy: dict
) -> list[RankedDirection]:
    p = policy
    main_elig = p.get("main_eligibility", {})
    alt_elig = p.get("alternative_eligibility", {})
    main_max = int(p.get("main_max", 3))
    alt_max = int(p.get("alternative_max", 3))

    results: list[RankedDirection] = []

    # 1. hard gate -- BLOCKED excluded from eligibility
    eligible: list[DirectionOutcomeBundle] = []
    for b in bundles:
        if b.hard_blocked and p.get("exclude_hard_blocked", True):
            results.append(RankedDirection(b.career_code, DirectionPlacement.BLOCKED, None))
        else:
            eligible.append(b)

    forbidden_ga = set(main_elig.get("goal_alignment_forbidden_bands_when_known", ["low"]))
    forbidden_tf = set(main_elig.get("transition_feasibility_forbidden_bands_when_known", ["low"]))

    def main_eligible(b: DirectionOutcomeBundle) -> bool:
        if not _band_at_least(b.potential_fit.band, main_elig.get("potential_fit_min_band", "medium")):
            return False
        if not _band_at_least(
            b.evidence_confidence.band, main_elig.get("evidence_confidence_min_band", "medium")
        ):
            return False
        # Unknown Goal Alignment / Feasibility is NOT LOW (Founder decision A.2).
        if b.goal_alignment.band is not None and b.goal_alignment.band.value in forbidden_ga:
            return False
        if b.transition_feasibility.band is not None and b.transition_feasibility.band.value in forbidden_tf:
            return False
        return True

    def alt_eligible(b: DirectionOutcomeBundle) -> bool:
        return _band_at_least(b.potential_fit.band, alt_elig.get("potential_fit_min_band", "medium"))

    main_pool = sorted([b for b in eligible if main_eligible(b)], key=_sort_key)
    main_selected = main_pool[:main_max]
    main_codes = {b.career_code for b in main_selected}

    for i, b in enumerate(main_selected, start=1):
        results.append(
            RankedDirection(
                b.career_code,
                DirectionPlacement.MAIN,
                i,
                trade_off_notes=None,
                coverage_warnings=_coverage_warnings(b),
            )
        )

    remaining = [b for b in eligible if b.career_code not in main_codes]
    alt_pool = sorted([b for b in remaining if alt_eligible(b)], key=_sort_key)
    alt_selected = alt_pool[:alt_max]
    alt_codes = {b.career_code for b in alt_selected}

    for i, b in enumerate(alt_selected, start=1):
        results.append(
            RankedDirection(
                b.career_code,
                DirectionPlacement.ALTERNATIVE,
                i,
                trade_off_notes=_trade_offs(b),
                coverage_warnings=_coverage_warnings(b),
            )
        )

    for b in remaining:
        if b.career_code not in alt_codes:
            results.append(RankedDirection(b.career_code, DirectionPlacement.NOT_ELIGIBLE, None))

    return results
