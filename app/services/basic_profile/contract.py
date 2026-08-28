"""Channel-independent BASIC profile read contract (Matching V1 M2).

`BasicProfileResult` is the shape M5 (Telegram + Website, same engine) and
CRM will eventually read -- pure data, no formatting, no locale strings, no
HTML/Markdown. A future channel adapter decides how to render a
`normalized_value` or an `option_key`; this module never does.

Profile score != Career Fit (Founder Review §13): nothing here carries a
band/label beyond what the canonical methodology already defines
(Coverage's Full/Partial/Insufficient, and the per-vector differentiation
state) -- no HIGH/MEDIUM/LOW is invented for an individual scale.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_basic_assessment import ScaleFamily
from app.db.models_basic_profile import DeterministicProfile, ProfileStructuredContext, ProfileVectorDifferentiation
from app.services.basic_profile.queries import get_profile_scale_results

STRUCTURED_FAMILIES = (ScaleFamily.GOALS, ScaleFamily.CONSTRAINTS, ScaleFamily.EXPERIENCE)


@dataclass(frozen=True)
class ScaleResultView:
    scale_key: str
    raw_mean: float | None
    normalized_value: float | None
    sufficiently_answered: bool
    mapping_status: str
    matching_usage: str
    provisional: bool


@dataclass(frozen=True)
class VectorView:
    scales: list[ScaleResultView]
    differentiation_state: str
    stdev: float | None


@dataclass(frozen=True)
class StructuredContextItemView:
    scale_key: str
    response_type: str
    numeric_value: int | None
    boolean_value: bool | None
    selected_option_keys: list[str] | None


@dataclass(frozen=True)
class ProvenanceView:
    user_id: uuid.UUID
    attempt_id: uuid.UUID
    assessment_code: str
    assessment_version: str
    methodology_version: str
    profile_engine_version: str
    calculated_at: datetime
    is_current: bool


@dataclass(frozen=True)
class BasicProfileResult:
    interests: VectorView
    work_styles: VectorView
    work_values: VectorView
    work_environment: VectorView
    goals: list[StructuredContextItemView]
    experience: list[StructuredContextItemView]
    constraints: list[StructuredContextItemView]
    coverage: float
    coverage_band: str
    context_completeness: float
    differentiation_state: str  # worst-case across the 4 vector families
    interest_ordering: list[str]
    provenance: ProvenanceView


async def build_basic_profile_result(session: AsyncSession, profile: DeterministicProfile) -> BasicProfileResult:
    def _vector(family: ScaleFamily, results: list, diff_by_family: dict) -> VectorView:
        scales = [
            ScaleResultView(
                scale_key=r.scale_key,
                raw_mean=r.raw_mean,
                normalized_value=r.normalized_value,
                sufficiently_answered=r.sufficiently_answered,
                mapping_status=r.mapping_status.value,
                matching_usage=r.matching_usage.value,
                provisional=r.provisional,
            )
            for r in results
            if r.scale_family == family
        ]
        diff = diff_by_family.get(family)
        return VectorView(
            scales=scales,
            differentiation_state=diff.state.value if diff else "insufficient_data",
            stdev=diff.stdev if diff else None,
        )

    scale_results = await get_profile_scale_results(session, profile)

    diff_rows = (
        (
            await session.execute(
                select(ProfileVectorDifferentiation).where(ProfileVectorDifferentiation.profile_id == profile.id)
            )
        )
        .scalars()
        .all()
    )
    diff_by_family = {d.scale_family: d for d in diff_rows}

    context_rows = (
        (
            await session.execute(
                select(ProfileStructuredContext).where(ProfileStructuredContext.profile_id == profile.id)
            )
        )
        .scalars()
        .all()
    )
    structured_by_family: dict[ScaleFamily, list[StructuredContextItemView]] = {family: [] for family in STRUCTURED_FAMILIES}
    for row in context_rows:
        structured_by_family[row.scale_family].append(
            StructuredContextItemView(
                scale_key=row.scale_key,
                response_type=row.response_type.value,
                numeric_value=row.numeric_value,
                boolean_value=row.boolean_value,
                selected_option_keys=row.selected_option_keys,
            )
        )

    return BasicProfileResult(
        interests=_vector(ScaleFamily.RIASEC, scale_results, diff_by_family),
        work_styles=_vector(ScaleFamily.WORK_STYLE, scale_results, diff_by_family),
        work_values=_vector(ScaleFamily.WORK_VALUES, scale_results, diff_by_family),
        work_environment=_vector(ScaleFamily.WORK_ENVIRONMENT, scale_results, diff_by_family),
        goals=structured_by_family[ScaleFamily.GOALS],
        experience=structured_by_family[ScaleFamily.EXPERIENCE],
        constraints=structured_by_family[ScaleFamily.CONSTRAINTS],
        coverage=profile.coverage,
        coverage_band=profile.coverage_band.value,
        context_completeness=profile.context_completeness,
        differentiation_state=profile.differentiation_state.value,
        interest_ordering=profile.interest_ordering or [],
        provenance=ProvenanceView(
            user_id=profile.user_id,
            attempt_id=profile.attempt_id,
            assessment_code=profile.assessment_code,
            assessment_version=profile.assessment_version,
            methodology_version=profile.methodology_version,
            profile_engine_version=profile.profile_engine_version,
            calculated_at=profile.calculated_at,
            is_current=profile.is_current,
        ),
    )
