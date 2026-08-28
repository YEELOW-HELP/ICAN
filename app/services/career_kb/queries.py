"""Channel-independent career matching profile read contract, Matching V1
M3. No UI formatting -- pure data, mirroring `app.services.basic_profile.
contract`'s shape so M4's matching engine can read both sides uniformly.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_basic_assessment import ScaleFamily
from app.db.models_career_kb import CareerExternalMapping, CareerMatchingComponent, CareerMatchingProfile
from app.services.exceptions import NoCurrentCareerMatchingProfileError


@dataclass(frozen=True)
class ExternalMappingView:
    source_system: str
    external_code: str | None
    external_label: str | None
    mapping_status: str
    confidence: float | None


@dataclass(frozen=True)
class MatchingComponentView:
    scale_key: str
    normalized_value: float | None  # None == unavailable, never a fabricated 0
    mapping_status: str
    provisional: bool
    source_system: str | None
    source_element_id: str | None


@dataclass(frozen=True)
class CareerVectorView:
    components: list[MatchingComponentView]

    def coverage(self, expected_scale_keys: list[str]) -> float:
        """Career-side coverage for this family, per Founder Review §22:
        (# expected MATCH_ENABLED scales with a real, non-null value) /
        (# expected MATCH_ENABLED scales) -- NOT the same concept as user
        Assessment Coverage (M1/M2). Returns 0.0 if `expected_scale_keys`
        is empty."""

        if not expected_scale_keys:
            return 0.0
        available = {c.scale_key for c in self.components if c.normalized_value is not None}
        return len(available & set(expected_scale_keys)) / len(expected_scale_keys)


@dataclass(frozen=True)
class CareerMatchingProfileView:
    career_id: uuid.UUID
    career_code: str
    profile_version: int
    career_vector_version: str
    matching_methodology_version: str
    source_version: str
    mapping_version: str
    localization_version: str
    provisional: bool
    is_current: bool
    external_mappings: list[ExternalMappingView]
    interests: CareerVectorView  # RIASEC
    work_styles: CareerVectorView
    work_values: CareerVectorView
    work_environment: CareerVectorView


async def get_career_matching_profile(
    session: AsyncSession, career_id: uuid.UUID, *, version: int | None = None
) -> CareerMatchingProfileView:
    """`version=None` returns the current profile; an explicit
    `profile_version` returns that specific historical (immutable) one."""

    if version is None:
        result = await session.execute(
            select(CareerMatchingProfile).where(
                CareerMatchingProfile.career_id == career_id, CareerMatchingProfile.is_current.is_(True)
            )
        )
    else:
        result = await session.execute(
            select(CareerMatchingProfile).where(
                CareerMatchingProfile.career_id == career_id, CareerMatchingProfile.profile_version == version
            )
        )
    profile = result.scalar_one_or_none()
    if profile is None:
        raise NoCurrentCareerMatchingProfileError(f"no CareerMatchingProfile for career {career_id} (version={version})")

    from app.db.models_knowledge import Career  # local import: models_knowledge is the Stage 3A module

    career = await session.get(Career, career_id)

    mapping_rows = (
        (await session.execute(select(CareerExternalMapping).where(CareerExternalMapping.career_id == career_id)))
        .scalars()
        .all()
    )
    external_mappings = [
        ExternalMappingView(
            source_system=m.source_system.value,
            external_code=m.external_code,
            external_label=m.external_label,
            mapping_status=m.mapping_status.value,
            confidence=m.confidence,
        )
        for m in mapping_rows
    ]

    component_rows = (
        (
            await session.execute(
                select(CareerMatchingComponent).where(CareerMatchingComponent.profile_id == profile.id)
            )
        )
        .scalars()
        .all()
    )

    def _vector(family: ScaleFamily) -> CareerVectorView:
        return CareerVectorView(
            components=[
                MatchingComponentView(
                    scale_key=c.scale_key,
                    normalized_value=c.normalized_value,
                    mapping_status=c.mapping_status.value,
                    provisional=c.provisional,
                    source_system=c.source_system,
                    source_element_id=c.source_element_id,
                )
                for c in component_rows
                if c.scale_family == family
            ]
        )

    return CareerMatchingProfileView(
        career_id=career_id,
        career_code=career.code,
        profile_version=profile.profile_version,
        career_vector_version=profile.career_vector_version,
        matching_methodology_version=profile.matching_methodology_version,
        source_version=profile.source_version,
        mapping_version=profile.mapping_version,
        localization_version=profile.localization_version,
        provisional=profile.provisional,
        is_current=profile.is_current,
        external_mappings=external_mappings,
        interests=_vector(ScaleFamily.RIASEC),
        work_styles=_vector(ScaleFamily.WORK_STYLE),
        work_values=_vector(ScaleFamily.WORK_VALUES),
        work_environment=_vector(ScaleFamily.WORK_ENVIRONMENT),
    )
