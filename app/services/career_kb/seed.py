"""Seeds the Matching V1 Alpha career vector catalog (Founder Review "M3
GO", 2026-08-28): 24 careers, reused unchanged from the existing Stage 3A
curated seed (`app/services/knowledge/seed.py::ensure_seed_knowledge_base`,
32 careers) -- no new/duplicate Career rows are created, no existing
Career row is altered. This is deliberate: that seed's own docstring
already states its 32 careers were "chosen for structural diversity," and
its 12-domain, 2-per-domain shape is exactly what Founder Review's Alpha
selection criteria (§2/§16) asks for -- reusing it avoids fragmenting the
catalog into two parallel, partially-overlapping lists.

Idempotent end-to-end: `seed_alpha_career_matching_profiles` may be called
any number of times against the same DB state and creates no duplicate
mapping/profile/component/source rows (every sub-step checks-then-creates,
never blind-inserts).
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_basic_assessment import ScaleFamily
from app.db.models_career_kb import CareerMatchingProfile, ExternalMappingStatus, ExternalSourceSystem
from app.db.models_knowledge import CareerFact, FactVerificationState, KnowledgeSource
from app.services.basic_assessment.seed import seed_alpha_long_form
from app.services.career_kb.crosswalk import create_external_mapping, get_external_mappings, mark_unmapped
from app.services.career_kb.onet_alpha_fixture import ONET_SOURCE_VERSION, MAPPING_VERSION, load_onet_source
from app.services.career_kb.vectors import (
    RIASEC_LETTERS,
    RIASEC_TRANSFORMATION_VERSION,
    add_career_matching_component,
    create_career_matching_profile,
    holland_code_to_riasec_vector,
)
from app.services.knowledge.retrieval import get_career_by_code
from app.services.knowledge.seed import ensure_seed_knowledge_base

CAREER_VECTOR_VERSION = "career_vector_v0.1"
MATCHING_METHODOLOGY_VERSION = "golden_test_v0.1"
EXPLICIT_STYLE_SIGNAL_TRANSFORMATION_VERSION = "onet_explicit_style_signal_v0.1"
EXPLICIT_STYLE_SIGNAL_VALUE = 0.85  # disclosed proxy for "O*NET textually confirms this style as emphasized"

# The 24 Alpha career codes -- 2 per domain across the 12 categories
# Founder Review §2 named explicitly, selected from the existing 32-career
# Stage 3A seed (see module docstring). The remaining 8 seeded careers
# (marketing/administration/hospitality/manufacturing domains) are simply
# not included in the M3 Alpha vector-building pass -- their Career rows
# are untouched and available for a future catalog expansion.
ALPHA_CAREER_CODES = [
    "software_developer", "it_support_specialist",          # software / data
    "civil_engineer", "mechanical_engineer",                  # engineering / technical
    "registered_nurse", "pharmacist",                         # healthcare
    "school_teacher", "corporate_trainer",                    # education
    "social_worker", "community_outreach_coordinator",        # social / helping
    "sales_manager", "retail_sales_associate",                # sales
    "operations_manager", "project_manager",                  # management
    "accountant", "financial_analyst",                        # finance / accounting
    "graphic_designer", "video_editor",                       # creative / design
    "truck_driver", "logistics_coordinator",                  # logistics / operations
    "electrician", "plumber",                                 # skilled / practical
    "customer_service_representative", "call_center_operator",  # customer / service
]


async def _ensure_onet_knowledge_source(session: AsyncSession) -> KnowledgeSource:
    existing = await session.execute(
        select(KnowledgeSource).where(
            KnowledgeSource.source_type == "structured_occupational_data", KnowledgeSource.publisher == "O*NET"
        )
    )
    found = existing.scalar_one_or_none()
    if found is not None:
        return found

    source = KnowledgeSource(
        source_type="structured_occupational_data",
        publisher="O*NET",
        title="O*NET Database (Interests, Job Zones, Work Styles) — sponsored by the U.S. Department of Labor",
        url="https://www.onetonline.org/",
        country_region="US",
        trust_level="high",
        notes=(
            f"Source version {ONET_SOURCE_VERSION}. O*NET content is developed by the National Center for "
            "O*NET Development and is in the public domain in the United States, per O*NET's published usage "
            "terms (attribution requested: 'This [product] incorporates information from O*NET Web Services "
            "by the U.S. Department of Labor, Employment and Training Administration.'). See "
            "docs/engineering/24_MATCHING_V1_M3_CAREER_VECTOR_KB.md §Licensing for the full attribution text "
            "and citation this product must display wherever O*NET-derived data is shown to end users."
        ),
    )
    session.add(source)
    await session.flush()
    return source


async def seed_alpha_career_matching_profiles(session: AsyncSession) -> list[CareerMatchingProfile]:
    """Idempotent orchestrator. Returns the current `CareerMatchingProfile`
    for each of the 24 Alpha careers (creating them, and their mappings/
    components, only if they do not already exist for the current source/
    mapping/vector version stamps)."""

    await ensure_seed_knowledge_base(session)
    await seed_alpha_long_form(session)  # M1's AssessmentScale rows are required by vectors.add_career_matching_component
    onet_source = await _ensure_onet_knowledge_source(session)

    profiles: list[CareerMatchingProfile] = []

    for record in load_onet_source():
        if record.mnp_career_code not in ALPHA_CAREER_CODES:
            continue  # fixture may carry entries beyond the Alpha 24 in the future; ignore silently

        career = await get_career_by_code(session, record.mnp_career_code)

        existing_mappings = await get_external_mappings(session, career.id, source_system=ExternalSourceSystem.ONET)
        if not existing_mappings:
            if not record.onet_occupations:
                await mark_unmapped(
                    session,
                    career_id=career.id,
                    source_system=ExternalSourceSystem.ONET,
                    mapping_version=MAPPING_VERSION,
                    notes="No single O*NET occupation corresponds cleanly to this MNP career (M3 Alpha).",
                )
            else:
                for occ in record.onet_occupations:
                    await create_external_mapping(
                        session,
                        career_id=career.id,
                        source_system=ExternalSourceSystem.ONET,
                        external_code=occ.soc_code,
                        external_label=occ.label,
                        external_url=f"https://www.onetonline.org/link/summary/{occ.soc_code}",
                        mapping_status=ExternalMappingStatus(occ.mapping_status),
                        mapping_version=MAPPING_VERSION,
                        confidence=occ.confidence,
                    )

        profile = await create_career_matching_profile(
            session,
            career_id=career.id,
            career_vector_version=CAREER_VECTOR_VERSION,
            matching_methodology_version=MATCHING_METHODOLOGY_VERSION,
            source_version=ONET_SOURCE_VERSION,
            mapping_version=MAPPING_VERSION,
            provisional=True,  # ALL Alpha vectors are provisional (Founder Review §21), unconditionally
        )

        if record.holland_code:
            riasec_vector = holland_code_to_riasec_vector(record.holland_code)
            for letter in RIASEC_LETTERS:
                await add_career_matching_component(
                    session,
                    profile=profile,
                    scale_family=ScaleFamily.RIASEC,
                    scale_key=letter,
                    normalized_value=riasec_vector[letter],
                    transformation_version=RIASEC_TRANSFORMATION_VERSION,
                    source_system="onet",
                    source_element_id=record.onet_occupations[0].soc_code if record.onet_occupations else None,
                    source_element_name="Interests (RIASEC)",
                    source_raw_value=record.holland_code,
                )
        # If holland_code is None (UNMAPPED career), no RIASEC components are
        # created at all -- UNKNOWN != zero, not even a "baseline" vector.

        for scale_key, signal_note in record.work_style_signals.items():
            await add_career_matching_component(
                session,
                profile=profile,
                scale_family=ScaleFamily.WORK_STYLE,
                scale_key=scale_key,
                normalized_value=EXPLICIT_STYLE_SIGNAL_VALUE,
                transformation_version=EXPLICIT_STYLE_SIGNAL_TRANSFORMATION_VERSION,
                source_system="onet",
                source_element_id=record.onet_occupations[0].soc_code if record.onet_occupations else None,
                source_element_name=signal_note,
                source_raw_value="explicit_high_importance",
            )
        # Work Values and Work Environment: no components created for any
        # Alpha career in M3 -- honest scope limitation, see doc 24.

        if record.job_zone is not None:
            existing_fact = await session.execute(
                select(CareerFact).where(
                    CareerFact.career_id == career.id,
                    CareerFact.fact_type == "onet_job_zone",
                    CareerFact.knowledge_base_version_id == career.knowledge_base_version_id,
                )
            )
            if existing_fact.scalar_one_or_none() is None:
                session.add(
                    CareerFact(
                        career_id=career.id,
                        knowledge_base_version_id=career.knowledge_base_version_id,
                        fact_type="onet_job_zone",
                        value_text=str(record.job_zone),
                        value_metadata={"source_system": "onet", "source_version": ONET_SOURCE_VERSION},
                        is_market_sensitive=False,
                        verification_state=(
                            FactVerificationState.VERIFIED if record.verified_live else FactVerificationState.UNVERIFIED
                        ),
                        source_id=onet_source.id,
                    )
                )
                await session.flush()

        profiles.append(profile)

    return profiles
