"""Shared fixtures for the Stage 3B Slice 2 end-to-end pipeline tests
(tests/test_direction_pipeline.py). Builds real DB rows -- unlike
`tests/direction_test_helpers.py`'s pure in-memory builders -- since the
orchestrator itself is what's under test here.
"""

from __future__ import annotations

import uuid

from app.db.models_identity import IdentityUser
from app.db.models_knowledge import (
    Career,
    CareerDomain,
    CareerStatus,
    IndoorOutdoor,
    RequirementCategory,
    RequirementCertainty,
    SkillRequirementType,
    WorkSetting,
)
from app.db.models_profile import ClaimStatus, PotentialProfile, ProfileClaim, ProfileDimension, ProfileGenerationStatus
from app.services.knowledge.careers import (
    add_career_requirement,
    add_career_skill,
    create_career,
    create_knowledge_source,
    set_career_work_context,
)
from app.services.knowledge.skills import ensure_skills_taxonomy, get_skill_term_by_key
from app.services.knowledge.versioning import create_draft_version, publish_version


async def make_user(session) -> IdentityUser:
    user = IdentityUser()
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def make_ready_profile(session, *, user_id: uuid.UUID, version: int = 1) -> PotentialProfile:
    profile = PotentialProfile(
        user_id=user_id, session_id=uuid.uuid4(), version=version, status=ProfileGenerationStatus.READY,
        is_current=True, methodology_version="potential_dimensions:v1", prompt_version="test",
    )
    session.add(profile)
    await session.commit()
    await session.refresh(profile)
    return profile


async def add_claim(
    session,
    *,
    profile_id: uuid.UUID,
    dimension: ProfileDimension,
    term_key: str | None = None,
    label: str = "test claim",
    normalized_value: str = "test value",
    confidence: float = 0.9,
    status: ClaimStatus = ClaimStatus.SUPPORTED,
) -> ProfileClaim:
    claim = ProfileClaim(
        profile_id=profile_id, dimension=dimension, term_key=term_key, label=label,
        normalized_value=normalized_value, confidence=confidence, status=status, generated_by="test",
    )
    session.add(claim)
    await session.commit()
    await session.refresh(claim)
    return claim


async def seed_knowledge_base(session) -> dict:
    """Builds a small, real, published KnowledgeBaseVersion with four
    careers exercising: a real Potential Fit match, a real Transition
    Feasibility gap, a HARD_FACTUAL-blockable requirement, a
    TYPICAL_RECOMMENDATION requirement (must never block), and an exact
    title collision for dedup. Returns a dict of everything a test might
    need by name."""
    skills_tv = await ensure_skills_taxonomy(session)
    programming_term = await get_skill_term_by_key(session, taxonomy_version_id=skills_tv.id, term_key="programming")
    communication_term = await get_skill_term_by_key(session, taxonomy_version_id=skills_tv.id, term_key="communication")
    leadership_term = await get_skill_term_by_key(session, taxonomy_version_id=skills_tv.id, term_key="leadership")
    teamwork_term = await get_skill_term_by_key(session, taxonomy_version_id=skills_tv.id, term_key="teamwork")

    kb_version = await create_draft_version(session, notes="Slice 2 e2e test KB")
    source = await create_knowledge_source(session, source_type="internal_curation", publisher="Test", title="Test source")

    dev = await create_career(
        session, knowledge_base_version_id=kb_version.id, code="dev_strong", title_uk="Розробник ПЗ (сильний)",
        short_description="Software developer.", domain=CareerDomain.TECHNOLOGY,
        works_with_technology=0.95, works_with_people=0.1, creative_component=0.3,
    )
    await add_career_skill(session, career_id=dev.id, skill_term_id=programming_term.id, requirement_type=SkillRequirementType.REQUIRED)
    await set_career_work_context(session, career_id=dev.id, setting=WorkSetting.REMOTE, indoor_outdoor=IndoorOutdoor.INDOOR, teamwork_level=0.2)
    # a TYPICAL_RECOMMENDATION requirement -- must never auto-block, no source needed
    await add_career_requirement(
        session, career_id=dev.id, category=RequirementCategory.EDUCATION,
        description="A degree is typically expected but not required.", certainty=RequirementCertainty.TYPICAL_RECOMMENDATION,
    )

    dev_weak_dup = await create_career(
        session, knowledge_base_version_id=kb_version.id, code="dev_weak_dup", title_uk="Розробник ПЗ (сильний)",  # EXACT title collision with `dev`
        short_description="Software developer (weaker curated data, exact title duplicate).",
        domain=CareerDomain.TECHNOLOGY, works_with_technology=0.5, works_with_people=0.1,
    )
    await add_career_skill(session, career_id=dev_weak_dup.id, skill_term_id=programming_term.id, requirement_type=SkillRequirementType.REQUIRED)

    dev_gap = await create_career(
        session, knowledge_base_version_id=kb_version.id, code="dev_needs_advanced_skills",
        title_uk="Розробник ПЗ (потребує додаткових навичок)", short_description="Software developer role requiring skills the candidate lacks.",
        domain=CareerDomain.TECHNOLOGY, works_with_technology=0.95, works_with_people=0.1,
    )
    await add_career_skill(session, career_id=dev_gap.id, skill_term_id=programming_term.id, requirement_type=SkillRequirementType.REQUIRED)
    await add_career_skill(session, career_id=dev_gap.id, skill_term_id=communication_term.id, requirement_type=SkillRequirementType.REQUIRED)
    await add_career_skill(session, career_id=dev_gap.id, skill_term_id=leadership_term.id, requirement_type=SkillRequirementType.REQUIRED)
    await add_career_skill(session, career_id=dev_gap.id, skill_term_id=teamwork_term.id, requirement_type=SkillRequirementType.REQUIRED)

    pilot = await create_career(
        session, knowledge_base_version_id=kb_version.id, code="commercial_pilot", title_uk="Пілот", short_description="Commercial pilot.",
        domain=CareerDomain.LOGISTICS_TRANSPORT,
        works_with_technology=0.9, works_with_people=0.2,
    )
    await add_career_requirement(
        session, career_id=pilot.id, category=RequirementCategory.LICENSE,
        description="A valid commercial pilot license is legally required.", certainty=RequirementCertainty.HARD_FACTUAL,
        source_id=source.id,
    )

    sales = await create_career(
        session, knowledge_base_version_id=kb_version.id, code="sales_manager", title_uk="Менеджер з продажів",
        short_description="Sales manager.", domain=CareerDomain.SALES, works_with_people=0.95, works_with_technology=0.1,
    )
    await add_career_skill(session, career_id=sales.id, skill_term_id=communication_term.id, requirement_type=SkillRequirementType.REQUIRED)
    await set_career_work_context(session, career_id=sales.id, setting=WorkSetting.OFFICE, teamwork_level=0.9)

    await publish_version(session, kb_version.id)
    await session.refresh(kb_version)

    return dict(
        kb_version=kb_version, source=source, dev=dev, dev_weak_dup=dev_weak_dup, dev_gap=dev_gap,
        pilot=pilot, sales=sales, programming_term=programming_term, communication_term=communication_term,
        leadership_term=leadership_term, teamwork_term=teamwork_term,
    )


