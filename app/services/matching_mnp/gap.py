"""Personal Skill Gap + Learning Priority (`MNP_SKILL_GAP_AND_PRIORITY_V1`).

Gap state per requirement:
- MATCH: PersonSkill exists and meets/exceeds the required level.
- PARTIAL_GAP: PersonSkill exists but below the required level.
- UNKNOWN: no PersonSkill row at all -- **never** silently treated as a
  confirmed absence (MNP_EVIDENCE_AND_CONFIDENCE_MODEL_V1 §16). FULL_GAP
  is reserved for a future explicit "I do not have this" negative
  signal, which no current input flow (resume parser, questionnaire)
  collects -- a documented simplification, not a silent gap in this
  pass; it is simply never emitted in v0.1.

Priority = importance x gap_size x market_value x learnability /
time_cost (MNP_SKILL_GAP_AND_PRIORITY_V1 "Priority"). No market
ingestion and no learning-time taxonomy exist yet, so market_value/
learnability/time_cost are held at the neutral default from `config.py`
-- Priority reduces to importance x gap_size in this pass, a disclosed
simplification, never a fabricated market/learnability number."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.matching_mnp.config import (
    DEFAULT_LEARNABILITY,
    DEFAULT_MARKET_VALUE,
    IMPORTANCE_WEIGHTS,
    PROFICIENCY_NUMERIC,
)

STATE_MATCH = "match"
STATE_PARTIAL_GAP = "partial_gap"
STATE_UNKNOWN = "unknown"

CLASS_MUST_HAVE = "must_have"
CLASS_HIGH_VALUE = "high_value"
CLASS_DIFFERENTIATOR = "differentiator"
CLASS_OPTIONAL = "optional"

ACTION_LEARN = "learn"
ACTION_PRACTICE = "practice"
ACTION_REFRAME = "reframe"


@dataclass(frozen=True)
class SkillGapInput:
    skill_key: str
    skill_label: str
    importance: str
    required_level: str
    requirement_type: str  # must_have | high_value | differentiator | optional
    person_proficiency: str | None  # None if no PersonSkill row exists


@dataclass(frozen=True)
class PersonalGapResult:
    gap_type: str  # always "skill" in this module
    reference_key: str
    reference_label: str
    state: str
    classification: str
    action: str
    priority_internal: float


def _classify_state(person_proficiency: str | None, required_level: str) -> str:
    if person_proficiency is None:
        return STATE_UNKNOWN
    adequacy = min(1.0, PROFICIENCY_NUMERIC[person_proficiency] / PROFICIENCY_NUMERIC[required_level])
    return STATE_MATCH if adequacy >= 1.0 else STATE_PARTIAL_GAP


def _gap_size(state: str, person_proficiency: str | None, required_level: str) -> float:
    if state == STATE_UNKNOWN:
        return 1.0  # full potential gap for priority-sorting purposes only -- not a factual claim
    if state == STATE_PARTIAL_GAP:
        adequacy = min(1.0, PROFICIENCY_NUMERIC[person_proficiency] / PROFICIENCY_NUMERIC[required_level])
        return 1.0 - adequacy
    return 0.0


def _choose_action(state: str, requirement_type: str) -> str:
    if requirement_type == CLASS_DIFFERENTIATOR:
        return ACTION_REFRAME
    if state == STATE_PARTIAL_GAP:
        return ACTION_PRACTICE
    return ACTION_LEARN


def compute_skill_gaps(requirements: list[SkillGapInput]) -> list[PersonalGapResult]:
    """Returns one `PersonalGapResult` per requirement NOT already a
    MATCH -- callers show only the top 3-5 by `priority_internal`
    (MNP_SKILL_GAP_AND_PRIORITY_V1 "UX")."""

    results: list[PersonalGapResult] = []
    for req in requirements:
        state = _classify_state(req.person_proficiency, req.required_level)
        if state == STATE_MATCH:
            continue
        gap_size = _gap_size(state, req.person_proficiency, req.required_level)
        priority = IMPORTANCE_WEIGHTS[req.importance] * gap_size * DEFAULT_MARKET_VALUE * DEFAULT_LEARNABILITY
        results.append(
            PersonalGapResult(
                gap_type="skill", reference_key=req.skill_key, reference_label=req.skill_label, state=state,
                classification=req.requirement_type, action=_choose_action(state, req.requirement_type),
                priority_internal=priority,
            )
        )
    results.sort(key=lambda r: r.priority_internal, reverse=True)
    return results
