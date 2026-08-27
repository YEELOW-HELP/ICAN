"""Founder decisions D + N: Evidence Confidence is the 4th output --
separate, deterministic, banded LOW/MEDIUM/HIGH, never an LLM number,
never Fit. `None` (unknown) is not `LOW`.
"""

from app.db.models_direction import QualitativeBand
from app.services.direction.config import EXPERIMENTAL_NON_PRODUCTION_SCORING_CONFIG_V1
from app.services.direction.scoring.evidence_confidence import (
    EvidenceConfidenceContext,
    compute_evidence_confidence,
)

_TH = EXPERIMENTAL_NON_PRODUCTION_SCORING_CONFIG_V1["thresholds"]


def _ctx(**kw):
    base = dict(
        supporting_claim_confidences=[0.7, 0.7],
        dominant_evidence_tier="E2",
        distinct_source_type_count=2,
        fit_outputs_with_raw=2,
        contradiction_count=0,
        kb_completeness=1.0,
    )
    base.update(kw)
    return EvidenceConfidenceContext(**base)


def test_no_supporting_claims_yields_none_not_low():
    out = compute_evidence_confidence(_ctx(supporting_claim_confidences=[]), thresholds=_TH)
    assert out.raw_experimental is None
    assert out.band is None


def test_is_deterministic_and_bounded():
    a = compute_evidence_confidence(_ctx(), thresholds=_TH)
    b = compute_evidence_confidence(_ctx(), thresholds=_TH)
    assert a == b
    assert 0.0 <= a.raw_experimental <= 1.0


def test_contradictions_drive_confidence_down():
    clean = compute_evidence_confidence(_ctx(contradiction_count=0), thresholds=_TH)
    noisy = compute_evidence_confidence(_ctx(contradiction_count=3), thresholds=_TH)
    assert noisy.raw_experimental < clean.raw_experimental


def test_kb_incompleteness_penalises():
    full = compute_evidence_confidence(_ctx(kb_completeness=1.0), thresholds=_TH)
    sparse = compute_evidence_confidence(_ctx(kb_completeness=0.2), thresholds=_TH)
    assert sparse.raw_experimental < full.raw_experimental


def test_stronger_tier_and_diversity_raise_confidence():
    weak = compute_evidence_confidence(
        _ctx(dominant_evidence_tier="E1", distinct_source_type_count=1, fit_outputs_with_raw=1), thresholds=_TH
    )
    strong = compute_evidence_confidence(
        _ctx(dominant_evidence_tier="E3", distinct_source_type_count=3, fit_outputs_with_raw=3), thresholds=_TH
    )
    assert strong.raw_experimental > weak.raw_experimental


def test_banding_uses_the_shared_cutoffs():
    hi = compute_evidence_confidence(
        _ctx(supporting_claim_confidences=[0.9, 0.9], dominant_evidence_tier="E3", distinct_source_type_count=3),
        thresholds=_TH,
    )
    assert hi.band is QualitativeBand.HIGH
    lo = compute_evidence_confidence(
        _ctx(supporting_claim_confidences=[0.2], dominant_evidence_tier="E1", distinct_source_type_count=1,
             fit_outputs_with_raw=1, kb_completeness=0.1),
        thresholds=_TH,
    )
    assert lo.band is QualitativeBand.LOW
