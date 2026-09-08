"""Claim synthesis and deterministic confidence (Stage 2 brief §5/§6/§7/§8,
tests per §27 CLAIMS section).
"""

from app.db.models_profile import ClaimStatus, Evidence, EvidenceSourceType, ProfileDimension
from app.services.profile.claim_synthesis import ClaimProposal, compute_claim_confidence


def _evidence(confidence: float, extraction_method: str = "llm_extraction") -> Evidence:
    return Evidence(
        user_id="00000000-0000-0000-0000-000000000000",
        session_id="00000000-0000-0000-0000-000000000000",
        source_type=EvidenceSourceType.OPEN_ANSWER,
        source_id="00000000-0000-0000-0000-000000000000",
        evidence_type="test_signal",
        normalized_text="some observation",
        confidence=confidence,
        extraction_method=extraction_method,
    )


def test_no_evidence_means_claim_is_never_emitted():
    result = compute_claim_confidence([], is_contradictory=False)
    assert result is None


def test_single_weak_evidence_produces_hypothesis_not_supported():
    confidence, status = compute_claim_confidence([_evidence(0.4)], is_contradictory=False)
    assert status == ClaimStatus.HYPOTHESIS
    assert confidence < 0.6


def test_multiple_corroborating_evidence_produces_supported():
    evidence = [_evidence(0.7), _evidence(0.75), _evidence(0.8)]
    confidence, status = compute_claim_confidence(evidence, is_contradictory=False)
    assert status == ClaimStatus.SUPPORTED
    assert confidence >= 0.6


def test_single_direct_deterministic_evidence_can_be_supported():
    confidence, status = compute_claim_confidence([_evidence(0.9, extraction_method="deterministic")], is_contradictory=False)
    assert status == ClaimStatus.SUPPORTED  # direct/structured evidence doesn't need corroboration to be trusted


def test_very_weak_evidence_is_insufficient_not_hypothesis():
    confidence, status = compute_claim_confidence([_evidence(0.1)], is_contradictory=False)
    assert status == ClaimStatus.INSUFFICIENT_EVIDENCE


def test_contradiction_lowers_confidence_and_marks_contradicted_never_averaged():
    """Two conflicting high-confidence evidence items must not average
    into a confident claim -- confidence must drop, not be smoothed over."""
    evidence = [_evidence(0.9), _evidence(0.85)]
    confidence, status = compute_claim_confidence(evidence, is_contradictory=True)
    assert status == ClaimStatus.CONTRADICTED
    assert confidence < 0.6  # sharply lower than what 0.9/0.85 would otherwise produce


def test_contradiction_confidence_is_always_lower_than_non_contradiction_with_same_evidence():
    evidence = [_evidence(0.8), _evidence(0.8)]
    contradicted_confidence, _ = compute_claim_confidence(evidence, is_contradictory=True)
    supported_confidence, _ = compute_claim_confidence(evidence, is_contradictory=False)
    assert contradicted_confidence < supported_confidence
