"""Versioned, configurable constants for the deterministic matching
engine (Matching V1 M4) -- never inlined as unexplained magic numbers,
per the same discipline established in
`app/services/basic_profile/config.py`.

Every value here is PROVISIONAL v0.1, sourced from an approved
methodology document. Changing any of them is a methodology decision,
not a code-review nit.
"""

from __future__ import annotations

from dataclasses import dataclass

#: `MNP_MATCHING_METRIC_BENCHMARK_V0.1.md` §6, Founder-approved
#: "M0 FINAL DECISIONS" (2026-08-28): PROVISIONAL / VERSIONED /
#: CONFIGURABLE / EXPERIMENTAL engineering guard -- NOT a validated
#: psychometric threshold. Reused verbatim from
#: `app/services/basic_profile/config.py::DIFFERENTIATION_STDEV_THRESHOLD`
#: (imported there, not re-declared, so the two engines can never drift
#: apart on this constant).
from app.services.basic_profile.config import DIFFERENTIATION_STDEV_THRESHOLD  # noqa: F401

#: Golden Test doc §17 ("If comparable-component count is below the
#: configured minimum: INSUFFICIENT_DATA", Founder Review §5) -- same
#: floor already used for M2's own per-vector differentiation gate
#: (`app/services/basic_profile/config.py::DIFFERENTIATION_MIN_SCALE_COVERAGE`
#: uses a ratio; this is an absolute floor on count of comparable scales,
#: a distinct but analogous guard).
MIN_COMPARABLE_COMPONENTS = 2

#: `MNP_GOLDEN_TEST_V0.1.md` §23 -- three-band cutoffs, applied uniformly
#: to Interest/Work Style/Values Fit and to Feasibility's own numeric
#: score. PROVISIONAL/EXPERIMENTAL, never claimed calibrated (Founder
#: Review §14).
BAND_HIGH_MIN = 0.70
BAND_MEDIUM_MIN = 0.40

#: `MNP_GOLDEN_TEST_V0.1.md` §22 -- the exact, already-approved soft
#: feasibility penalty factors. No new penalty factor is invented in M4;
#: any comparison this engine cannot ground in one of these four
#: documented penalties is surfaced as a qualitative barrier/gap only,
#: never a numeric multiplier.
FEASIBILITY_EDUCATION_BELOW_TYPICAL_PENALTY = 0.85
FEASIBILITY_WORK_FORMAT_MISMATCH_PENALTY = 0.90
FEASIBILITY_FAMILY_LOGISTICS_SIGNIFICANT_PENALTY = 0.90
FEASIBILITY_NO_CAPACITY_WITH_SKILLS_GAP_PENALTY = 0.80

#: `docs/engineering/21_..._IMPLEMENTATION_PLAN.md` §4 versioning-stamp
#: requirement. Bump only when this package's calculation logic itself
#: changes.
MATCHING_ENGINE_VERSION = "matching_engine_v0.1"
METRIC_VERSION = "guarded_cosine_v0.1"
CONFIG_VERSION = "matching_config_v0.1"


@dataclass(frozen=True)
class MatchingConfig:
    """Snapshot of every versioned constant this package uses for one
    calculation run -- passed explicitly into every pure function rather
    than read from module globals inside them, so `calculate_pair_match`
    stays a pure function of its arguments (Founder Review §17) and a
    test can exercise a different threshold without monkeypatching."""

    differentiation_stdev_threshold: float = DIFFERENTIATION_STDEV_THRESHOLD
    min_comparable_components: int = MIN_COMPARABLE_COMPONENTS
    band_high_min: float = BAND_HIGH_MIN
    band_medium_min: float = BAND_MEDIUM_MIN
    feasibility_education_penalty: float = FEASIBILITY_EDUCATION_BELOW_TYPICAL_PENALTY
    feasibility_work_format_penalty: float = FEASIBILITY_WORK_FORMAT_MISMATCH_PENALTY
    feasibility_family_logistics_penalty: float = FEASIBILITY_FAMILY_LOGISTICS_SIGNIFICANT_PENALTY
    feasibility_no_capacity_skills_gap_penalty: float = FEASIBILITY_NO_CAPACITY_WITH_SKILLS_GAP_PENALTY
    matching_engine_version: str = MATCHING_ENGINE_VERSION
    metric_version: str = METRIC_VERSION
    config_version: str = CONFIG_VERSION


DEFAULT_CONFIG = MatchingConfig()
