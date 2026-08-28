"""DB orchestration + persistence for the deterministic matching engine
(Matching V1 M4). Reads M2's `DeterministicProfile`/`ProfileScaleResult`/
`ProfileStructuredContext`, M3's `CareerMatchingProfile`/
`CareerMatchingComponent`, and Stage 3A's `CareerRequirement`/
`CareerSkill`/`CareerWorkContext`/`CareerFact` -- all read-only, none
modified. Converts them into `app.services.matching.pure`'s plain
dataclasses, calls the pure functions, and persists the result.

Separation of concerns (Founder Review §17): every actual formula lives
in `pure.py`, which never imports SQLAlchemy. This module's only job is
"fetch, convert, call, persist" -- it is not unit-tested for arithmetic
correctness, only for correct wiring.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_basic_assessment import MatchingUsage, ScaleFamily
from app.db.models_basic_profile import DeterministicProfile, ProfileScaleResult, ProfileStructuredContext
from app.db.models_career_kb import CareerMatchingComponent, CareerMatchingProfile
from app.db.models_knowledge import Career, CareerFact, CareerRequirement, CareerSkill, CareerWorkContext
from app.db.models_matching import (
    FitBand,
    FitStatus,
    MatchFamilyResult,
    MatchFeasibilityResult,
    MatchingResult,
)
from app.services.matching.config import DEFAULT_CONFIG, MatchingConfig
from app.services.matching.pure import (
    CareerRequirementInput,
    CareerSkillInput,
    ConstraintAnswer,
    FeasibilityResult,
    FitFamilyResult,
    compute_feasibility,
    guarded_cosine_fit,
)

FIT_FAMILIES = (ScaleFamily.RIASEC, ScaleFamily.WORK_STYLE, ScaleFamily.WORK_VALUES)


async def _load_user_family_values(
    session: AsyncSession, profile_id: uuid.UUID
) -> dict[ScaleFamily, dict[str, float]]:
    """Only MATCH_ENABLED, sufficiently-answered, non-null scale results
    count as a user value for matching -- PROFILE_ONLY scales are
    excluded outright (Founder Review §5), never merely deprioritized."""

    result = await session.execute(select(ProfileScaleResult).where(ProfileScaleResult.profile_id == profile_id))
    rows = result.scalars().all()
    values: dict[ScaleFamily, dict[str, float]] = {family: {} for family in FIT_FAMILIES}
    for row in rows:
        if row.scale_family not in values:
            continue
        if row.matching_usage != MatchingUsage.MATCH_ENABLED:
            continue
        if not row.sufficiently_answered or row.normalized_value is None:
            continue
        values[row.scale_family][row.scale_key] = row.normalized_value
    return values


async def _load_career_family_values(
    session: AsyncSession, career_matching_profile_id: uuid.UUID
) -> tuple[dict[ScaleFamily, dict[str, float]], dict[ScaleFamily, bool]]:
    result = await session.execute(
        select(CareerMatchingComponent).where(CareerMatchingComponent.profile_id == career_matching_profile_id)
    )
    rows = result.scalars().all()
    values: dict[ScaleFamily, dict[str, float]] = {family: {} for family in FIT_FAMILIES}
    provisional: dict[ScaleFamily, bool] = {family: False for family in FIT_FAMILIES}
    for row in rows:
        if row.scale_family not in values or row.normalized_value is None:
            continue
        values[row.scale_family][row.scale_key] = row.normalized_value
        if row.provisional:
            provisional[row.scale_family] = True
    return values, provisional


async def _load_user_constraints(session: AsyncSession, profile_id: uuid.UUID) -> dict[str, ConstraintAnswer]:
    result = await session.execute(
        select(ProfileStructuredContext).where(
            ProfileStructuredContext.profile_id == profile_id, ProfileStructuredContext.scale_family == "constraints"
        )
    )
    rows = result.scalars().all()
    return {
        row.scale_key: ConstraintAnswer(
            scale_key=row.scale_key,
            boolean_value=row.boolean_value,
            selected_option_keys=tuple(row.selected_option_keys) if row.selected_option_keys else None,
        )
        for row in rows
    }


async def _load_career_feasibility_inputs(
    session: AsyncSession, career_id: uuid.UUID
) -> tuple[list[CareerRequirementInput], list[CareerSkillInput], str | None, int | None]:
    requirements_result = await session.execute(
        select(CareerRequirement).where(CareerRequirement.career_id == career_id)
    )
    requirements = [
        CareerRequirementInput(category=r.category.value, certainty=r.certainty.value, description=r.description)
        for r in requirements_result.scalars().all()
    ]

    from app.db.models_profile import TaxonomyTerm  # local import: models_profile owns TaxonomyTerm

    skills_result = await session.execute(
        select(CareerSkill, TaxonomyTerm)
        .join(TaxonomyTerm, CareerSkill.skill_term_id == TaxonomyTerm.id)
        .where(CareerSkill.career_id == career_id)
    )
    skills = [
        CareerSkillInput(label=term.label_uk, requirement_type=skill.requirement_type.value)
        for skill, term in skills_result.all()
    ]

    work_context_result = await session.execute(
        select(CareerWorkContext).where(CareerWorkContext.career_id == career_id)
    )
    work_context = work_context_result.scalar_one_or_none()
    work_format_setting = work_context.setting.value if (work_context and work_context.setting) else None

    fact_result = await session.execute(
        select(CareerFact).where(CareerFact.career_id == career_id, CareerFact.fact_type == "onet_job_zone")
    )
    fact = fact_result.scalars().first()
    job_zone = int(fact.value_text) if fact is not None else None

    return requirements, skills, work_format_setting, job_zone


def _fit_status_enum(status: str) -> FitStatus:
    return FitStatus(status)


def _band_enum(band: str | None) -> FitBand | None:
    return FitBand(band) if band is not None else None


async def calculate_pair_match(
    session: AsyncSession,
    *,
    profile: DeterministicProfile,
    career_matching_profile: CareerMatchingProfile,
    config: MatchingConfig = DEFAULT_CONFIG,
) -> MatchingResult:
    """Idempotent per (profile_id, career_matching_profile_id,
    matching_engine_version, config_version) -- a re-run with identical
    inputs and the same engine/config version returns the existing,
    immutable row untouched."""

    existing = await session.execute(
        select(MatchingResult).where(
            MatchingResult.profile_id == profile.id,
            MatchingResult.career_matching_profile_id == career_matching_profile.id,
            MatchingResult.matching_engine_version == config.matching_engine_version,
            MatchingResult.config_version == config.config_version,
        )
    )
    found = existing.scalar_one_or_none()
    if found is not None:
        return found

    user_values = await _load_user_family_values(session, profile.id)
    career_values, career_provisional = await _load_career_family_values(session, career_matching_profile.id)

    fit_results: dict[ScaleFamily, FitFamilyResult] = {}
    for family in FIT_FAMILIES:
        fit_results[family] = guarded_cosine_fit(
            user_values[family],
            career_values[family],
            config=config,
            provisional=career_provisional[family] or career_matching_profile.provisional,
        )

    constraints = await _load_user_constraints(session, profile.id)
    requirements, skills, work_format_setting, job_zone = await _load_career_feasibility_inputs(
        session, career_matching_profile.career_id
    )
    feasibility: FeasibilityResult = compute_feasibility(
        constraints=constraints,
        career_requirements=requirements,
        career_skills=skills,
        career_work_format_setting=work_format_setting,
        job_zone=job_zone,
        config=config,
    )

    matching_result = MatchingResult(
        profile_id=profile.id,
        career_id=career_matching_profile.career_id,
        career_matching_profile_id=career_matching_profile.id,
        assessment_version=profile.assessment_version,
        profile_engine_version=profile.profile_engine_version,
        matching_methodology_version=profile.methodology_version,
        career_vector_version=career_matching_profile.career_vector_version,
        career_source_version=career_matching_profile.source_version,
        matching_engine_version=config.matching_engine_version,
        metric_version=config.metric_version,
        config_version=config.config_version,
        eligible=(feasibility.status != "blocked"),
    )
    session.add(matching_result)
    await session.flush()

    for family, fit in fit_results.items():
        session.add(
            MatchFamilyResult(
                matching_result_id=matching_result.id,
                scale_family=family,
                status=_fit_status_enum(fit.status),
                raw_score=fit.raw_score,
                band=_band_enum(fit.band),
                user_component_count=fit.user_component_count,
                career_component_count=fit.career_component_count,
                comparable_component_count=fit.comparable_component_count,
                comparable_scale_keys=list(fit.comparable_scale_keys),
                coverage_ratio=fit.coverage_ratio,
                provisional=fit.provisional,
                user_stdev=fit.user_stdev,
                career_stdev=fit.career_stdev,
                differentiation_threshold=fit.differentiation_threshold,
            )
        )

    session.add(
        MatchFeasibilityResult(
            matching_result_id=matching_result.id,
            status=feasibility.status,
            raw_score=feasibility.raw_score,
            band=_band_enum(feasibility.band),
            hard_barriers=list(feasibility.hard_barriers),
            soft_barriers=list(feasibility.soft_barriers),
            information_gaps=list(feasibility.information_gaps),
            skills_to_verify=[{"label": s.label, "status": s.status} for s in feasibility.skills_to_verify],
        )
    )

    await session.flush()
    return matching_result


async def match_profile_to_careers(
    session: AsyncSession,
    *,
    profile_id: uuid.UUID,
    career_ids: list[uuid.UUID] | None = None,
    config: MatchingConfig = DEFAULT_CONFIG,
) -> list[MatchingResult]:
    """Channel-independent entry point: match one `DeterministicProfile`
    against either the given `career_ids` or (if `None`) every career
    that currently has a `CareerMatchingProfile`. Returns one
    `MatchingResult` per career, in no particular order -- ranking is a
    separate step (`app.services.matching.ranking`)."""

    profile = await session.get(DeterministicProfile, profile_id)
    if profile is None:
        raise ValueError(f"no DeterministicProfile {profile_id}")

    query = select(CareerMatchingProfile).where(CareerMatchingProfile.is_current.is_(True))
    if career_ids is not None:
        query = query.where(CareerMatchingProfile.career_id.in_(career_ids))
    career_profiles = (await session.execute(query)).scalars().all()

    results = []
    for career_profile in career_profiles:
        result = await calculate_pair_match(
            session, profile=profile, career_matching_profile=career_profile, config=config
        )
        results.append(result)
    return results
