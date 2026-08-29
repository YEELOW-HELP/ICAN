"""Matching V1 M4.6 -- production O*NET import seed (DATA-002).

Builds a NEW `career_vector_v0.3` `CareerMatchingProfile` per mapped Alpha
career from the generated, committed `onet_source_v3.json` (full official
O*NET 31.0 numeric data + O*NET 30.2 Work Values), via the SAME, UNCHANGED
`create_career_matching_profile` / `add_career_matching_component` gates
M3/M4.5 already use. The existing versioning contract does the rest: a new
source/mapping/vector version stamp supersedes the prior `is_current`
profile, never edits it -- `career_vector_v0.1` (M3 Holland approximation)
and `career_vector_v0.2` (M4.5, hand-typed 30.3 numeric) stay immutable
and independently queryable.

What v0.3 fixes over v0.2 (see docs/engineering/27_...md for the full
coverage table):
  * Work Style now populated for EVERY mapped career (was: 1 of 24) --
    `leadership`, `initiative`, `ambiguity_tolerance` (DIRECT) + the
    `collaboration` DERIVED composite.
  * Work Values now populated (was: 0 of 24) -- the 3 DIRECT keys, from
    O*NET 30.2, flagged `legacy_onet_work_values_30.2_v0.1`.
  * Work Environment from the full O*NET 31.0 Work Context set.
  * RIASEC from real O*NET 31.0 `OI` numeric values (not the Holland
    top-code approximation).

Idempotent end-to-end. Zero-AI (no `app.ai_gateway` import anywhere in the
call graph).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_basic_assessment import ScaleFamily
from app.db.models_career_kb import CareerMatchingProfile
from app.db.models_knowledge import CareerFact, FactVerificationState, KnowledgeSource
from app.services.career_kb.onet_alpha_fixture import get_onet_source
from app.services.career_kb.onet_source_v3 import (
    CAREER_VECTOR_VERSION_V3,
    CT_TRANSFORMATION_VERSION,
    CX_TRANSFORMATION_VERSION,
    EX_TRANSFORMATION_VERSION,
    NUMERIC_MAPPING_VERSION_V3,
    OI_TRANSFORMATION_VERSION,
    ONET_SOURCE_VERSION,
    RIASEC_ELEMENT_IDS,
    RIASEC_ELEMENT_NAMES,
    WI_TRANSFORMATION_VERSION,
    WORK_CONTEXT_ELEMENT_IDS,
    WORK_STYLE_ELEMENT_IDS,
    WORK_VALUES_ELEMENT_IDS,
    WORK_VALUES_SOURCE_LABEL,
    OnetSocData,
    get_onet_data,
)
from app.services.career_kb.seed import ALPHA_CAREER_CODES, MATCHING_METHODOLOGY_VERSION
from app.services.career_kb.seed_hardened import seed_alpha_career_matching_profiles_hardened
from app.services.career_kb.vectors import (
    add_career_matching_component,
    create_career_matching_profile,
    ct_to_normalized,
    cx_to_normalized,
    ex_to_normalized,
    oi_to_normalized,
    wi_to_normalized,
)
from app.services.knowledge.retrieval import get_career_by_code


def _primary_soc(mnp_career_code: str) -> str | None:
    """M4.5 "primary-mapping rule": use the single CONFIRMED O*NET-SOC
    code's data; if a career only has a PROVISIONAL mapping, use that;
    a deliberately UNMAPPED career (empty list) gets no vector. No
    confidence-weighted blending of multiple codes (no such rule is
    Founder-approved)."""
    record = get_onet_source(mnp_career_code)
    if record is None or not record.onet_occupations:
        return None
    confirmed = [o.soc_code for o in record.onet_occupations if o.mapping_status == "confirmed"]
    if confirmed:
        return confirmed[0]
    return record.onet_occupations[0].soc_code


async def _add_riasec(session, profile, data: OnetSocData) -> None:
    for letter, raw in data.riasec_oi.items():
        await add_career_matching_component(
            session, profile=profile, scale_family=ScaleFamily.RIASEC, scale_key=letter,
            normalized_value=oi_to_normalized(raw), transformation_version=OI_TRANSFORMATION_VERSION,
            source_system="onet", source_element_id=RIASEC_ELEMENT_IDS[letter],
            source_element_name=f"Interests — {RIASEC_ELEMENT_NAMES[letter]}",
            source_raw_value=str(raw),
        )


async def _add_work_style(session, profile, data: OnetSocData) -> None:
    for scale_key in ("leadership", "initiative", "ambiguity_tolerance"):
        raw = data.work_style_wi.get(scale_key)
        if raw is None:
            continue
        element_name, element_id = WORK_STYLE_ELEMENT_IDS[scale_key]
        await add_career_matching_component(
            session, profile=profile, scale_family=ScaleFamily.WORK_STYLE, scale_key=scale_key,
            normalized_value=wi_to_normalized(raw), transformation_version=WI_TRANSFORMATION_VERSION,
            source_system="onet", source_element_id=element_id, source_element_name=element_name,
            source_raw_value=str(raw),
        )
    # DERIVED `collaboration` = mean(Social Orientation, Cooperation) -- M4.5 convention.
    social = data.work_style_wi.get("collaboration_social")
    cooperation = data.work_style_wi.get("collaboration_cooperation")
    if social is not None and cooperation is not None:
        await add_career_matching_component(
            session, profile=profile, scale_family=ScaleFamily.WORK_STYLE, scale_key="collaboration",
            normalized_value=(wi_to_normalized(social) + wi_to_normalized(cooperation)) / 2.0,
            transformation_version=WI_TRANSFORMATION_VERSION, source_system="onet",
            source_element_id=f"{WORK_STYLE_ELEMENT_IDS['collaboration_social'][1]}+"
                              f"{WORK_STYLE_ELEMENT_IDS['collaboration_cooperation'][1]}",
            source_element_name="Social Orientation + Cooperation (mean)",
            source_raw_value=f"{social},{cooperation}",
        )
    # `structure_preference`: never populated -- no O*NET Work Context element
    # corresponds to it in 30.3 or 31.0 (M4.5 finding, re-confirmed by M4.6).


async def _add_work_environment(session, profile, data: OnetSocData) -> None:
    for scale_key in ("collaboration_context", "customer_interaction_context", "schedule_predictability"):
        raw = data.work_context.get(scale_key)
        if raw is None:
            continue
        element_name, element_id, scale_id = WORK_CONTEXT_ELEMENT_IDS[scale_key]
        normalized = ct_to_normalized(raw) if scale_id == "CT" else cx_to_normalized(raw)
        transformation = CT_TRANSFORMATION_VERSION if scale_id == "CT" else CX_TRANSFORMATION_VERSION
        await add_career_matching_component(
            session, profile=profile, scale_family=ScaleFamily.WORK_ENVIRONMENT, scale_key=scale_key,
            normalized_value=normalized, transformation_version=transformation,
            source_system="onet", source_element_id=element_id, source_element_name=element_name,
            source_raw_value=str(raw),
        )
    setting = data.work_context.get("setting")
    if setting is not None:
        element_name, element_id, _ = WORK_CONTEXT_ELEMENT_IDS["setting"]
        await add_career_matching_component(
            session, profile=profile, scale_family=ScaleFamily.WORK_ENVIRONMENT, scale_key="setting",
            normalized_value=cx_to_normalized(setting), transformation_version=CX_TRANSFORMATION_VERSION,
            source_system="onet", source_element_id=element_id, source_element_name=element_name,
            source_raw_value=str(setting),
        )
    standing = data.work_context.get("physical_environment_standing")
    walking = data.work_context.get("physical_environment_walking")
    if standing is not None and walking is not None:
        await add_career_matching_component(
            session, profile=profile, scale_family=ScaleFamily.WORK_ENVIRONMENT,
            scale_key="physical_environment",
            normalized_value=(cx_to_normalized(standing) + cx_to_normalized(walking)) / 2.0,
            transformation_version=CX_TRANSFORMATION_VERSION, source_system="onet",
            source_element_id=f"{WORK_CONTEXT_ELEMENT_IDS['physical_environment_standing'][1]}+"
                              f"{WORK_CONTEXT_ELEMENT_IDS['physical_environment_walking'][1]}",
            source_element_name="Spend Time Standing + Spend Time Walking or Running (mean)",
            source_raw_value=f"{standing},{walking}",
        )


async def _add_work_values(session, profile, data: OnetSocData) -> None:
    """The 3 DIRECT-mappable MNP keys only, from O*NET 30.2. The gate in
    `add_career_matching_component` independently refuses the other 5
    (`MatchDisabledScaleError`) -- this loop simply never offers them."""
    for scale_key, raw in data.work_values_ex.items():
        element_name, element_id = WORK_VALUES_ELEMENT_IDS[scale_key]
        await add_career_matching_component(
            session, profile=profile, scale_family=ScaleFamily.WORK_VALUES, scale_key=scale_key,
            normalized_value=ex_to_normalized(raw), transformation_version=EX_TRANSFORMATION_VERSION,
            source_system="onet",
            source_element_id=element_id,
            source_element_name=f"{element_name} (O*NET Work Values, {WORK_VALUES_SOURCE_LABEL})",
            source_raw_value=str(raw),
        )


async def _onet_source_id(session):
    """The O*NET `KnowledgeSource` row -- already created by
    `seed_alpha_career_matching_profiles` earlier in this call graph
    (M3's `_ensure_onet_knowledge_source`). Not re-created here."""
    row = (
        await session.execute(
            select(KnowledgeSource).where(
                KnowledgeSource.source_type == "structured_occupational_data",
                KnowledgeSource.publisher == "O*NET",
            )
        )
    ).scalar_one_or_none()
    return row.id if row is not None else None


async def _ensure_job_zone_fact(session, career, data: OnetSocData, source_id) -> None:
    """Check-then-create, exactly like M3's `seed.py` -- an existing
    `onet_job_zone` fact (from the M3 / M4.5 seed) is left untouched, not
    mutated, so anything that already read it stays reproducible. A job
    zone that genuinely changed between O*NET releases would need explicit
    handling (a new KB version), not a silent overwrite here."""
    if data.job_zone is None:
        return
    existing = await session.execute(
        select(CareerFact).where(
            CareerFact.career_id == career.id,
            CareerFact.fact_type == "onet_job_zone",
            CareerFact.knowledge_base_version_id == career.knowledge_base_version_id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        return
    session.add(
        CareerFact(
            career_id=career.id,
            knowledge_base_version_id=career.knowledge_base_version_id,
            fact_type="onet_job_zone",
            value_text=str(data.job_zone),
            value_metadata={"source_system": "onet", "source_version": ONET_SOURCE_VERSION},
            is_market_sensitive=False,
            verification_state=FactVerificationState.UNVERIFIED,
            source_id=source_id,
        )
    )
    await session.flush()


async def seed_career_matching_profiles_v3(session: AsyncSession) -> list[CareerMatchingProfile]:
    """Idempotent. Returns the current (now v0.3) `CareerMatchingProfile`
    for each mapped Alpha career. Deliberately-UNMAPPED careers
    (`community_outreach_coordinator`) get no v0.3 profile, exactly as in
    M3/M4.5."""

    # Ensure the base catalog + O*NET crosswalk + v0.1/v0.2 profiles exist.
    await seed_alpha_career_matching_profiles_hardened(session)

    onet_source_id = await _onet_source_id(session)

    profiles: list[CareerMatchingProfile] = []
    for code in ALPHA_CAREER_CODES:
        soc = _primary_soc(code)
        if soc is None:
            continue  # UNMAPPED -- no vector, by design
        data = get_onet_data(soc)
        if data is None:
            raise RuntimeError(
                f"career {code!r} maps to O*NET-SOC {soc} but it is missing from "
                "onet_source_v3.json -- regenerate:  "
                "python -m scripts.onet_import.export_source_artifact"
            )

        career = await get_career_by_code(session, code)
        profile = await create_career_matching_profile(
            session,
            career_id=career.id,
            career_vector_version=CAREER_VECTOR_VERSION_V3,
            matching_methodology_version=MATCHING_METHODOLOGY_VERSION,
            source_version=ONET_SOURCE_VERSION,
            mapping_version=NUMERIC_MAPPING_VERSION_V3,
            provisional=True,  # still Alpha -- unreviewed / uncalibrated
        )

        await _add_riasec(session, profile, data)
        await _add_work_style(session, profile, data)
        await _add_work_environment(session, profile, data)
        await _add_work_values(session, profile, data)
        await _ensure_job_zone_fact(session, career, data, onet_source_id)

        profiles.append(profile)

    return profiles
