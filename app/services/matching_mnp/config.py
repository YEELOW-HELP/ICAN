"""Versioned internal scales/thresholds. `MNP_MATCHING_MATH_V1`:
"weights are configuration, versioned, and calibrated using Golden
Dataset/pilot outcomes" -- Methodology §25 explicitly leaves exact
weights unapproved in v1, so these are a documented, reasonable default,
not a claimed calibration. Bumping `MATCHING_ENGINE_VERSION` is required
whenever any constant below changes (MnpMatchRun pins it for
reproducibility, MNP_CAREER_PROFILE_SCHEMA_V1 §29)."""

from __future__ import annotations

METHODOLOGY_VERSION = "mnp_methodology_v1.0"
MATCHING_ENGINE_VERSION = "mnp_matching_engine_v0.1"

# MNP_SKILL_SCHEMA_V1 §12.
IMPORTANCE_WEIGHTS: dict[str, float] = {"low": 1.0, "medium": 2.0, "high": 3.0, "critical": 4.0}

# MNP_SKILL_SCHEMA_V1 §5 -- BASIC/WORKING/STRONG as an ordered internal scale.
PROFICIENCY_NUMERIC: dict[str, float] = {"basic": 0.34, "working": 0.67, "strong": 1.0}

# MnpCareerAttribute.attribute_key ("work_context" group) -> the
# comparable MnpPreferenceProfile field, and whether the two scales point
# the same direction. `routine` measures how routine the CAREER is;
# `routine_vs_novelty_preference` measures the PERSON's appetite for
# novelty (0=prefers routine, 1=prefers novelty) -- opposite polarity, so
# it's inverted before comparing. `pace` is seeded on some careers as
# editorial context but has no questionnaire-collected person-side
# counterpart in V1 -- deliberately excluded here, not silently guessed.
PREFERENCE_ATTRIBUTE_MAPPING: dict[str, tuple[str, bool]] = {
    "customer_interaction": ("customer_interaction_preference", False),
    "autonomy": ("autonomy_preference", False),
    "routine": ("routine_vs_novelty_preference", True),  # True = invert career value before comparing
}

# Minimum number of comparable (career-side AND person-side present)
# data points before a Fit component may be SCORED rather than
# INSUFFICIENT_DATA -- mirrors the general Confidence principle
# (MNP_EVIDENCE_AND_CONFIDENCE_MODEL_V1 §17): a fit computed from one
# data point is not trustworthy enough to present as a real signal.
MIN_COMPARABLE_SKILL_REQUIREMENTS = 1  # any real MUST_HAVE/HIGH_VALUE requirement is meaningful on its own
MIN_COMPARABLE_PREFERENCE_SIGNALS = 2

# Internal score bands (MatchComponent.band) -- never shown as raw
# numbers to the user (Founder Decision #15).
BAND_HIGH = 0.70
BAND_MEDIUM = 0.40


def score_to_band(score: float) -> str:
    if score >= BAND_HIGH:
        return "high"
    if score >= BAND_MEDIUM:
        return "medium"
    return "low"


# Confidence bands (MNP_EVIDENCE_AND_CONFIDENCE_MODEL_V1 §6) driven by
# coverage ratio (# of comparable data points actually present / #
# expected) for the given component.
def coverage_to_confidence_band(coverage_ratio: float) -> str:
    if coverage_ratio >= 0.75:
        return "high"
    if coverage_ratio >= 0.4:
        return "medium"
    if coverage_ratio > 0:
        return "low"
    return "insufficient"


# MNP_SKILL_GAP_AND_PRIORITY_V1 "Priority": importance x gap size x
# market value x learnability / time cost. Market value/learnability are
# not modeled numerically in v0.1 (no market ingestion, no learning-time
# taxonomy yet) -- held at neutral 1.0 so priority currently reduces to
# importance x gap size, documented as a known simplification.
DEFAULT_LEARNABILITY = 1.0
DEFAULT_MARKET_VALUE = 1.0
