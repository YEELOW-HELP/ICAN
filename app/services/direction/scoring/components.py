"""Deterministic score components (Career Fit / Direction Evaluation Model
v0.1 section 3).

Each component compares ONE compatible structured pair and returns a
`ScoreComponentResult`. `SCORED` only when a real comparable pair exists;
otherwise `INSUFFICIENT_DATA` (never zero -- Founder decision F). No LLM.

v0.1 implements three real Potential Fit scorers (`pf_interests`,
`pf_skills_match`, `pf_work_environment`) and one real Transition
Feasibility scorer (`tf_skill_gap`, using the PRESENT/CONFIRMED_MISSING/
UNKNOWN model -- Founder decision P). Every other component is registered,
enabled, and returns `INSUFFICIENT_DATA` with a documented reason, per the
Model's v0.1 status table. They become real as methodology + KB curation
supply the missing structured pair.
"""

from __future__ import annotations

from collections.abc import Callable

from app.services.direction.dimensions import CanonicalDimension
from app.services.direction.scoring.base import (
    OutputFamily,
    ScoreComponentResult,
    ScoreComponentStatus,
    ScoreContext,
    _claims_for,
    insufficient,
)
from app.services.direction.scoring.skill_state import SkillState, classify_required_skills

__all__ = ["COMPONENTS", "score_component", "score_family"]

_PF = OutputFamily.POTENTIAL_FIT
_GA = OutputFamily.GOAL_ALIGNMENT
_TF = OutputFamily.TRANSITION_FEASIBILITY

_INTEREST_SIGNAL_MAP: tuple[tuple[tuple[str, ...], str], ...] = (
    (("people_facing_work", "people", "робота з людьми", "люди"), "works_with_people"),
    (("technical_problem_solving", "technical", "техніч", "технич", "engineering"), "works_with_technology"),
    (("creative_expression", "creative", "творч", "design", "дизайн"), "creative_component"),
    (("data", "analytics", "аналіз", "анализ", "research"), "works_with_data"),
)


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


# ---------------------------------------------------------------- Potential Fit


def pf_interests(ctx: ScoreContext) -> ScoreComponentResult:
    claims = _claims_for(ctx, CanonicalDimension.INTERESTS)
    if not claims:
        return insufficient("pf_interests", _PF, "no usable Interests claims")

    pairs: list[tuple[str, float]] = []
    used_claim_ids = []
    for mc in claims:
        haystack = f"{mc.legacy_term_key or ''} {mc.label} {mc.normalized_value}".lower()
        for needles, char_key in _INTEREST_SIGNAL_MAP:
            if any(n in haystack for n in needles):
                value = ctx.career_characteristics.get(char_key)
                if value is not None:
                    pairs.append((char_key, float(value)))
                    used_claim_ids.append(mc.source_claim_id)
                break

    if not pairs:
        return insufficient(
            "pf_interests",
            _PF,
            "Interests claims could not be matched to a curated career characteristic",
        )

    raw = _clamp01(sum(v for _, v in pairs) / len(pairs))
    return ScoreComponentResult(
        component_key="pf_interests",
        family=_PF,
        status=ScoreComponentStatus.SCORED,
        raw_score=raw,
        rationale=(
            f"mean alignment of {len(pairs)} interest signal(s) with curated career characteristics "
            f"({', '.join(sorted({k for k, _ in pairs}))})"
        ),
        contributing_claim_ids=tuple(c for c in used_claim_ids if c is not None),
        contributing_career_attributes={k: v for k, v in pairs},
    )


