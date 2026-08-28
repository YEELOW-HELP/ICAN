"""Matching V1 M4 -- pure guarded-cosine unit tests, no DB (Founder
Review test items #1-6)."""

import pytest

from app.services.matching.config import MatchingConfig
from app.services.matching.pure import guarded_cosine_fit

CONFIG = MatchingConfig()


def test_identical_riasec_vectors_high_similarity():
    """#1."""
    vector = {"R": 0.9, "I": 0.7, "A": 0.2, "S": 0.2, "E": 0.5, "C": 0.3}
    result = guarded_cosine_fit(vector, dict(vector), config=CONFIG, provisional=False)
    assert result.status == "scored"
    assert result.raw_score == pytest.approx(1.0)
    assert result.band == "high"


def test_differentiated_opposite_vectors_lower_similarity():
    """#2."""
    user = {"R": 0.9, "I": 0.1, "A": 0.9, "S": 0.1, "E": 0.9, "C": 0.1}
    career = {"R": 0.1, "I": 0.9, "A": 0.1, "S": 0.9, "E": 0.1, "C": 0.9}
    result = guarded_cosine_fit(user, career, config=CONFIG, provisional=False)
    assert result.status == "scored"
    assert result.raw_score < 0.5


def test_flat_user_vector_triggers_low_differentiation():
    """#3."""
    user = {"R": 0.5, "I": 0.5, "A": 0.5, "S": 0.5, "E": 0.5, "C": 0.5}
    career = {"R": 0.9, "I": 0.2, "A": 0.8, "S": 0.3, "E": 0.7, "C": 0.1}
    result = guarded_cosine_fit(user, career, config=CONFIG, provisional=False)
    assert result.status == "low_differentiation"
    assert result.raw_score is None
    assert result.band is None
    assert result.user_stdev == pytest.approx(0.0)


def test_flat_career_vector_triggers_low_differentiation():
    """#4."""
    user = {"R": 0.9, "I": 0.2, "A": 0.8, "S": 0.3, "E": 0.7, "C": 0.1}
    career = {"R": 0.5, "I": 0.5, "A": 0.5, "S": 0.5, "E": 0.5, "C": 0.5}
    result = guarded_cosine_fit(user, career, config=CONFIG, provisional=False)
    assert result.status == "low_differentiation"
    assert result.career_stdev == pytest.approx(0.0)


def test_stdev_guard_configurable_versioned():
    """#5 -- a different threshold changes the outcome for the SAME
    inputs, proving the guard is not a hardcoded magic number."""
    user = {"R": 0.55, "I": 0.5, "A": 0.5, "S": 0.45, "E": 0.5, "C": 0.5}
    career = {"R": 0.9, "I": 0.2, "A": 0.8, "S": 0.3, "E": 0.7, "C": 0.1}

    strict_config = MatchingConfig(differentiation_stdev_threshold=0.10)
    lenient_config = MatchingConfig(differentiation_stdev_threshold=0.01)

    strict_result = guarded_cosine_fit(user, career, config=strict_config, provisional=False)
    lenient_result = guarded_cosine_fit(user, career, config=lenient_config, provisional=False)

    assert strict_result.status == "low_differentiation"
    assert lenient_result.status == "scored"
    assert strict_result.differentiation_threshold == 0.10
    assert lenient_result.differentiation_threshold == 0.01


def test_interest_fit_deterministic():
    """#6 -- same vectors, repeated calls, byte-identical result."""
    user = {"R": 0.7, "I": 0.6, "A": 0.3, "S": 0.4, "E": 0.5, "C": 0.2}
    career = {"R": 0.8, "I": 0.5, "A": 0.2, "S": 0.3, "E": 0.6, "C": 0.1}

    results = [guarded_cosine_fit(dict(user), dict(career), config=CONFIG, provisional=False) for _ in range(5)]
    assert all(r == results[0] for r in results)
