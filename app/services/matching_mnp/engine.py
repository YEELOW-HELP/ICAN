"""DB orchestration for the Matching Engine: loads `MnpCareerCard` +
every ACTIVE `MnpCareer`, converts to the pure layer's plain inputs,
computes every Fit component, and persists `MnpMatchRun`/`MnpCareerMatch`/
`MnpMatchComponent`/`MnpFeasibilityFinding`/`MnpPersonalGap`/
`MnpCareerRoute`/`MnpRouteStep`. Every actual formula lives in the pure
modules (`pure.py`/`feasibility.py`/`transition.py`/`gap.py`/`ranking.py`/
`route.py`), which never import SQLAlchemy -- this module's only job is
fetch/convert/call/persist (mirrors this repo's own architecture
principle, `MNP_SYSTEM_ARCHITECTURE_V1` "Boundaries")."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models_career_card import (
    MnpCareerCard,
    MnpConstraint,
    MnpCredential,
    MnpEducation,
    MnpExperience,
    MnpLanguage,
    MnpPersonSkill,
    MnpPreferenceProfile,
)
from app.db.models_career_kb_mnp import (
    CareerLifecycleStatus,
    MnpCareer,
    MnpCareerAttribute,
    MnpCareerRequirement,
    MnpCareerSkillRequirement,
)
from app.db.models_matching_mnp import (
    ComponentBand,
    DisplayBand,
    FeasibilityStatus,
    MatchComponentType,
    MnpCareerMatch,
    MnpCareerRoute,
    MnpFeasibilityFinding,
    MnpMatchComponent,
    MnpMatchRun,
    MnpPersonalGap,
    MnpRouteStep,
    RouteStepType,
    RouteType,
    TransitionDistance,
)
from app.services.matching_mnp.config import MATCHING_ENGINE_VERSION, METHODOLOGY_VERSION, score_to_band
from app.services.matching_mnp.feasibility import (
    OUTCOME_BLOCKER,
    OUTCOME_GAP,
    OUTCOME_PASS,
    OUTCOME_UNKNOWN,
    PersonFactsForFeasibility,
    RequirementCheckInput,
    compute_feasibility,
    resolve_requirement_outcome,
)
from app.services.matching_mnp.gap import PersonalGapResult, SkillGapInput, compute_skill_gaps
from app.services.matching_mnp.pure import (
    ExperienceTransferInput,
    FitResult,
    PersonLevelInput,
    PreferenceFitInput,
    RequirementInput,
    STATUS_SCORED,
    compute_experience_transfer,
    compute_preference_fit,
    compute_weighted_coverage_fit,
)
from app.services.matching_mnp.ranking import BEST_FOR_ME, ComponentValue, compute_overall_score
from app.services.matching_mnp.route import build_route_steps
from app.services.matching_mnp.transition import (
    compute_transition_cost_score,
    compute_transition_distance,
    scenario_for_distance,
)

CAREER_KB_VERSION = "mnp_alpha_5_v0.1"
MARKET_DATA_VERSION = "mnp_no_market_data_v0.1"

_STEP_TYPE_MAP = {
    "existing_capital": RouteStepType.EXISTING_CAPITAL,
    "reframe_or_prove": RouteStepType.REFRAME_OR_PROVE,
    "learn_practice_certify": RouteStepType.LEARN_PRACTICE_CERTIFY,
    "first_evidence": RouteStepType.FIRST_EVIDENCE,
    "entry_opportunity": RouteStepType.ENTRY_OPPORTUNITY,
    "target_role": RouteStepType.TARGET_ROLE,
    "next_step": RouteStepType.NEXT_STEP,
}


async def _load_person_skill_levels(session: AsyncSession, career_card_id: uuid.UUID) -> dict[str, PersonLevelInput]:
    rows = (await session.execute(select(MnpPersonSkill).where(MnpPersonSkill.career_card_id == career_card_id))).scalars().all()
    return {
        str(row.skill_id): PersonLevelInput(
            key=str(row.skill_id), proficiency_level=row.proficiency_level.value, evidence_strength=row.evidence_strength,
        )
        for row in rows
    }


async def _load_person_facts(session: AsyncSession, career_card_id: uuid.UUID) -> PersonFactsForFeasibility:
    educations = (await session.execute(select(MnpEducation).where(MnpEducation.career_card_id == career_card_id))).scalars().all()
    credentials = (await session.execute(select(MnpCredential).where(MnpCredential.career_card_id == career_card_id))).scalars().all()
    languages = (await session.execute(select(MnpLanguage).where(MnpLanguage.career_card_id == career_card_id))).scalars().all()
    experiences = (await session.execute(select(MnpExperience).where(MnpExperience.career_card_id == career_card_id))).scalars().all()

    total_months = None
    if experiences:
        known = [e.duration_months for e in experiences if e.duration_months is not None]
        if known:
            total_months = sum(known)

    return PersonFactsForFeasibility(
        education_levels={e.level for e in educations if e.level and e.level != "unknown"},
        credential_names_normalized={c.name.strip().lower() for c in credentials},
        language_levels={l.language_code: l.overall_level for l in languages if l.overall_level},
        total_experience_months=total_months,
        has_any_education_data=bool(educations),
        has_any_credential_data=bool(credentials),
    )


async def _load_excluded_career_codes(session: AsyncSession, career_card_id: uuid.UUID) -> set[str]:
    rows = (
        await session.execute(
            select(MnpConstraint).where(
                MnpConstraint.career_card_id == career_card_id, MnpConstraint.constraint_type == "excluded_career",
                MnpConstraint.active.is_(True),
            )
        )
    ).scalars().all()
    return {row.value for row in rows}


async def _load_experience_transfer_input(
    session: AsyncSession, career_card_id: uuid.UUID, target_career: MnpCareer,
) -> ExperienceTransferInput:
    experiences = (await session.execute(select(MnpExperience).where(MnpExperience.career_card_id == career_card_id))).scalars().all()
    if not experiences:
        return ExperienceTransferInput(
            has_any_experience=False, matches_target_career=False, matches_target_family=False,
            has_management_experience=False, target_career_needs_management=False,
        )

    matched_career_ids = {e.normalized_career_id for e in experiences if e.normalized_career_id}
    matches_target_career = target_career.id in matched_career_ids

    matches_target_family = False
    if matched_career_ids:
        result = await session.execute(select(MnpCareer).where(MnpCareer.id.in_(matched_career_ids)))
        for matched_career in result.scalars().all():
            if matched_career.career_family_id == target_career.career_family_id:
                matches_target_family = True
                break

    has_management_experience = any(e.management_scope for e in experiences)

    from app.db.models_career_card import MnpSkill, SkillType

    management_requirement = await session.execute(
        select(MnpCareerSkillRequirement.skill_id).where(MnpCareerSkillRequirement.career_id == target_career.id)
    )
    required_skill_ids = [row[0] for row in management_requirement.all()]
    target_career_needs_management = False
    if required_skill_ids:
        skill_types = await session.execute(select(MnpSkill.skill_type).where(MnpSkill.id.in_(required_skill_ids)))
        target_career_needs_management = any(st == SkillType.MANAGEMENT for (st,) in skill_types.all())

    return ExperienceTransferInput(
        has_any_experience=True, matches_target_career=matches_target_career, matches_target_family=matches_target_family,
        has_management_experience=has_management_experience, target_career_needs_management=target_career_needs_management,
    )


async def _load_preference_fit_input(session: AsyncSession, career_card_id: uuid.UUID, target_career: MnpCareer) -> PreferenceFitInput:
    pref_row = (
        await session.execute(select(MnpPreferenceProfile).where(MnpPreferenceProfile.career_card_id == career_card_id))
    ).scalar_one_or_none()
    person_values: dict[str, float] = {}
    if pref_row is not None:
        for field_name in (
            "autonomy_preference", "teamwork_preference", "customer_interaction_preference",
            "routine_vs_novelty_preference", "leadership_preference", "physical_activity_preference",
        ):
            value = getattr(pref_row, field_name)
            if value is not None:
                person_values[field_name] = value

    attribute_rows = (
        await session.execute(
            select(MnpCareerAttribute).where(
                MnpCareerAttribute.career_id == target_career.id, MnpCareerAttribute.attribute_group == "work_context",
            )
        )
    ).scalars().all()
    career_values = {row.attribute_key: row.value_numeric for row in attribute_rows if row.value_numeric is not None}

    return PreferenceFitInput(person_values=person_values, career_values=career_values)


async def _compute_skill_fit(
    session: AsyncSession, career_id: uuid.UUID, person_levels: dict[str, PersonLevelInput],
) -> tuple[FitResult, list[MnpCareerSkillRequirement]]:
    requirement_rows = (
        await session.execute(
            select(MnpCareerSkillRequirement)
            .where(MnpCareerSkillRequirement.career_id == career_id)
            .options(selectinload(MnpCareerSkillRequirement.skill))
        )
    ).scalars().all()
    requirement_inputs = [
        RequirementInput(key=str(r.skill_id), importance=r.importance.value, required_level=r.required_level)
        for r in requirement_rows
    ]
    fit = compute_weighted_coverage_fit(requirement_inputs, person_levels)
    return fit, requirement_rows


async def _load_feasibility_requirements(
    session: AsyncSession, career_id: uuid.UUID,
) -> tuple[list[RequirementCheckInput], list[MnpCareerRequirement]]:
    rows = (await session.execute(select(MnpCareerRequirement).where(MnpCareerRequirement.career_id == career_id))).scalars().all()
    inputs = [
        RequirementCheckInput(category=r.category.value, hardness=r.hardness.value, value=r.value, description=r.description)
        for r in rows
    ]
    return inputs, rows


def _band_enum(band: str | None) -> ComponentBand | None:
    return ComponentBand(band) if band else None


async def _persist_component(
    session: AsyncSession, career_match: MnpCareerMatch, component_type: MatchComponentType, fit: FitResult,
) -> None:
    session.add(
        MnpMatchComponent(
            career_match_id=career_match.id, component_type=component_type, score_internal=fit.score,
            band=_band_enum(fit.band) or ComponentBand.INSUFFICIENT,
            confidence=ComponentBand(fit.confidence_band), explanation_code=fit.explanation_code, detail=fit.detail or None,
        )
    )


_INSUFFICIENT = FitResult(status="insufficient_data", score=None, band=None, confidence_band="insufficient", coverage_ratio=0.0, explanation_code="not_modeled_v0.1")


async def run_match(
    session: AsyncSession, *, career_card_id: uuid.UUID, ranking_mode: str = BEST_FOR_ME,
) -> MnpMatchRun:
    career_card = await session.get(MnpCareerCard, career_card_id)
    if career_card is None:
        raise ValueError(f"no MnpCareerCard {career_card_id}")

    person_levels = await _load_person_skill_levels(session, career_card_id)
    person_facts = await _load_person_facts(session, career_card_id)
    excluded_codes = await _load_excluded_career_codes(session, career_card_id)

    careers = (
        await session.execute(select(MnpCareer).where(MnpCareer.status == CareerLifecycleStatus.ACTIVE))
    ).scalars().all()
    careers = [c for c in careers if c.code not in excluded_codes]

    match_run = MnpMatchRun(
        career_card_id=career_card.id, career_card_version=career_card.version,
        assessment_session_id=career_card.assessment_session_id, methodology_version=METHODOLOGY_VERSION,
        matching_engine_version=MATCHING_ENGINE_VERSION, career_kb_version=CAREER_KB_VERSION,
        market_data_version=MARKET_DATA_VERSION, ranking_mode=ranking_mode,
    )
    session.add(match_run)
    await session.flush()

    scored_entries: list[tuple[MnpCareerMatch, float, str]] = []

    for career in careers:
        skill_fit, skill_requirement_rows = await _compute_skill_fit(session, career.id, person_levels)
        experience_input = await _load_experience_transfer_input(session, career_card_id, career)
        experience_transfer = compute_experience_transfer(experience_input)
        preference_input = await _load_preference_fit_input(session, career_card_id, career)
        preference_fit = compute_preference_fit(preference_input)

        feasibility_requirements, feasibility_requirement_rows = await _load_feasibility_requirements(session, career.id)
        feasibility = compute_feasibility(feasibility_requirements, person_facts)

        requires_hard_new_education = any(
            r.category == "education" and r.hardness == "hard" for r in feasibility_requirements
        )
        transition_distance = compute_transition_distance(
            domain_label=(
                "same_career" if experience_input.matches_target_career
                else "same_family" if experience_input.matches_target_family
                else "unrelated_domain"
            ),
            skill_fit_band=skill_fit.band, requires_hard_new_education=requires_hard_new_education,
        )
        transition_cost_score = compute_transition_cost_score(
            distance=transition_distance, soft_gap_count=len(feasibility.soft_gaps),
        )
        transition_cost_fit = FitResult(
            status=STATUS_SCORED, score=transition_cost_score, band=score_to_band(transition_cost_score),
            confidence_band="high", coverage_ratio=1.0, explanation_code="transition_cost_proxy_v0.1",
        )

        components: dict[str, ComponentValue] = {
            "skill_fit": ComponentValue(skill_fit.status, skill_fit.score),
            "experience_transfer": ComponentValue(experience_transfer.status, experience_transfer.score),
            "preference_fit": ComponentValue(preference_fit.status, preference_fit.score),
            "knowledge_fit": ComponentValue(_INSUFFICIENT.status, None),
            "values_fit": ComponentValue(_INSUFFICIENT.status, None),
            "market_attractiveness": ComponentValue(_INSUFFICIENT.status, None),
            "income_potential": ComponentValue(_INSUFFICIENT.status, None),
            "transition_cost": ComponentValue(transition_cost_fit.status, transition_cost_fit.score),
        }
        overall_score, participating = compute_overall_score(components, feasibility.status, mode=ranking_mode)

        career_match = MnpCareerMatch(
            match_run_id=match_run.id, career_id=career.id, rank_overall=0,
            overall_score_internal=overall_score,
            display_band=DisplayBand(score_to_band(overall_score)),
            feasibility_status=FeasibilityStatus(feasibility.status),
            transition_distance=TransitionDistance(transition_distance),
            confidence_internal=_band_enum(skill_fit.confidence_band) or ComponentBand.INSUFFICIENT,
            is_featured=False,
        )
        session.add(career_match)
        await session.flush()

        await _persist_component(session, career_match, MatchComponentType.SKILL_FIT, skill_fit)
        await _persist_component(session, career_match, MatchComponentType.EXPERIENCE_TRANSFER, experience_transfer)
        await _persist_component(session, career_match, MatchComponentType.PREFERENCE_FIT, preference_fit)
        await _persist_component(session, career_match, MatchComponentType.KNOWLEDGE_FIT, _INSUFFICIENT)
        await _persist_component(session, career_match, MatchComponentType.VALUES_FIT, _INSUFFICIENT)
        await _persist_component(session, career_match, MatchComponentType.MARKET_ATTRACTIVENESS, _INSUFFICIENT)
        await _persist_component(session, career_match, MatchComponentType.INCOME_POTENTIAL, _INSUFFICIENT)
        await _persist_component(session, career_match, MatchComponentType.TRANSITION_COST, transition_cost_fit)

        for req_input, req_row in zip(feasibility_requirements, feasibility_requirement_rows):
            outcome = resolve_requirement_outcome(req_input, person_facts)
            if outcome == OUTCOME_PASS:
                continue  # a clean pass is not a "finding" worth surfacing
            # MnpFeasibilityFinding.status only has PASS/GAP/BLOCKER
            # (MNP_DATA_MODEL_V1 §20, no 4th UNKNOWN value) -- an
            # information gap is filed as "gap" (never "pass", which
            # would falsely imply we confirmed the requirement is met);
            # `explanation_code` is what actually distinguishes a real
            # soft gap from a genuine unknown for any reader.
            status, explanation_code = {
                OUTCOME_BLOCKER: ("blocker", "feasibility_hard_blocker"),
                OUTCOME_GAP: ("gap", "feasibility_soft_gap"),
                OUTCOME_UNKNOWN: ("gap", "feasibility_information_gap"),
            }[outcome]
            session.add(MnpFeasibilityFinding(
                career_match_id=career_match.id, finding_type=req_input.category,
                severity=req_input.hardness, requirement_id=req_row.id, status=status,
                explanation_code=explanation_code,
            ))

        skill_gap_inputs = [
            SkillGapInput(
                skill_key=str(r.skill_id), skill_label=r.skill.canonical_name_uk, importance=r.importance.value,
                required_level=r.required_level, requirement_type=r.requirement_type.value,
                person_proficiency=(person_levels[str(r.skill_id)].proficiency_level if str(r.skill_id) in person_levels else None),
            )
            for r in skill_requirement_rows
        ]
        personal_gaps = compute_skill_gaps(skill_gap_inputs)
        for gap_result in personal_gaps:
            session.add(MnpPersonalGap(
                career_match_id=career_match.id, gap_type="skill", reference_id=uuid.UUID(gap_result.reference_key),
                reference_label=gap_result.reference_label, classification=gap_result.classification,
                action=gap_result.action, priority_internal=gap_result.priority_internal,
            ))

        if feasibility.status != "blocked":
            matched_labels = [
                r.skill.canonical_name_uk for r in skill_requirement_rows
                if str(r.skill_id) in person_levels
            ]
            route_steps = build_route_steps(
                career_label=career.canonical_name_uk, matched_skill_labels=matched_labels, gaps=personal_gaps,
            )
            route = MnpCareerRoute(
                career_match_id=career_match.id, route_type=RouteType(scenario_for_distance(transition_distance)),
                status="proposed",
            )
            session.add(route)
            await session.flush()
            for step in route_steps:
                session.add(MnpRouteStep(
                    route_id=route.id, order=step.order, step_type=_STEP_TYPE_MAP[step.step_type], title=step.title,
                    description=step.description,
                    target_skill_id=uuid.UUID(step.target_skill_key) if step.target_skill_key else None,
                ))

        scored_entries.append((career_match, overall_score, feasibility.status))

    ranked = sorted(
        (e for e in scored_entries if e[2] != "blocked"), key=lambda e: e[1], reverse=True,
    )
    for rank, (career_match, _, _) in enumerate(ranked, start=1):
        career_match.rank_overall = rank

    blocked = [e for e in scored_entries if e[2] == "blocked"]
    for career_match, _, _ in blocked:
        career_match.rank_overall = 0

    for rank, (career_match, _score, _status) in enumerate(ranked, start=1):
        skill_component_confidence = career_match.confidence_internal
        if rank <= 3 and skill_component_confidence in (ComponentBand.HIGH, ComponentBand.MEDIUM):
            career_match.is_featured = True

    await session.flush()
    return match_run