def pf_skills_match(ctx: ScoreContext) -> ScoreComponentResult:
    if not ctx.career_skills:
        return insufficient("pf_skills_match", _PF, "career has no curated CareerSkill rows")

    present_terms: set[str] = set()
    used_claim_ids = []
    for mc in _claims_for(ctx, CanonicalDimension.SKILLS):
        if mc.legacy_term_key and mc.claim_status == "supported":
            present_terms.add(mc.legacy_term_key)
            used_claim_ids.append(mc.source_claim_id)

    if not present_terms:
        return insufficient(
            "pf_skills_match",
            _PF,
            "no SUPPORTED profile Skills claims with a resolvable term_key",
        )

    weight = {"required": 1.0, "preferred": 0.6, "useful": 0.3}
    total = sum(weight.get(s.requirement_type, 0.3) for s in ctx.career_skills)
    covered = sum(
        weight.get(s.requirement_type, 0.3) for s in ctx.career_skills if s.term_key in present_terms
    )
    raw = _clamp01(covered / total) if total > 0 else 0.0
    return ScoreComponentResult(
        component_key="pf_skills_match",
        family=_PF,
        status=ScoreComponentStatus.SCORED,
        raw_score=raw,
        rationale=(
            f"{len([s for s in ctx.career_skills if s.term_key in present_terms])}/{len(ctx.career_skills)} "
            "curated career skills covered by SUPPORTED profile Skills claims (overlap only -- never a gap penalty)"
        ),
        contributing_claim_ids=tuple(c for c in used_claim_ids if c is not None),
        contributing_career_attributes={"matched_terms": sorted(present_terms & {s.term_key for s in ctx.career_skills})},
    )


def pf_work_environment(ctx: ScoreContext) -> ScoreComponentResult:
    claims = _claims_for(ctx, CanonicalDimension.WORK_ENVIRONMENT)
    if not claims:
        return insufficient("pf_work_environment", _PF, "no usable Work Environment claims")

    facet_scores: list[float] = []
    used_claim_ids = []
    attrs: dict = {}

    teamwork = ctx.work_context.get("teamwork_level")
    setting = ctx.work_context.get("setting")

    for mc in claims:
        val = (mc.normalized_value or "").lower()
        sub = mc.canonical_subdimension
        if sub == "collaboration_context" and teamwork is not None:
            wants_team = any(k in val for k in ("team", "collaborat", "команд", "разом", "вместе"))
            wants_solo = any(k in val for k in ("alone", "independent", "solo", "самостійн", "один", "самостоятельн"))
            if wants_team:
                facet_scores.append(_clamp01(float(teamwork)))
                used_claim_ids.append(mc.source_claim_id)
                attrs["teamwork_level"] = teamwork
            elif wants_solo:
                facet_scores.append(_clamp01(1.0 - float(teamwork)))
                used_claim_ids.append(mc.source_claim_id)
                attrs["teamwork_level"] = teamwork
        elif sub == "setting" and setting is not None:
            wants_remote = any(k in val for k in ("remote", "from home", "віддален", "удал", "дистанц"))
            if wants_remote:
                facet_scores.append(1.0 if str(setting) in ("remote", "mixed", "WorkSetting.REMOTE", "WorkSetting.MIXED") else 0.0)
                used_claim_ids.append(mc.source_claim_id)
                attrs["setting"] = str(setting)

    if not facet_scores:
        return insufficient(
            "pf_work_environment",
            _PF,
            "Work Environment claims could not be matched to a curated CareerWorkContext facet",
        )

    raw = _clamp01(sum(facet_scores) / len(facet_scores))
    return ScoreComponentResult(
        component_key="pf_work_environment",
        family=_PF,
        status=ScoreComponentStatus.SCORED,
        raw_score=raw,
        rationale=f"mean alignment over {len(facet_scores)} work-environment facet(s) present on both sides",
        contributing_claim_ids=tuple(c for c in used_claim_ids if c is not None),
        contributing_career_attributes=attrs,
    )


def _pf_stub(key: str, reason: str):
    def _fn(ctx: ScoreContext) -> ScoreComponentResult:
        return insufficient(key, _PF, reason)

    return _fn


# ---------------------------------------------------------------- Goal Alignment
# All INSUFFICIENT_DATA in legacy v0.1 (Career Fit / Direction Eval Model 3.2;
# Founder decision B for decision-relevant Values).


def _ga_stub(key: str, reason: str):
    def _fn(ctx: ScoreContext) -> ScoreComponentResult:
        return insufficient(key, _GA, reason)

    return _fn


# ------------------------------------------------------- Transition Feasibility


