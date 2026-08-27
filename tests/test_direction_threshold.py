"""Founder decision H: minimum-profile gate. >=4 SUPPORTED claims covering
>=3 canonical dimensions, on a READY current profile. Below -> the run is
INSUFFICIENT_INFORMATION, never a manufactured 3+3.
"""

from app.services.direction.config import EXPERIMENTAL_NON_PRODUCTION_SCORING_CONFIG_V1
from app.services.direction.dimensions import CanonicalDimension
from app.services.direction.threshold import ThresholdReason, evaluate_minimum_profile
from tests.direction_test_helpers import mapped

_TH = EXPERIMENTAL_NON_PRODUCTION_SCORING_CONFIG_V1["thresholds"]


def _supported(dim):
    return mapped(dim, claim_status="supported")


def _pass_set():
    return [
        _supported(CanonicalDimension.INTERESTS),
        _supported(CanonicalDimension.STRENGTHS),
        _supported(CanonicalDimension.SKILLS),
        _supported(CanonicalDimension.VALUES),
    ]


def test_passes_with_four_supported_claims_over_three_dimensions():
    res = evaluate_minimum_profile(
        profile_status="ready", profile_is_current=True, mapped_claims=_pass_set(), thresholds=_TH
    )
    assert res.passed is True
    assert res.reason is None


def test_fails_when_profile_not_ready():
    res = evaluate_minimum_profile(
        profile_status="processing", profile_is_current=True, mapped_claims=_pass_set(), thresholds=_TH
    )
    assert res.passed is False
    assert res.reason == ThresholdReason.PROFILE_NOT_READY


def test_fails_when_not_current():
    res = evaluate_minimum_profile(
        profile_status="ready", profile_is_current=False, mapped_claims=_pass_set(), thresholds=_TH
    )
    assert res.reason == ThresholdReason.PROFILE_NOT_READY


def test_fails_with_too_few_supported_claims():
    claims = _pass_set()[:3]
    res = evaluate_minimum_profile(
        profile_status="ready", profile_is_current=True, mapped_claims=claims, thresholds=_TH
    )
    assert res.passed is False
    assert res.reason == ThresholdReason.INSUFFICIENT_SUPPORTED_CLAIMS
    assert res.supported_claim_count == 3


def test_fails_when_supported_claims_do_not_cover_enough_dimensions():
    claims = [
        _supported(CanonicalDimension.SKILLS),
        _supported(CanonicalDimension.SKILLS),
        _supported(CanonicalDimension.SKILLS),
        _supported(CanonicalDimension.INTERESTS),
    ]
    res = evaluate_minimum_profile(
        profile_status="ready", profile_is_current=True, mapped_claims=claims, thresholds=_TH
    )
    assert res.passed is False
    assert res.reason == ThresholdReason.INSUFFICIENT_DIMENSION_COVERAGE
    assert len(res.canonical_dimensions_covered) == 2
    assert res.missing_dimension_hint  # non-empty hint of what to ask about


def test_hypotheses_do_not_count_toward_the_threshold():
    claims = [mapped(c.canonical_dimension, claim_status="hypothesis") for c in _pass_set()]
    res = evaluate_minimum_profile(
        profile_status="ready", profile_is_current=True, mapped_claims=claims, thresholds=_TH
    )
    assert res.passed is False
    assert res.supported_claim_count == 0
