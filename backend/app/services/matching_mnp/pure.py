"""Pure, dependency-free Fit computations (`MNP_MATCHING_MATH_V1`). Every
function takes plain dataclasses/dicts and returns a `FitResult` --
`engine.py` is the only place that touches the DB. `Confidence != Match`
(Methodology §32/§19): a component's `confidence_band` never feeds back
into its own `score`, it only gates/tie-breaks at the ranking layer."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.services.matching_mnp.config import (
    IMPORTANCE_WEIGHTS,
    PREFERENCE_ATTRIBUTE_MAPPING,
    PROFICIENCY_NUMERIC,
    coverage_to_confidence_band,
    score_to_band,
)

STATUS_SCORED = "scored"
STATUS_INSUFFICIENT_DATA = "insufficient_data"


@dataclass(frozen=True)
class FitResult:
    status: str  # STATUS_SCORED | STATUS_INSUFFICIENT_DATA
    score: float | None
    band: str | None
    confidence_band: str
    coverage_ratio: float
    explanation_code: str
    detail: dict = field(default_factory=dict)


def _insufficient(explanation_code: str, detail: dict | None = None) -> FitResult:
    return FitResult(
        status=STATUS_INSUFFICIENT_DATA, score=None, band=None, confidence_band="insufficient",
        coverage_ratio=0.0, explanation_code=explanation_code, detail=detail or {},
    )


# ---------------------------------------------------------------------------
# Skill Fit / Knowledge Fit -- structurally identical weighted-coverage
# formula (Methodology §19): SkillFit = Σ(importance x level_adequacy x
# evidence_strength) / Σ(importance), computed ONLY over requirements the
# person has ANY evidence for. A requirement with no matching PersonSkill/
# PersonKnowledge is a gap candidate, never scored as 0 (UNKNOWN != a
# confirmed absence, MNP_EVIDENCE_AND_CONFIDENCE_MODEL_V1 §16) -- it
# simply lowers `coverage_ratio`, which drives `confidence_band`, not
# `score` itself.

@dataclass(frozen=True)
class RequirementInput:
    key: str
    importance: str  # low | medium | high | critical
    required_level: str  # basic | working | strong


@dataclass(frozen=True)
class PersonLevelInput:
    key: str
    proficiency_level: str  # basic | working | strong
    evidence_strength: float


def compute_weighted_coverage_fit(
    requirements: list[RequirementInput], person_levels: dict[str, PersonLevelInput], *,
    min_matched: int = 1, explanation_prefix: str = "weighted_coverage",
) -> FitResult:
    if not requirements:
        return _insufficient(f"{explanation_prefix}_no_requirements")

    total_importance = 0.0
    numerator = 0.0
    matched_keys: list[str] = []
    gap_keys: list[str] = []

    for req in requirements:
        weight = IMPORTANCE_WEIGHTS[req.importance]
        total_importance += weight
        person = person_levels.get(req.key)
        if person is None:
            gap_keys.append(req.key)
            continue
        matched_keys.append(req.key)
        required_numeric = PROFICIENCY_NUMERIC[req.required_level]
        person_numeric = PROFICIENCY_NUMERIC[person.proficiency_level]
        adequacy = min(1.0, person_numeric / required_numeric) if required_numeric > 0 else 1.0
        numerator += weight * adequacy * person.evidence_strength

    coverage_ratio = len(matched_keys) / len(requirements)

    if len(matched_keys) < min_matched:
        # Genuinely unknown, not "confirmed you lack everything" -- no
        # fabricated low score.
        return _insufficient(f"{explanation_prefix}_no_matched_requirements", {"gap": gap_keys})

    score = numerator / total_importance if total_importance > 0 else 0.0
    return FitResult(
        status=STATUS_SCORED, score=score, band=score_to_band(score),
        confidence_band=coverage_to_confidence_band(coverage_ratio), coverage_ratio=coverage_ratio,
        explanation_code=explanation_prefix, detail={"matched": matched_keys, "gap": gap_keys},
    )


# ---------------------------------------------------------------------------
# Preference Fit -- Methodology §21: PreferenceProfile vs CareerAttribute
# work_context signals, 1 - |difference| per comparable pair, averaged.

@dataclass(frozen=True)
class PreferenceFitInput:
    person_values: dict[str, float]  # PreferenceProfile field name -> 0..1 value (only non-null fields)
    career_values: dict[str, float]  # CareerAttribute.attribute_key -> 0..1 value


def compute_preference_fit(inputs: PreferenceFitInput, *, min_comparable: int = 2) -> FitResult:
    comparable: list[tuple[str, float]] = []
    for career_key, (person_field, invert) in PREFERENCE_ATTRIBUTE_MAPPING.items():
        career_value = inputs.career_values.get(career_key)
        person_value = inputs.person_values.get(person_field)
        if career_value is None or person_value is None:
            continue
        career_value_normalized = (1.0 - career_value) if invert else career_value
        comparable.append((career_key, 1.0 - abs(career_value_normalized - person_value)))

    if len(comparable) < min_comparable:
        return _insufficient("preference_fit_insufficient_comparable_signals")

    score = sum(v for _, v in comparable) / len(comparable)
    coverage_ratio = len(comparable) / len(PREFERENCE_ATTRIBUTE_MAPPING)
    return FitResult(
        status=STATUS_SCORED, score=score, band=score_to_band(score),
        confidence_band=coverage_to_confidence_band(coverage_ratio), coverage_ratio=coverage_ratio,
        explanation_code="preference_fit", detail={"compared": [k for k, _ in comparable]},
    )


# ---------------------------------------------------------------------------
# Experience Transfer -- Methodology §20: functions/domain proximity,
# management, complexity, seniority. V1 uses only the signals the domain
# model can actually support without free-text semantic matching (no LLM
# tokens): domain proximity via MnpCareerAlias-resolved
# `normalized_career_id` (same career / same family / neither), and an
# explicit management-experience match against whether the target career
# has ANY MANAGEMENT-type skill requirement.

@dataclass(frozen=True)
class ExperienceTransferInput:
    has_any_experience: bool
    matches_target_career: bool  # some Experience.normalized_career_id == target career
    matches_target_family: bool  # some Experience row resolves to a career in the same family
    has_management_experience: bool
    target_career_needs_management: bool


def compute_experience_transfer(inputs: ExperienceTransferInput) -> FitResult:
    if not inputs.has_any_experience:
        return _insufficient("experience_transfer_no_experience_recorded")

    if inputs.matches_target_career:
        domain_score = 1.0
        domain_label = "same_career"
    elif inputs.matches_target_family:
        domain_score = 0.6
        domain_label = "same_family"
    else:
        domain_score = 0.25  # some general work experience always transfers a little -- never zero
        domain_label = "unrelated_domain"

    if inputs.target_career_needs_management:
        management_score = 1.0 if inputs.has_management_experience else 0.3
    else:
        management_score = 1.0  # not needed -- never penalizes for lacking it

    score = 0.7 * domain_score + 0.3 * management_score
    # Always "comparable" once any experience exists -- coverage isn't
    # partial the way multi-requirement Skill Fit is.
    return FitResult(
        status=STATUS_SCORED, score=score, band=score_to_band(score), confidence_band="high", coverage_ratio=1.0,
        explanation_code="experience_transfer", detail={"domain": domain_label, "management_relevant": inputs.target_career_needs_management},
    )
