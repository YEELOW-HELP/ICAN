"""Channel-independent explainability read contract, Matching V1 M4
(Founder Review §20): every pairwise result must be able to answer
deterministically which dimensions were compared and why a status is
what it is. No LLM explanation -- this is a structured trace, not prose.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_matching import MatchFamilyResult, MatchFeasibilityResult, MatchingResult
from app.services.exceptions import MatchingResultNotFoundError


@dataclass(frozen=True)
class FamilyExplanation:
    scale_family: str
    status: str
    raw_score: float | None
    band: str | None
    comparable_scale_keys: list[str]
    user_component_count: int
    career_component_count: int
    comparable_component_count: int
    coverage_ratio: float
    provisional: bool
    user_stdev: float | None
    career_stdev: float | None
    differentiation_threshold: float


@dataclass(frozen=True)
class FeasibilityExplanation:
    status: str
    raw_score: float | None
    band: str | None
    hard_barriers: list[str]
    soft_barriers: list[str]
    information_gaps: list[str]
    skills_to_verify: list[dict]


@dataclass(frozen=True)
class MatchingResultExplanation:
    matching_result_id: uuid.UUID
    profile_id: uuid.UUID
    career_id: uuid.UUID
    eligible: bool
    interests: FamilyExplanation
    work_styles: FamilyExplanation
    work_values: FamilyExplanation
    feasibility: FeasibilityExplanation
    versions: dict[str, str]


def _family_view(row: MatchFamilyResult) -> FamilyExplanation:
    return FamilyExplanation(
        scale_family=row.scale_family.value,
        status=row.status.value,
        raw_score=row.raw_score,
        band=row.band.value if row.band else None,
        comparable_scale_keys=list(row.comparable_scale_keys),
        user_component_count=row.user_component_count,
        career_component_count=row.career_component_count,
        comparable_component_count=row.comparable_component_count,
        coverage_ratio=row.coverage_ratio,
        provisional=row.provisional,
        user_stdev=row.user_stdev,
        career_stdev=row.career_stdev,
        differentiation_threshold=row.differentiation_threshold,
    )


async def explain_matching_result(session: AsyncSession, matching_result_id: uuid.UUID) -> MatchingResultExplanation:
    matching_result = await session.get(MatchingResult, matching_result_id)
    if matching_result is None:
        raise MatchingResultNotFoundError(f"no MatchingResult {matching_result_id}")

    family_rows = (
        (await session.execute(select(MatchFamilyResult).where(MatchFamilyResult.matching_result_id == matching_result_id)))
        .scalars()
        .all()
    )
    by_family = {row.scale_family.value: row for row in family_rows}

    feasibility_row = (
        await session.execute(
            select(MatchFeasibilityResult).where(MatchFeasibilityResult.matching_result_id == matching_result_id)
        )
    ).scalar_one()

    return MatchingResultExplanation(
        matching_result_id=matching_result_id,
        profile_id=matching_result.profile_id,
        career_id=matching_result.career_id,
        eligible=matching_result.eligible,
        interests=_family_view(by_family["riasec"]),
        work_styles=_family_view(by_family["work_style"]),
        work_values=_family_view(by_family["work_values"]),
        feasibility=FeasibilityExplanation(
            status=feasibility_row.status.value,
            raw_score=feasibility_row.raw_score,
            band=feasibility_row.band.value if feasibility_row.band else None,
            hard_barriers=list(feasibility_row.hard_barriers),
            soft_barriers=list(feasibility_row.soft_barriers),
            information_gaps=list(feasibility_row.information_gaps),
            skills_to_verify=list(feasibility_row.skills_to_verify),
        ),
        versions={
            "assessment_version": matching_result.assessment_version,
            "profile_engine_version": matching_result.profile_engine_version,
            "matching_methodology_version": matching_result.matching_methodology_version,
            "career_vector_version": matching_result.career_vector_version,
            "career_source_version": matching_result.career_source_version,
            "matching_engine_version": matching_result.matching_engine_version,
            "metric_version": matching_result.metric_version,
            "config_version": matching_result.config_version,
        },
    )
