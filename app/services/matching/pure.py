"""Pure deterministic calculation layer, Matching V1 M4 (Founder Review
§17: "Separate CALCULATION from PERSISTENCE. We need to unit-test math
without DB."). No SQLAlchemy import anywhere in this module -- every
function here operates only on plain dataclasses/dicts and returns plain
dataclasses. Same inputs -> byte-identical output, always (no AI, no
learned coefficient, no randomness, no wall-clock dependency).

Implements, without inventing a new formula:
  - guarded cosine similarity (`MNP_GOLDEN_TEST_V0.1.md` §17-19,
    hardened by `MNP_MATCHING_METRIC_BENCHMARK_V0.1.md` §6)
  - the band cutoffs (`MNP_GOLDEN_TEST_V0.1.md` §23)
  - the deterministic gate-then-score Feasibility algorithm
    (`MNP_GOLDEN_TEST_V0.1.md` §20-22), using only the four already-
    documented soft penalty factors -- no fifth, undocumented penalty
    is ever introduced.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field

from app.services.matching.config import MatchingConfig

# ---------------------------------------------------------------------------
# Fit family (Interest / Work Style / Values)
# ---------------------------------------------------------------------------

STATUS_SCORED = "scored"
STATUS_INSUFFICIENT_DATA = "insufficient_data"
STATUS_LOW_DIFFERENTIATION = "low_differentiation"
STATUS_NOT_APPLICABLE = "not_applicable"

BAND_HIGH = "high"
BAND_MEDIUM = "medium"
BAND_LOW = "low"


@dataclass(frozen=True)
class FitFamilyResult:
    status: str
    raw_score: float | None
    band: str | None
    user_component_count: int
    career_component_count: int
    comparable_component_count: int
    comparable_scale_keys: tuple[str, ...]
    coverage_ratio: float
    provisional: bool
    user_stdev: float | None
    career_stdev: float | None
    differentiation_threshold: float


def _band_for(score: float, config: MatchingConfig) -> str:
    if score >= config.band_high_min:
        return BAND_HIGH
    if score >= config.band_medium_min:
        return BAND_MEDIUM
    return BAND_LOW


def _population_stdev(values: list[float]) -> float:
    """Population (not sample) standard deviation, matching
    `MNP_MATCHING_METRIC_BENCHMARK_V0.1.md`'s own `statistics.pstdev`
    convention exactly (already used by M2's own differentiation gate).
    A single-value list has stdev 0.0 by definition (no dispersion
    possible), not undefined."""

    if len(values) <= 1:
        return 0.0
    return statistics.pstdev(values)


def cosine_similarity(u: list[float], v: list[float]) -> float:
    """Plain cosine similarity. For non-negative `[0,1]` vectors this is
    already bounded to `[0,1]` -- no rescaling needed (Golden Test doc
    §17)."""

    dot = sum(a * b for a, b in zip(u, v))
    norm_u = math.sqrt(sum(a * a for a in u))
    norm_v = math.sqrt(sum(a * a for a in v))
    if norm_u == 0.0 or norm_v == 0.0:
        raise ValueError("cosine_similarity is undefined for a zero vector")
    return dot / (norm_u * norm_v)


def guarded_cosine_fit(
    user_values: dict[str, float],
    career_values: dict[str, float],
    *,
    config: MatchingConfig,
    provisional: bool,
) -> FitFamilyResult:
    """The one gate every Fit family (Interest/Work Style/Values) passes
    through. `user_values`/`career_values` must already be filtered to
    only the scale keys each side genuinely has a value for (never a
    fabricated 0 standing in for a missing one) -- this function computes
    the intersection itself and never assumes the caller pre-intersected.

    Guard order, exactly per Founder Review §3-4:
      1. If the career side has zero components at all, or the comparable
         intersection is below `config.min_comparable_components`:
         INSUFFICIENT_DATA. Missing != low.
      2. Else, compute the population stdev of BOTH sides' comparable
         values. If either falls below `config.differentiation_stdev_threshold`:
         LOW_DIFFERENTIATION. A flat vector on either side is never
         silently scored as if it carried real signal.
      3. Else: SCORED, with the plain cosine similarity and its band.
    """

    user_component_count = len(user_values)
    career_component_count = len(career_values)
    comparable_keys = tuple(sorted(set(user_values) & set(career_values)))
    comparable_component_count = len(comparable_keys)
    coverage_ratio = (comparable_component_count / user_component_count) if user_component_count else 0.0

    if career_component_count == 0 or comparable_component_count < config.min_comparable_components:
        return FitFamilyResult(
            status=STATUS_INSUFFICIENT_DATA,
            raw_score=None,
            band=None,
            user_component_count=user_component_count,
            career_component_count=career_component_count,
            comparable_component_count=comparable_component_count,
            comparable_scale_keys=comparable_keys,
            coverage_ratio=coverage_ratio,
            provisional=provisional,
            user_stdev=None,
            career_stdev=None,
            differentiation_threshold=config.differentiation_stdev_threshold,
        )

    u = [user_values[k] for k in comparable_keys]
    c = [career_values[k] for k in comparable_keys]
    user_stdev = _population_stdev(u)
    career_stdev = _population_stdev(c)

    if user_stdev < config.differentiation_stdev_threshold or career_stdev < config.differentiation_stdev_threshold:
        return FitFamilyResult(
            status=STATUS_LOW_DIFFERENTIATION,
            raw_score=None,
            band=None,
            user_component_count=user_component_count,
            career_component_count=career_component_count,
            comparable_component_count=comparable_component_count,
            comparable_scale_keys=comparable_keys,
            coverage_ratio=coverage_ratio,
            provisional=provisional,
            user_stdev=user_stdev,
            career_stdev=career_stdev,
            differentiation_threshold=config.differentiation_stdev_threshold,
        )

    raw_score = cosine_similarity(u, c)
    return FitFamilyResult(
        status=STATUS_SCORED,
        raw_score=raw_score,
        band=_band_for(raw_score, config),
        user_component_count=user_component_count,
        career_component_count=career_component_count,
        comparable_component_count=comparable_component_count,
        comparable_scale_keys=comparable_keys,
        coverage_ratio=coverage_ratio,
        provisional=provisional,
        user_stdev=user_stdev,
        career_stdev=career_stdev,
        differentiation_threshold=config.differentiation_stdev_threshold,
    )


# ---------------------------------------------------------------------------
# Transition Feasibility
# ---------------------------------------------------------------------------

FEASIBILITY_FEASIBLE = "feasible"
FEASIBILITY_PARTIAL = "partial"
FEASIBILITY_BLOCKED = "blocked"
FEASIBILITY_INSUFFICIENT_DATA = "insufficient_data"

SKILL_UNKNOWN = "unknown"
SKILL_PRESENT = "present"
SKILL_CONFIRMED_MISSING = "confirmed_missing"

# Job Zone -> minimum defensible education rank, per O*NET's own Job Zone
# preparation-level descriptions (Job Zone 1 = little/no preparation ...
# Job Zone 5 = extensive preparation). A structural, documented mapping,
# not an invented one -- mirrors the same kind of disclosed convention as
# `holland_code_to_riasec_vector` in M3.
_EDUCATION_RANK = {"secondary": 1, "vocational": 2, "bachelor": 3, "master": 4, "phd": 5}
_JOB_ZONE_MIN_EDUCATION_RANK = {1: 1, 2: 1, 3: 2, 4: 3, 5: 4}

# User `work_format` constraint answer -> career `CareerWorkContext.setting`
# values it is compatible with. Any setting not listed for a given
# work_format answer is a soft mismatch (never hard -- Work_format is
# never a CareerRequirement row, so it can never be HARD_FACTUAL by
# construction).
_WORK_FORMAT_COMPATIBLE_SETTINGS = {
    "office": {"office", "mixed"},
    "remote": {"remote", "mixed"},
    "hybrid": {"office", "remote", "mixed", "field"},
}

_HARD_BLOCK_ELIGIBLE_CATEGORIES = frozenset({"license", "certification", "legal_regulatory"})


@dataclass(frozen=True)
class ConstraintAnswer:
    scale_key: str
    boolean_value: bool | None = None
    selected_option_keys: tuple[str, ...] | None = None


@dataclass(frozen=True)
class CareerRequirementInput:
    category: str  # RequirementCategory.value
    certainty: str  # RequirementCertainty.value
    description: str


@dataclass(frozen=True)
class CareerSkillInput:
    label: str
    requirement_type: str  # "required" | "preferred" | "useful"


@dataclass(frozen=True)
class SkillCheck:
    label: str
    status: str  # "present" | "confirmed_missing" | "unknown"


@dataclass(frozen=True)
class FeasibilityResult:
    status: str
    raw_score: float | None
    band: str | None
    hard_barriers: tuple[str, ...]
    soft_barriers: tuple[str, ...]
    information_gaps: tuple[str, ...]
    skills_to_verify: tuple[SkillCheck, ...]


def compute_feasibility(
    *,
    constraints: dict[str, ConstraintAnswer],
    career_requirements: list[CareerRequirementInput],
    career_skills: list[CareerSkillInput],
    career_work_format_setting: str | None,
    job_zone: int | None,
    config: MatchingConfig,
) -> FeasibilityResult:
    """Deterministic V1 Feasibility, `MNP_GOLDEN_TEST_V0.1.md` §20-22.

    Hard-gate invariant (Founder Review §9, binding): a hard barrier can
    ONLY fire for a `CareerRequirement` with `certainty == "hard_factual"`
    AND an explicit (non-None) user constraint answer that is
    incompatible. `certainty == "typical_recommendation"` never blocks
    (soft barrier only); `certainty == "unknown"` never blocks and is
    never even a soft barrier (too uncertain to assert anything from).
    A missing user answer is an information gap, never treated as
    confirming or denying a requirement.
    """

    hard_barriers: list[str] = []
    soft_barriers: list[str] = []
    information_gaps: list[str] = []

    credential = constraints.get("credential_legal")
    for req in career_requirements:
        if req.category not in _HARD_BLOCK_ELIGIBLE_CATEGORIES:
            continue
        if req.certainty == "unknown":
            continue  # never a barrier, never a gap -- too uncertain to assert anything
        if credential is None or credential.boolean_value is None:
            information_gaps.append(f"license/credential status not answered (relevant to: {req.description})")
            continue
        if credential.boolean_value is False:
            if req.certainty == "hard_factual":
                hard_barriers.append(f"Requires {req.category} (authoritative, unmet): {req.description}")
            elif req.certainty == "typical_recommendation":
                soft_barriers.append(f"Typically requires {req.category}: {req.description}")

    language = constraints.get("language")
    for req in career_requirements:
        if req.category != "language" or req.certainty == "unknown":
            continue
        if language is None or not language.selected_option_keys:
            information_gaps.append(f"language proficiency not answered (relevant to: {req.description})")
        elif language.selected_option_keys[0] in ("none", "basic"):
            soft_barriers.append(f"Language requirement noted: {req.description}")
        # certainty is never hard_factual for language in the current curated
        # data, but if it ever were, this loop still only ever appends to
        # soft_barriers for language -- language never hard-blocks in V1 by
        # design, since no structured "authoritative minimum level" exists
        # to compare against.

    education_below_typical = False
    education = constraints.get("education")
    if job_zone is not None:
        if education is None or not education.selected_option_keys:
            information_gaps.append("education level not answered")
        else:
            edu_rank = _EDUCATION_RANK.get(education.selected_option_keys[0])
            min_rank = _JOB_ZONE_MIN_EDUCATION_RANK.get(job_zone)
            if edu_rank is not None and min_rank is not None and edu_rank < min_rank:
                education_below_typical = True
                soft_barriers.append(
                    f"Career typically expects O*NET Job Zone {job_zone} preparation; stated education may be below the typical level"
                )

    work_format_mismatch = False
    work_format = constraints.get("work_format")
    if career_work_format_setting is not None:
        if work_format is None or not work_format.selected_option_keys:
            information_gaps.append("preferred work format not answered")
        else:
            answer = work_format.selected_option_keys[0]
            compatible = _WORK_FORMAT_COMPATIBLE_SETTINGS.get(answer, set())
            if career_work_format_setting not in compatible:
                work_format_mismatch = True
                soft_barriers.append(
                    f"Preferred work format ({answer}) may not match this career's typical setting ({career_work_format_setting})"
                )

    family_logistics_significant = False
    family_logistics = constraints.get("family_logistics")
    if family_logistics is not None and family_logistics.selected_option_keys:
        if family_logistics.selected_option_keys[0] == "significant":
            family_logistics_significant = True
            soft_barriers.append("Family/logistics constraints noted as significant")

    skills_to_verify = tuple(
        SkillCheck(label=skill.label, status=SKILL_UNKNOWN)
        for skill in career_skills
        if skill.requirement_type == "required"
    )

    financial_capacity = constraints.get("financial_capacity")
    no_capacity_with_skills_gap = bool(skills_to_verify) and financial_capacity is not None and financial_capacity.boolean_value is False

    if hard_barriers:
        return FeasibilityResult(
            status=FEASIBILITY_BLOCKED,
            raw_score=None,
            band=None,
            hard_barriers=tuple(hard_barriers),
            soft_barriers=tuple(soft_barriers),
            information_gaps=tuple(information_gaps),
            skills_to_verify=skills_to_verify,
        )

    has_any_career_data = bool(career_requirements) or bool(career_skills) or job_zone is not None
    if not has_any_career_data:
        return FeasibilityResult(
            status=FEASIBILITY_INSUFFICIENT_DATA,
            raw_score=None,
            band=None,
            hard_barriers=(),
            soft_barriers=tuple(soft_barriers),
            information_gaps=tuple(information_gaps),
            skills_to_verify=skills_to_verify,
        )

    score = 1.0
    if education_below_typical:
        score *= config.feasibility_education_penalty
    if work_format_mismatch:
        score *= config.feasibility_work_format_penalty
    if family_logistics_significant:
        score *= config.feasibility_family_logistics_penalty
    if no_capacity_with_skills_gap:
        score *= config.feasibility_no_capacity_skills_gap_penalty

    band = _band_for(score, config)
    status = FEASIBILITY_FEASIBLE if not (soft_barriers or information_gaps or skills_to_verify) else FEASIBILITY_PARTIAL

    return FeasibilityResult(
        status=status,
        raw_score=score,
        band=band,
        hard_barriers=(),
        soft_barriers=tuple(soft_barriers),
        information_gaps=tuple(information_gaps),
        skills_to_verify=skills_to_verify,
    )
