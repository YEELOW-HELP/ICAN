"""Stage 3B Slice 3 §11 item 24: the full path works end-to-end --
generate_directions -> critic -> narrative -> consultant approval."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.db.models import AdminRole
from app.db.models_direction import (
    Direction,
    DirectionCriticFinding,
    DirectionPlacement,
    DirectionRunStatus,
    ReviewStatus,
)
from app.services.direction import critic, review
from app.services.direction.config import ensure_experimental_ranking_policy, ensure_experimental_scoring_config
from app.services.direction.pipeline import generate_directions
from tests.direction_pipeline_test_helpers import make_user, seed_eligible_developer_profile, seed_knowledge_base
from tests.profile_test_helpers import make_admin
from tests.test_direction_narrative import FakeGateway, _WELL_FORMED_PAYLOAD
from app.services.direction.narrative import DirectionNarrator, generate_narratives_for_run


async def test_full_path_generate_critic_narrative_approve(session):
    """#24. Also produces the concrete example for the Founder Report."""
    await ensure_experimental_scoring_config(session)
    await ensure_experimental_ranking_policy(session)
    kb = await seed_knowledge_base(session)
    user = await make_user(session)
    await seed_eligible_developer_profile(session, user=user)

    # 1. generate_directions
    run = await generate_directions(session, user_id=user.id)
    assert run.status is DirectionRunStatus.READY

    # 2. critic
    findings = await critic.run_critic(session, run_id=run.id)
    blockers = [f for f in findings if f.severity.value == "blocker"]
    assert blockers == []  # a correctly-generated run has zero BLOCKER findings

    # 3. narrative
    fake = FakeGateway(payloads=[_WELL_FORMED_PAYLOAD] * 10)
    narrated_count = await generate_narratives_for_run(session, run_id=run.id, narrator=DirectionNarrator(fake))
    assert narrated_count >= 1

    # 4. consultant approval
    consultant = await make_admin(session, role=AdminRole.CAREER_CONSULTANT, email="full-path-consultant@test.dev")
    review_row = await review.approve_run(session, run_id=run.id, reviewer=consultant, comment="Approved for pilot.")
    assert review_row.status is ReviewStatus.APPROVED

    approved_run = await review.get_approved_direction_run(session, user_id=user.id)
    assert approved_run.id == run.id

    # Print the concrete example the Founder Report references.
    directions = (
        await session.execute(
            select(Direction).where(Direction.run_id == run.id, Direction.placement.in_([DirectionPlacement.MAIN, DirectionPlacement.ALTERNATIVE]))
        )
    ).scalars().all()
    assert directions
    example = directions[0]
    assert example.narrative_structured is not None
    assert example.explanation_bundle is not None

    run_findings = (
        await session.execute(select(DirectionCriticFinding).where(DirectionCriticFinding.run_id == run.id))
    ).scalars().all()

    print("\n=== Slice 3 full-path example ===")
    print(f"Direction: {example.career_code} | placement={example.placement.value}")
    print(f"  PF={example.potential_fit_raw_experimental} {example.potential_fit_band}")
    print(f"  GA={example.goal_alignment_raw_experimental} {example.goal_alignment_band}")
    print(f"  TF={example.transition_feasibility_raw_experimental} {example.transition_feasibility_band}")
    print(f"  EC={example.evidence_confidence_raw_experimental} {example.evidence_confidence_band}")
    print(f"  Critic findings on this run: {len(run_findings)} ({len(blockers)} BLOCKER)")
    print(f"  Narrative summary: {example.narrative_structured['summary']}")
    print(f"  Review status: {review_row.status.value} by reviewer_id={review_row.reviewer_id}")