async def seed_eligible_developer_profile(session, *, user) -> dict:
    """A READY profile clearing the minimum threshold, evidenced as a
    strong match for `dev`/`dev_weak_dup` (programming + technical
    interest), with a confirmed-missing `communication` skill (real
    Transition Feasibility gap for `dev_gap`/`sales`) and a credential
    constraint claim (for the hard-constraint-gate tests)."""
    profile = await make_ready_profile(session, user_id=user.id)

    interest_claim = await add_claim(
        session, profile_id=profile.id, dimension=ProfileDimension.INTEREST,
        term_key="technical_problem_solving", normalized_value="enjoys technical problem solving", confidence=0.95,
    )
    skill_claim = await add_claim(
        session, profile_id=profile.id, dimension=ProfileDimension.SKILL,
        term_key="programming", normalized_value="proficient in programming", confidence=0.95,
    )
    comm_gap_claim = await add_claim(
        session, profile_id=profile.id, dimension=ProfileDimension.SKILL, term_key="communication",
        normalized_value="cannot do public communication, no experience", confidence=0.8,
    )
    leadership_gap_claim = await add_claim(
        session, profile_id=profile.id, dimension=ProfileDimension.SKILL, term_key="leadership",
        normalized_value="never used leadership skills, no experience leading teams", confidence=0.8,
    )
    teamwork_gap_claim = await add_claim(
        session, profile_id=profile.id, dimension=ProfileDimension.SKILL, term_key="teamwork",
        normalized_value="cannot work well in teams, lack teamwork experience", confidence=0.8,
    )
    strength_claim = await add_claim(
        session, profile_id=profile.id, dimension=ProfileDimension.STRENGTH,
        term_key=None, normalized_value="strong analytical strength", confidence=0.85,
    )
    constraint_claim = await add_claim(
        session, profile_id=profile.id, dimension=ProfileDimension.CONSTRAINT, term_key="credential",
        normalized_value="I have no pilot license and cannot obtain one", confidence=0.9,
    )
    goal_claim = await add_claim(
        session, profile_id=profile.id, dimension=ProfileDimension.GOAL, term_key=None,
        normalized_value="wants a stable remote job", confidence=0.6,
    )

    return dict(
        profile=profile, interest_claim=interest_claim, skill_claim=skill_claim, comm_gap_claim=comm_gap_claim,
        leadership_gap_claim=leadership_gap_claim, teamwork_gap_claim=teamwork_gap_claim,
        strength_claim=strength_claim, constraint_claim=constraint_claim, goal_claim=goal_claim,
    )
