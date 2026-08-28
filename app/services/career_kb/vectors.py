"""Career-side vector normalization and persistence, Matching V1 M3.

`holland_code_to_riasec_vector` is the ONE new transformation this slice
introduces -- it is an explicit, documented, deterministic MNP convention
for converting a real O*NET/Holland top-letter code into a full
6-dimensional profile, not an O*NET-native numeric scale and not an
invented psychometric formula: O*NET's own RIASEC *letters* are the real
source value; the graduated numeric spread is this function's own
disclosed rule (mirrors how `MNP_GOLDEN_TEST_V0.1.md` already normalizes
raw Likert means into `[0,1]` via its own disclosed formula).

`add_career_matching_component` is the ONE gate through which every
`CareerMatchingComponent` is created -- it looks up the scale's
`mapping_status`/`matching_usage` from the EXISTING `AssessmentScale` rows
(M1's seeded question bank, the single source of truth for MNP<->O*NET
compatibility) and refuses outright (`MatchDisabledScaleError`) to create
a component for any scale whose `matching_usage` is not `MATCH_ENABLED`.
This is the literal enforcement of Founder Review's hard invariant
(§8/§9): PROFILE_ONLY is never a career-side matching vector, no
exceptions, no per-call override.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_basic_assessment import AssessmentScale, MatchingUsage, MappingStatus, ScaleFamily
from app.db.models_career_kb import CareerMatchingComponent, CareerMatchingProfile
from app.services.exceptions import MatchDisabledScaleError

RIASEC_LETTERS = ("R", "I", "A", "S", "E", "C")
_RANK_VALUES = (0.90, 0.70, 0.50)
_BASELINE_VALUE = 0.20
RIASEC_TRANSFORMATION_VERSION = "onet_holland_to_riasec_v0.1"


def holland_code_to_riasec_vector(holland_code: str) -> dict[str, float]:
    """Deterministic, pure function: same `holland_code` string always
    produces the same 6-key dict. Letters appearing in the code (in
    order, first = strongest) get `_RANK_VALUES[rank]`; the remaining
    letters get `_BASELINE_VALUE`. A code longer than 3 letters only uses
    its first 3 (O*NET/Holland codes are conventionally 2-3 letters)."""

    letters = [c for c in holland_code.upper() if c in RIASEC_LETTERS][:3]
    vector = {letter: _BASELINE_VALUE for letter in RIASEC_LETTERS}
    for rank, letter in enumerate(letters):
        vector[letter] = _RANK_VALUES[rank]
    return vector


async def create_career_matching_profile(
    session: AsyncSession,
    *,
    career_id: uuid.UUID,
    career_vector_version: str,
    matching_methodology_version: str,
    source_version: str,
    mapping_version: str,
    localization_version: str = "mnp_localization_v0.1",
    provisional: bool = True,
) -> CareerMatchingProfile:
    """Idempotent per (career_id, career_vector_version, mapping_version,
    source_version) -- a second call with identical version stamps returns
    the existing row untouched. A genuinely new version combination
    supersedes (never edits) the prior `is_current` profile for this
    career."""

    existing = await session.execute(
        select(CareerMatchingProfile).where(
            CareerMatchingProfile.career_id == career_id,
            CareerMatchingProfile.career_vector_version == career_vector_version,
            CareerMatchingProfile.mapping_version == mapping_version,
            CareerMatchingProfile.source_version == source_version,
        )
    )
    found = existing.scalar_one_or_none()
    if found is not None:
        return found

    next_version = (
        await session.execute(
            select(func.coalesce(func.max(CareerMatchingProfile.profile_version), 0)).where(
                CareerMatchingProfile.career_id == career_id
            )
        )
    ).scalar_one() + 1

    prior_current = await session.execute(
        select(CareerMatchingProfile).where(
            CareerMatchingProfile.career_id == career_id, CareerMatchingProfile.is_current.is_(True)
        )
    )
    prior = prior_current.scalar_one_or_none()

    profile = CareerMatchingProfile(
        career_id=career_id,
        profile_version=next_version,
        career_vector_version=career_vector_version,
        matching_methodology_version=matching_methodology_version,
        source_version=source_version,
        mapping_version=mapping_version,
        localization_version=localization_version,
        provisional=provisional,
        is_current=True,
        supersedes_id=prior.id if prior is not None else None,
    )
    if prior is not None:
        prior.is_current = False

    session.add(profile)
    await session.flush()
    return profile


async def add_career_matching_component(
    session: AsyncSession,
    *,
    profile: CareerMatchingProfile,
    scale_family: ScaleFamily,
    scale_key: str,
    normalized_value: float | None,
    transformation_version: str,
    source_system: str | None = None,
    source_element_id: str | None = None,
    source_element_name: str | None = None,
    source_raw_value: str | None = None,
) -> CareerMatchingComponent:
    scale_result = await session.execute(
        select(AssessmentScale).where(
            AssessmentScale.scale_family == scale_family, AssessmentScale.scale_key == scale_key
        )
    )
    scale = scale_result.scalar_one_or_none()
    if scale is None:
        raise ValueError(
            f"no AssessmentScale found for {scale_family.value}/{scale_key} -- "
            "seed_alpha_long_form() (M1) must run before career vectors can be built"
        )
    if scale.matching_usage != MatchingUsage.MATCH_ENABLED:
        raise MatchDisabledScaleError(
            f"{scale_family.value}/{scale_key} is {scale.matching_usage.value} "
            "(mapping_status={0}) -- a career-side component may never be created for a PROFILE_ONLY scale".format(
                scale.mapping_status.value
            )
        )

    existing = await session.execute(
        select(CareerMatchingComponent).where(
            CareerMatchingComponent.profile_id == profile.id,
            CareerMatchingComponent.scale_family == scale_family,
            CareerMatchingComponent.scale_key == scale_key,
        )
    )
    found = existing.scalar_one_or_none()
    if found is not None:
        return found

    component = CareerMatchingComponent(
        profile_id=profile.id,
        scale_family=scale_family,
        scale_key=scale_key,
        normalized_value=normalized_value,
        mapping_status=scale.mapping_status,
        matching_usage=scale.matching_usage,
        provisional=(scale.mapping_status != MappingStatus.DIRECT),
        source_system=source_system,
        source_element_id=source_element_id,
        source_element_name=source_element_name,
        source_raw_value=source_raw_value,
        transformation_version=transformation_version,
    )
    session.add(component)
    await session.flush()
    return component
