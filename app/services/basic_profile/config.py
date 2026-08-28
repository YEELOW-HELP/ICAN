"""Versioned, configurable constants for the deterministic BASIC profile
engine -- never inlined as unexplained magic numbers inside the
calculation logic itself (Founder Review, 2026-08-28, on the
differentiation gate specifically, generalized here to every engine
constant).

Every value here is PROVISIONAL v0.1, sourced directly from an approved
methodology document -- never invented in code. Changing any of them is a
methodology decision, not a code-review nit; see the referenced document
before touching a value here.
"""

from __future__ import annotations

#: `MNP_GOLDEN_TEST_V0.1.md` §7 -- a scale counts as "sufficiently
#: answered" if at least this fraction of its items have a non-null
#: response.
SUFFICIENT_ANSWER_RATIO = 0.8

#: `MNP_GOLDEN_TEST_V0.1.md` §15 (hardened, schema-driven) -- the
#: Full/Partial/Insufficient Coverage band cutoffs.
COVERAGE_FULL_MIN = 1.0
COVERAGE_PARTIAL_MIN = 0.8

#: `MNP_MATCHING_METRIC_BENCHMARK_V0.1.md` §6, approved by Founder Review
#: "M0 FINAL DECISIONS" (2026-08-28) as a PROVISIONAL / VERSIONED /
#: CONFIGURABLE / EXPERIMENTAL engineering guard -- NOT a validated
#: psychometric threshold, NOT a personality/ability judgment. A vector
#: whose population standard deviation across its sufficiently-answered
#: components falls below this value is flagged LOW_DIFFERENTIATION
#: rather than silently scored as if it carried real signal.
DIFFERENTIATION_STDEV_THRESHOLD = 0.10

#: Same 80% floor as `SUFFICIENT_ANSWER_RATIO`, applied at the vector
#: (not single-scale) level: a vector family with fewer than this
#: fraction of its scales sufficiently answered cannot support a
#: meaningful differentiation judgment at all, regardless of what
#: stdev over the partial data would say -- classified INSUFFICIENT_DATA,
#: never NORMAL or LOW_DIFFERENTIATION.
DIFFERENTIATION_MIN_SCALE_COVERAGE = 0.8

#: `docs/engineering/21_..._IMPLEMENTATION_PLAN.md` §4 versioning-stamp
#: requirement. Bump this only when the calculation logic in
#: `calculation.py` itself changes -- never for a data/content-only
#: change (e.g. a new seeded item bank keeps the same engine version).
PROFILE_ENGINE_VERSION = "basic_profile_engine_v0.1"
