"""Career-side vector normalization and persistence, Matching V1 M3
(hardened in M4.5 with official-numeric normalization functions, purely
additive -- nothing below this docstring that existed in M3 was changed).

`holland_code_to_riasec_vector` was M3's ONE transformation -- an explicit,
documented, deterministic MNP convention for converting a real O*NET/
Holland top-letter code into a full 6-dimensional profile, not an
O*NET-native numeric scale. **Retained unchanged as
`LEGACY_ENGINEERING_FALLBACK`** (Founder Review M4.5 §1) -- still used by
`app/services/career_kb/seed.py`'s original M3 profile version, never
edited, never silently mixed with the M4.5 numeric functions below.

M4.5 adds four new, independent normalization functions for the OFFICIAL
O*NET 30.3 numeric scales actually found in the raw database release
(`oi_to_normalized`, `wi_to_normalized`, `cx_to_normalized`,
`ct_to_normalized`) -- each a plain linear rescale from that scale's
*official* min/max (`onet_30_3_numeric_fixture.py::SCALE_RANGES`, taken
verbatim from O*NET's own `Scales Reference.txt`, never inferred) into
the internal `[0,1]` range, exactly mirroring the same rescale convention
`MNP_GOLDEN_TEST_V0.1.md` already uses for user-side Likert scores.

`add_career_matching_component` is the ONE gate through which every
`CareerMatchingComponent` is created -- it looks up the scale's
`mapping_status`/`matching_usage` from the EXISTING `AssessmentScale` rows
(M1's seeded question bank, the single source of truth for MNP<->O*NET
compatibility) and refuses outright (`MatchDisabledScaleError`) to create
a component for any scale whose `matching_usage` is not `MATCH_ENABLED`.
This is the literal enforcement of Founder Review's hard invariant
(§8/§9): PROFILE_ONLY is never a career-side matching vector, no
exceptions, no per-call override. Unchanged in M4.5.
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


# ---------------------------------------------------------------------------
# M4.5: official O*NET 30.3 numeric-scale normalization (CURRENT_OFFICIAL
# quality tier). Every range below is the OFFICIAL scale definition from
# O*NET 30.3's own "Scales Reference.txt" -- never inferred from the data
# itself. Each function is a plain linear rescale to internal [0,1],
# exactly the same rescale shape used everywhere else in Matching V1 for a
# bounded source scale (Golden Test doc §6/§8).

OI_TRANSFORMATION_VERSION = "onet_oi_numeric_v0.1"
WI_TRANSFORMATION_VERSION = "onet_wi_numeric_v0.1"
CX_TRANSFORMATION_VERSION = "onet_cx_numeric_v0.1"
CT_TRANSFORMATION_VERSION = "onet_ct_numeric_v0.1"


def oi_to_normalized(raw: float) -> float:
    """O*NET Occupational Interests (`OI`) scale, official range 1-7."""

    return (raw - 1.0) / 6.0


def wi_to_normalized(raw: float) -> float:
    """O*NET Work Styles Impact (`WI`) scale, official range -3 to +3 --
    signed (negative = detrimental, positive = beneficial to performance
    in this occupation). Rescaled linearly to [0,1]; 0 (neutral/
    irrelevant) maps to 0.5, not to 0 -- a neutral/irrelevant trait is not
    the same as a strongly detrimental one, and this rescale preserves
    that distinction."""

    return (raw + 3.0) / 6.0


def cx_to_normalized(raw: float) -> float:
    """O*NET Context (`CX`) scale, official range 1-5 -- the scale used by
    most Work Context elements."""

    return (raw - 1.0) / 4.0


def ct_to_normalized(raw: float) -> float:
    """O*NET Context (`CT`) scale, official range 1-3 -- confirmed
    empirically to be the scale used specifically by the "Work Schedules"
    Work Context element in O*NET 30.3 (a DIFFERENT scale than `CX`;
    never assumed to be 1-5)."""

    return (raw - 1.0) / 2.0


# M4.6 (DATA-002): O*NET Work Values "Extent" (`EX`) scale. Added for the
# production import pass -- Work Values data is sourced from O*NET **30.2**
# (the last release that still shipped `Work Values.txt`; removed from
# 30.3 onward), only for the 3 DIRECT-mappable MNP keys. Official range
# from O*NET 30.2's own `Scales Reference.txt`, verbatim (never inferred).
EX_TRANSFORMATION_VERSION = "legacy_onet_work_values_30.2_v0.1"


def ex_to_normalized(raw: float) -> float:
    """O*NET Work Values Extent (`EX`) scale, official range 1-7 -- the
    importance-of-outcome rating O*NET's Theory-of-Work-Adjustment-derived
    Work Values model uses. Plain linear rescale to internal [0,1], same
    convention as every other bounded source scale in Matching V1."""

    return (raw - 1.0) / 6.0


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