def tf_skill_gap(ctx: ScoreContext) -> ScoreComponentResult:
    required = [s.term_key for s in ctx.career_skills if s.requirement_type == "required"]
    if not required:
        return insufficient(
            "tf_skill_gap",
            _TF,
            "career lists no required skills -- nothing to assess",
            skills_to_verify=[],
        )

    classifications = classify_required_skills(required, ctx.mapped_claims)
    present = [c for c in classifications if c.state is SkillState.PRESENT]
    confirmed_missing = [c for c in classifications if c.state is SkillState.CONFIRMED_MISSING]
    unknown = [c for c in classifications if c.state is SkillState.UNKNOWN]
    assessed = len(present) + len(confirmed_missing)

    if assessed == 0:
        # Every required skill is UNKNOWN -- we cannot infer a gap
        # (UNKNOWN != NEGATIVE, Founder decision P). Verify, don't penalise.
        return insufficient(
            "tf_skill_gap",
            _TF,
            f"all {len(required)} required skills are UNKNOWN -- insufficient evidence to assess skill gaps",
            skills_to_verify=[c.term_key for c in unknown],
            coverage=0.0,
        )

    raw = _clamp01(1.0 - (len(confirmed_missing) / assessed))
    return ScoreComponentResult(
        component_key="tf_skill_gap",
        family=_TF,
        status=ScoreComponentStatus.SCORED,
        raw_score=raw,
        rationale=(
            f"{len(confirmed_missing)} confirmed-missing of {assessed} assessed required skills "
            f"({len(present)} present); {len(unknown)} still UNKNOWN and flagged for verification"
        ),
        contributing_claim_ids=(),
        contributing_career_attributes={
            "present": [c.term_key for c in present],
            "confirmed_missing": [c.term_key for c in confirmed_missing],
            "skills_to_verify": [c.term_key for c in unknown],
            "coverage": assessed / len(required),
        },
    )


def _tf_stub(key: str, reason: str):
    def _fn(ctx: ScoreContext) -> ScoreComponentResult:
        return insufficient(key, _TF, reason)

    return _fn


# ---------------------------------------------------------------- registry

COMPONENTS: dict[str, Callable[[ScoreContext], ScoreComponentResult]] = {
    # Potential Fit
    "pf_interests": pf_interests,
    "pf_strengths": _pf_stub("pf_strengths", "no structured Strengths->career mapping in v0.1"),
    "pf_skills_match": pf_skills_match,
    "pf_work_style": _pf_stub("pf_work_style", "no structured career-side counterpart for Work Style in KB v1"),
    "pf_work_environment": pf_work_environment,
    "pf_values_general": _pf_stub("pf_values_general", "no structured career-side values data in KB v1"),
    "pf_experience_relevance": _pf_stub(
        "pf_experience_relevance", "no structured user Experience representation in v0.1"
    ),
    # Goal Alignment (all INSUFFICIENT_DATA in legacy v0.1)
    "ga_goals": _ga_stub("ga_goals", "no structured career goal-target data in KB v1"),
    "ga_motivation": _ga_stub("ga_motivation", "no structured career-side motivation counterpart"),
    "ga_decision_relevant_values": _ga_stub(
        "ga_decision_relevant_values",
        "legacy Value claims carry no decision-relevance marker (Founder decision B) -- general Values feed Potential Fit only",
    ),
    # Transition Feasibility
    "tf_skill_gap": tf_skill_gap,
    "tf_abilities_learning": _tf_stub(
        "tf_abilities_learning", "Abilities & Learning Potential has no legacy claim source (MNP-HPM 4.3)"
    ),
    "tf_career_adaptability": _tf_stub(
        "tf_career_adaptability", "no structured adaptability<->requirement-load model in v0.1"
    ),
    "tf_constraint_load": _tf_stub(
        "tf_constraint_load", "soft-constraint scoring is a later slice; no confirmed non-hard constraint model yet"
    ),
    "tf_requirement_barriers": _tf_stub(
        "tf_requirement_barriers",
        "a career requirement existing is not evidence the user cannot meet it (UNKNOWN != NEGATIVE)",
    ),
}


def score_component(component_key: str, ctx: ScoreContext) -> ScoreComponentResult:
    return COMPONENTS[component_key](ctx)


def score_family(component_keys, ctx: ScoreContext) -> list[ScoreComponentResult]:
    return [score_component(k, ctx) for k in component_keys]
