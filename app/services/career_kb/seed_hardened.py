"""Matching V1 M4.5 -- hardens the Alpha career vectors with official
O*NET 30.3 NUMERIC data (Founder Review "M4.5 GO", 2026-08-28).

Does NOT modify `seed.py` (M3, frozen) -- calls it first (idempotent) to
ensure the base Alpha catalog + crosswalk + LEGACY_ENGINEERING_FALLBACK
profile exist, then creates a SEPARATE, NEW `CareerMatchingProfile`
version per career via the SAME, UNCHANGED `create_career_matching_profile`/
`add_career_matching_component` functions M3 already used -- this is the
existing versioning architecture working exactly as designed (a changed
source/mapping version supersedes the prior `is_current` profile, never
edits it). `app/services/matching/engine.py` (M4, also unchanged) reads
whichever `CareerMatchingProfile` is `is_current` for a career, so
re-running the unchanged M4 matching engine after this seed automatically
uses the new, hardened numeric data.

Values Fit remains untouched -- no Work Values component is created here
(Founder Review §7: no current O*NET source exists for it).
`structure_preference` (Work Style) remains untouched -- no current O*NET
Work Context element corresponds to it (see
`onet_30_3_numeric_fixture.py`'s docstring for the disclosed finding).
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_basic_assessment import ScaleFamily
from app.db.models_career_kb import CareerMatchingProfile
from app.services.career_kb.onet_30_3_numeric_fixture import (
    CAREER_VECTOR_VERSION_V2,
    NUMERIC_MAPPING_VERSION,
    ONET_NUMERIC_SOURCE_VERSION,
    RIASEC_ELEMENT_IDS,
    WORK_ENVIRONMENT_ELEMENT_IDS,
    WORK_STYLE_ELEMENT_IDS,
    load_numeric_source,
)
from app.services.career_kb.seed import (
    ALPHA_CAREER_CODES,
    MATCHING_METHODOLOGY_VERSION,
    seed_alpha_career_matching_profiles,
)
from app.services.career_kb.vectors import (
    CT_TRANSFORMATION_VERSION,
    CX_TRANSFORMATION_VERSION,
    OI_TRANSFORMATION_VERSION,
    WI_TRANSFORMATION_VERSION,
    add_career_matching_component,
    create_career_matching_profile,
    ct_to_normalized,
    cx_to_normalized,
    oi_to_normalized,
    wi_to_normalized,
)
from app.services.knowledge.retrieval import get_career_by_code

_RIASEC_ELEMENT_NAME = {
    "R": "Realistic", "I": "Investigative", "A": "Artistic", "S": "Social", "E": "Enterprising", "C": "Conventional",
}


async def seed_alpha_career_matching_profiles_hardened(session: AsyncSession) -> list[CareerMatchingProfile]:
    """Idempotent, exactly like M3's own seed. Returns the current (now
    hardened) `CareerMatchingProfile` for each of the 24 Alpha careers."""

    await seed_alpha_career_matching_profiles(session)  # M3, unchanged -- ensures base catalog/crosswalk exist

    profiles: list[CareerMatchingProfile] = []

    for record in load_numeric_source():
        if record.mnp_career_code not in ALPHA_CAREER_CODES:
            continue

        career = await get_career_by_code(session, record.mnp_career_code)
        profile = await create_career_matching_profile(
            session,
            career_id=career.id,
            career_vector_version=CAREER_VECTOR_VERSION_V2,
            matching_methodology_version=MATCHING_METHODOLOGY_VERSION,
            source_version=ONET_NUMERIC_SOURCE_VERSION,
            mapping_version=NUMERIC_MAPPING_VERSION,
            provisional=True,  # still Alpha -- not yet reviewed/calibrated (Founder Review §21, unconditional)
        )

        # --- RIASEC (OI) ---
        if record.riasec_oi:
            for letter, raw in record.riasec_oi.items():
                await add_career_matching_component(
                    session,
                    profile=profile,
                    scale_family=ScaleFamily.RIASEC,
                    scale_key=letter,
                    normalized_value=oi_to_normalized(raw),
                    transformation_version=OI_TRANSFORMATION_VERSION,
                    source_system="onet",
                    source_element_id=RIASEC_ELEMENT_IDS[letter],
                    source_element_name=_RIASEC_ELEMENT_NAME[letter],
                    source_raw_value=str(raw),
                )
        # else: UNMAPPED career -- zero RIASEC components, exactly as M3.

        # --- Work Style (WI): DIRECT scales ---
        for scale_key in ("leadership", "initiative", "ambiguity_tolerance"):
            raw = record.work_style_wi.get(scale_key)
            if raw is None:
                continue
            element_name, element_id = WORK_STYLE_ELEMENT_IDS[scale_key]
            await add_career_matching_component(
                session,
                profile=profile,
                scale_family=ScaleFamily.WORK_STYLE,
                scale_key=scale_key,
                normalized_value=wi_to_normalized(raw),
                transformation_version=WI_TRANSFORMATION_VERSION,
                source_system="onet",
                source_element_id=element_id,
                source_element_name=element_name,
                source_raw_value=str(raw),
            )

        # --- Work Style (WI): DERIVED `collaboration` = mean(Social Orientation, Cooperation) ---
        social = record.work_style_wi.get("collaboration_social")
        cooperation = record.work_style_wi.get("collaboration_cooperation")
        if social is not None and cooperation is not None:
            composite_normalized = (wi_to_normalized(social) + wi_to_normalized(cooperation)) / 2.0
            await add_career_matching_component(
                session,
                profile=profile,
                scale_family=ScaleFamily.WORK_STYLE,
                scale_key="collaboration",
                normalized_value=composite_normalized,
                transformation_version=WI_TRANSFORMATION_VERSION,
                source_system="onet",
                source_element_id=f"{WORK_STYLE_ELEMENT_IDS['collaboration_social'][1]}+{WORK_STYLE_ELEMENT_IDS['collaboration_cooperation'][1]}",
                source_element_name="Social Orientation + Cooperation (mean)",
                source_raw_value=f"{social},{cooperation}",
            )
        # `structure_preference`: intentionally never populated -- no current
        # O*NET Work Context element corresponds to it (disclosed finding).

        # --- Work Environment (CX/CT): DIRECT scales ---
        if record.work_context:
            for scale_key in ("collaboration_context", "customer_interaction_context", "schedule_predictability"):
                entry = record.work_context.get(scale_key)
                if entry is None:
                    continue
                raw, scale_id = entry
                element_name, element_id, _ = WORK_ENVIRONMENT_ELEMENT_IDS[scale_key]
                normalized = ct_to_normalized(raw) if scale_id == "CT" else cx_to_normalized(raw)
                transformation = CT_TRANSFORMATION_VERSION if scale_id == "CT" else CX_TRANSFORMATION_VERSION
                await add_career_matching_component(
                    session,
                    profile=profile,
                    scale_family=ScaleFamily.WORK_ENVIRONMENT,
                    scale_key=scale_key,
                    normalized_value=normalized,
                    transformation_version=transformation,
                    source_system="onet",
                    source_element_id=element_id,
                    source_element_name=element_name,
                    source_raw_value=str(raw),
                )

            # `setting` (DERIVED, conservative single-element subset of the
            # M0-approved composite): "Indoors, Environmentally Controlled" alone.
            setting_entry = record.work_context.get("setting")
            if setting_entry is not None:
                raw, _scale_id = setting_entry
                element_name, element_id, _ = WORK_ENVIRONMENT_ELEMENT_IDS["setting"]
                await add_career_matching_component(
                    session,
                    profile=profile,
                    scale_family=ScaleFamily.WORK_ENVIRONMENT,
                    scale_key="setting",
                    normalized_value=cx_to_normalized(raw),
                    transformation_version=CX_TRANSFORMATION_VERSION,
                    source_system="onet",
                    source_element_id=element_id,
                    source_element_name=element_name,
                    source_raw_value=str(raw),
                )

            # `physical_environment` (DERIVED) = mean(Standing, Walking/Running)
            standing_entry = record.work_context.get("physical_environment_standing")
            walking_entry = record.work_context.get("physical_environment_walking")
            if standing_entry is not None and walking_entry is not None:
                standing_raw, _ = standing_entry
                walking_raw, _ = walking_entry
                composite_normalized = (cx_to_normalized(standing_raw) + cx_to_normalized(walking_raw)) / 2.0
                await add_career_matching_component(
                    session,
                    profile=profile,
                    scale_family=ScaleFamily.WORK_ENVIRONMENT,
                    scale_key="physical_environment",
                    normalized_value=composite_normalized,
                    transformation_version=CX_TRANSFORMATION_VERSION,
                    source_system="onet",
                    source_element_id=f"{WORK_ENVIRONMENT_ELEMENT_IDS['physical_environment_standing'][1]}+{WORK_ENVIRONMENT_ELEMENT_IDS['physical_environment_walking'][1]}",
                    source_element_name="Spend Time Standing + Spend Time Walking or Running (mean)",
                    source_raw_value=f"{standing_raw},{walking_raw}",
                )
        # else: no Work Context data for this O*NET occupation (e.g.
        # 13-1082.00, 13-2051.00) -- zero Work Environment components,
        # never fabricated.

        profiles.append(profile)

    return profiles
