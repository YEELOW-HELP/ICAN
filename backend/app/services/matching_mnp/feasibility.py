"""Deterministic Feasibility gate-then-ladder (`MNP_FEASIBILITY_RULES_V1`).
BLOCKED requires an authoritative HARD requirement contradicted by an
explicit fact -- never a preference mismatch, never a missing answer
(MNP_EVIDENCE_AND_CONFIDENCE_MODEL_V1 §20/§16: a missing user answer is
an information gap, not an assumed fail). Statuses: READY_NOW /
NEAR_READY / REACHABLE / LONG_TRANSITION / BLOCKED, per the doc's own
"Suggested interpretation" ladder."""

from __future__ import annotations

from dataclasses import dataclass, field

READY_NOW = "ready_now"
NEAR_READY = "near_ready"
REACHABLE = "reachable"
LONG_TRANSITION = "long_transition"
BLOCKED = "blocked"

OUTCOME_PASS = "pass"
OUTCOME_GAP = "gap"
OUTCOME_BLOCKER = "blocker"
OUTCOME_UNKNOWN = "unknown"

# A single ordered scale covering every canonical education level string
# this codebase produces (`patterns.EDUCATION_LEVEL_KEYWORDS` values).
_EDUCATION_RANK = {"junior_specialist": 0, "specialist": 1, "bachelor": 2, "master": 3, "phd": 4}

# Covers every canonical language-level string this codebase produces
# (`patterns.LANGUAGE_LEVEL_WORDS` values) plus raw CEFR codes.
_LANGUAGE_RANK = {
    "a1": 0, "elementary": 0, "a2": 1, "b1": 2, "intermediate": 2, "b2": 3, "upper_intermediate": 3,
    "c1": 4, "advanced": 4, "c2": 5, "fluent": 5, "native": 6,
}


@dataclass(frozen=True)
class RequirementCheckInput:
    category: str  # education | experience | credential | language | legal | other
    hardness: str  # soft | hard
    value: str | None  # e.g. "bachelor", "1_year", "certified_accountant", "en:b2"
    description: str


@dataclass(frozen=True)
class PersonFactsForFeasibility:
    education_levels: set[str] = field(default_factory=set)
    credential_names_normalized: set[str] = field(default_factory=set)
    language_levels: dict[str, str] = field(default_factory=dict)  # code -> level
    total_experience_months: int | None = None
    has_any_education_data: bool = False
    has_any_credential_data: bool = False


def _check_education(value: str | None, facts: PersonFactsForFeasibility) -> str:
    if not facts.has_any_education_data:
        return OUTCOME_UNKNOWN
    if value is None or value not in _EDUCATION_RANK:
        return OUTCOME_PASS if facts.education_levels else OUTCOME_UNKNOWN
    required_rank = _EDUCATION_RANK[value]
    best_held = max((_EDUCATION_RANK[l] for l in facts.education_levels if l in _EDUCATION_RANK), default=None)
    if best_held is None:
        return OUTCOME_UNKNOWN
    return OUTCOME_PASS if best_held >= required_rank else OUTCOME_GAP


def _check_experience(value: str | None, facts: PersonFactsForFeasibility) -> str:
    if facts.total_experience_months is None:
        return OUTCOME_UNKNOWN
    if value is None or not value.endswith("_year"):
        return OUTCOME_PASS
    try:
        required_years = float(value.split("_")[0])
    except ValueError:
        return OUTCOME_UNKNOWN
    return OUTCOME_PASS if facts.total_experience_months >= required_years * 12 else OUTCOME_GAP


def _check_credential(value: str | None, facts: PersonFactsForFeasibility) -> str:
    if not facts.has_any_credential_data:
        return OUTCOME_UNKNOWN
    if value is None:
        return OUTCOME_PASS if facts.credential_names_normalized else OUTCOME_UNKNOWN
    normalized_value = value.strip().lower()
    return OUTCOME_PASS if any(normalized_value in name for name in facts.credential_names_normalized) else OUTCOME_GAP


def _check_language(value: str | None, facts: PersonFactsForFeasibility) -> str:
    if value is None or ":" not in value:
        return OUTCOME_UNKNOWN
    code, required_level = value.split(":", 1)
    held_level = facts.language_levels.get(code)
    if held_level is None:
        return OUTCOME_UNKNOWN
    required_rank = _LANGUAGE_RANK.get(required_level)
    held_rank = _LANGUAGE_RANK.get(held_level)
    if required_rank is None or held_rank is None:
        return OUTCOME_UNKNOWN
    return OUTCOME_PASS if held_rank >= required_rank else OUTCOME_GAP


_CHECKERS = {
    "education": _check_education,
    "experience": _check_experience,
    "credential": _check_credential,
    "legal": _check_credential,  # legal permits/licenses use the same "named item held" shape as credentials
    "language": _check_language,
}


def resolve_requirement_outcome(requirement: RequirementCheckInput, facts: PersonFactsForFeasibility) -> str:
    """A HARD requirement's `gap` outcome escalates to `blocker`; UNKNOWN
    never escalates, regardless of hardness (a HARD requirement can only
    ever be `blocker` when we hold an actual contradicting fact,
    MNP_EVIDENCE_AND_CONFIDENCE_MODEL_V1 §20)."""

    checker = _CHECKERS.get(requirement.category)
    if checker is None:
        return OUTCOME_UNKNOWN
    outcome = checker(requirement.value, facts)
    if outcome == OUTCOME_GAP and requirement.hardness == "hard":
        return OUTCOME_BLOCKER
    return outcome


@dataclass(frozen=True)
class FeasibilityResult:
    status: str
    hard_blockers: list[str] = field(default_factory=list)
    soft_gaps: list[str] = field(default_factory=list)
    information_gaps: list[str] = field(default_factory=list)


def compute_feasibility(
    requirements: list[RequirementCheckInput], facts: PersonFactsForFeasibility,
) -> FeasibilityResult:
    hard_blockers: list[str] = []
    soft_gaps: list[str] = []
    information_gaps: list[str] = []

    for req in requirements:
        outcome = resolve_requirement_outcome(req, facts)
        if outcome == OUTCOME_BLOCKER:
            hard_blockers.append(req.description)
        elif outcome == OUTCOME_GAP:
            soft_gaps.append(req.description)
        elif outcome == OUTCOME_UNKNOWN:
            information_gaps.append(req.description)
        # OUTCOME_PASS contributes nothing to any list.

    if hard_blockers:
        status = BLOCKED
    elif len(soft_gaps) == 0:
        status = READY_NOW
    elif len(soft_gaps) == 1:
        status = NEAR_READY
    elif len(soft_gaps) <= 3:
        status = REACHABLE
    else:
        status = LONG_TRANSITION

    return FeasibilityResult(
        status=status, hard_blockers=hard_blockers, soft_gaps=soft_gaps, information_gaps=information_gaps,
    )
