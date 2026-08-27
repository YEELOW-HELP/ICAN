"""Stage 3B Slice 3 §2/§3: the deterministic Critic."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.db.models_direction import (
    ConstraintCheckResult,
    CriticSeverity,
    Direction,
    DirectionConstraintCheck,
    DirectionCriticFinding,
    DirectionPlacement,
    DirectionRun,
    DirectionRunStatus,
)
from app.services.direction import critic
from app.services.direction.config import ensure_experimental_ranking_policy, ensure_experimental_scoring_config
from tests.direction_pipeline_test_helpers import make_user, seed_eligible_developer_profile, seed_knowledge_base


@pytest.fixture
async def world(session):
    scoring_config = await ensure_experimental_scoring_config(session)
    ranking_policy = await ensure_experimental_ranking_policy(session)
    kb = await seed_knowledge_base(session)
    user = await make_user(session)
    prof = await seed_eligible_developer_profile(session, user=user)
    return dict(**kb, **prof, user=user, scoring_config=scoring_config, ranking_policy=ranking_policy)


async def _findings_by_code(session, run_id) -> dict[str, list[DirectionCriticFinding]]:
    rows = (await session.execute(select(DirectionCriticFinding).where(DirectionCriticFinding.run_id == run_id))).scalars().all()
    by_code: dict[str, list[DirectionCriticFinding]] = {}
    for row in rows:
        by_code.setdefault(row.code, []).append(row)
    return by_code


async def _minimal_run(session, world) -> DirectionRun:
    run = DirectionRun(
        user_id=world["user"].id, profile_id=world["profile"].id, knowledge_base_version_id=world["kb_version"].id,
        scoring_config_id=world["scoring_config"].id, ranking_policy_id=world["ranking_policy"].id,
        version=99, status=DirectionRunStatus.READY, is_current=False,
        methodology_version="mnp-hpm:v0.1", direction_engine_version="direction-intelligence:v0.1-slice1",
        direction_evaluation_model_version="mnp-direction-evaluation-model:v0.1", ranking_policy_version="mnp-ranking-policy:v0.1",
        dimension_mapping_version="legacy-to-mnp:v0.1", subdimension_taxonomy_version="mnp-hpm-subdimensions:v0.1",
        constraint_taxonomy_version="mnp-constraint-taxonomy:v0.1", evidence_standard_version="mnp-evidence-standard:v0.1",
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


# ---------------------------------------------------------------- 4


async def test_critic_finds_blocked_direction_in_main(session, world):
    """#4: a Direction with a confirmed hard-BLOCK constraint check but
    placement=MAIN is a BLOCKER."""
    run = await _minimal_run(session, world)
    direction = Direction(
        run_id=run.id, career_id=world["pilot"].id, career_code="commercial_pilot", domain="technology",
        placement=DirectionPlacement.MAIN, potential_fit_scored_component_count=0,
        goal_alignment_scored_component_count=0, transition_feasibility_scored_component_count=0,
    )
    session.add(direction)
    await session.flush()
    session.add(
        DirectionConstraintCheck(
            direction_id=direction.id, constraint_subtype="credential", result=ConstraintCheckResult.BLOCK,
            is_hard=True, explanation="test: confirmed hard constraint blocks this career",
        )
    )
    await session.commit()

    findings = await critic.run_critic(session, run_id=run.id)
    by_code = await _findings_by_code(session, run.id)
    assert critic.CriticCode.BLOCKED_CAREER_IN_RECOMMENDATION in by_code
    finding = by_code[critic.CriticCode.BLOCKED_CAREER_IN_RECOMMENDATION][0]
    assert finding.severity is CriticSeverity.BLOCKER
    assert finding.direction_id == direction.id


# ---------------------------------------------------------------- 5


async def test_critic_finds_nonexistent_provenance_reference(session, world):
    """#5: an explanation_bundle referencing a ProfileClaim id that does
    not exist is a BLOCKER."""
    run = await _minimal_run(session, world)
    fake_claim_id = str(uuid.uuid4())
    direction = Direction(
        run_id=run.id, career_id=world["dev"].id, career_code="dev_strong", domain="technology",
        placement=DirectionPlacement.MAIN, potential_fit_scored_component_count=0,
        goal_alignment_scored_component_count=0, transition_feasibility_scored_component_count=0,
        explanation_bundle={
            "why_fit": {}, "why_now": {}, "transition": {}, "confidence": {},
            "provenance": {
                "contributing_claim_ids": [fake_claim_id], "evidence_ids": [], "career_id": str(world["dev"].id),
                "career_requirement_ids": [], "knowledge_base_version_id": str(world["kb_version"].id),
                "scoring_config_version": 1, "ranking_policy_version": 1, "methodology_version": "mnp-hpm:v0.1",
            },
        },
    )
    session.add(direction)
    await session.commit()

    await critic.run_critic(session, run_id=run.id)
    by_code = await _findings_by_code(session, run.id)
    assert critic.CriticCode.EXPLANATION_REFERENCES_NONEXISTENT_CLAIM in by_code
    finding = by_code[critic.CriticCode.EXPLANATION_REFERENCES_NONEXISTENT_CLAIM][0]
    assert finding.severity is CriticSeverity.BLOCKER
    assert fake_claim_id in (finding.related_claim_ids or [])


# ---------------------------------------------------------------- 6, 7


async def test_critic_warns_on_unknown_goal_alignment_and_warning_is_not_blocker(session, world):
    """#6 + #7: unknown Goal Alignment on a MAIN direction is a WARNING,
    and a WARNING never counts as (or coexists misleadingly with) a
    BLOCKER for the same, otherwise-clean direction."""
    run = await _minimal_run(session, world)
    direction = Direction(
        run_id=run.id, career_id=world["dev"].id, career_code="dev_strong", domain="technology",
        placement=DirectionPlacement.MAIN, potential_fit_scored_component_count=0,
        goal_alignment_band=None, goal_alignment_scored_component_count=0,
        transition_feasibility_scored_component_count=0,
    )
    session.add(direction)
    await session.commit()

    await critic.run_critic(session, run_id=run.id)
    by_code = await _findings_by_code(session, run.id)
    assert critic.CriticCode.GOAL_ALIGNMENT_UNKNOWN in by_code
    ga_finding = by_code[critic.CriticCode.GOAL_ALIGNMENT_UNKNOWN][0]
    assert ga_finding.severity is CriticSeverity.WARNING

    blocker_count = await review_module_unresolved_blocker_count(session, run.id)
    assert blocker_count == 0  # the WARNING alone never produces a BLOCKER


async def review_module_unresolved_blocker_count(session, run_id) -> int:
    from app.services.direction.review import unresolved_blocker_count

    return await unresolved_blocker_count(session, run_id=run_id)


# ---------------------------------------------------------------- bonus: real e2e critic pass is clean


async def test_critic_finds_zero_blockers_on_a_real_clean_run(session, world):
    """Sanity counterpart: running the real orchestrator + critic on a
    correctly-generated run produces zero BLOCKER findings."""
    from app.services.direction.pipeline import generate_directions

    run = await generate_directions(session, user_id=world["user"].id)
    await critic.run_critic(session, run_id=run.id)
    assert await review_module_unresolved_blocker_count(session, run.id) == 0


async def test_critic_flags_duplicate_career_in_recommendations(session, world):
    run = await _minimal_run(session, world)
    for i in range(2):
        session.add(
            Direction(
                run_id=run.id, career_id=world["dev"].id, career_code=f"dev_strong_dup_{i}", domain="technology",
                placement=DirectionPlacement.MAIN, potential_fit_scored_component_count=0,
                goal_alignment_scored_component_count=0, transition_feasibility_scored_component_count=0,
            )
        )
    await session.commit()

    await critic.run_critic(session, run_id=run.id)
    by_code = await _findings_by_code(session, run.id)
    assert critic.CriticCode.DUPLICATE_CAREER_IN_RECOMMENDATIONS in by_code
    assert by_code[critic.CriticCode.DUPLICATE_CAREER_IN_RECOMMENDATIONS][0].severity is CriticSeverity.BLOCKER
