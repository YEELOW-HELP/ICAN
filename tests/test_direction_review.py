"""Stage 3B Slice 3 §4/§5/§6/§7: consultant review state machine,
append-only corrections, and the approval gate."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.db.models import AdminRole
from app.db.models_direction import (
    ConsultantCorrection,
    CorrectionReasonCode,
    DirectionPlacement,
    DirectionReview,
    DirectionRun,
    ReviewStatus,
)
from app.services.direction import critic, review
from app.services.direction.config import ensure_experimental_ranking_policy, ensure_experimental_scoring_config
from app.services.direction.pipeline import generate_directions
from app.services.exceptions import (
    DirectionRunHasUnresolvedBlockerError,
    InsufficientRoleError,
    InvalidStateTransitionError,
    NoApprovedDirectionRunError,
)
from tests.direction_pipeline_test_helpers import make_user, seed_eligible_developer_profile, seed_knowledge_base
from tests.profile_test_helpers import make_admin


@pytest.fixture
async def world(session):
    await ensure_experimental_scoring_config(session)
    await ensure_experimental_ranking_policy(session)
    kb = await seed_knowledge_base(session)
    user = await make_user(session)
    prof = await seed_eligible_developer_profile(session, user=user)
    return dict(**kb, **prof, user=user)


@pytest.fixture
async def clean_run(session, world):
    """A real, generated, critic-passed run with zero BLOCKER findings."""
    run = await generate_directions(session, user_id=world["user"].id)
    await critic.run_critic(session, run_id=run.id)
    return run


# ---------------------------------------------------------------- 9, 11


async def test_clean_run_can_be_approved(session, clean_run):
    """#9."""
    consultant = await make_admin(session, role=AdminRole.CAREER_CONSULTANT, email="consultant1@test.dev")
    result = await review.approve_run(session, run_id=clean_run.id, reviewer=consultant, comment="looks good")
    assert result.status is ReviewStatus.APPROVED
    assert result.reviewer_id == consultant.id


async def test_career_consultant_can_approve(session, clean_run):
    """#11 (same assertion as #9, phrased around the role specifically)."""
    consultant = await make_admin(session, role=AdminRole.CAREER_CONSULTANT, email="consultant2@test.dev")
    result = await review.approve_run(session, run_id=clean_run.id, reviewer=consultant)
    assert result.status is ReviewStatus.APPROVED


# ---------------------------------------------------------------- 10


async def test_unauthorized_reviewer_cannot_approve(session, clean_run):
    """#10: a role outside REVIEW_ROLES is rejected."""
    unauthorized = await make_admin(session, role=AdminRole.MANAGER, email="manager1@test.dev")
    with pytest.raises(InsufficientRoleError):
        await review.approve_run(session, run_id=clean_run.id, reviewer=unauthorized)


# ---------------------------------------------------------------- 8


async def test_unresolved_blocker_prevents_approval(session, world):
    """#8."""
    from app.db.models_direction import ConstraintCheckResult, Direction, DirectionConstraintCheck, DirectionRunStatus

    run = await generate_directions(session, user_id=world["user"].id)
    # Inject a synthetic BLOCKER-worthy inconsistency: a MAIN direction
    # with a confirmed hard BLOCK constraint check (should never happen
    # from the real pipeline -- this simulates the orchestrator bug the
    # Critic exists to catch).
    directions = (
        await session.execute(select(Direction).where(Direction.run_id == run.id, Direction.placement == DirectionPlacement.MAIN))
    ).scalars().all()
    assert directions, "fixture must produce at least one MAIN direction"
    session.add(
        DirectionConstraintCheck(
            direction_id=directions[0].id, constraint_subtype="credential", result=ConstraintCheckResult.BLOCK,
            is_hard=True, explanation="synthetic BLOCKER for the approval-gate test",
        )
    )
    await session.commit()

    await critic.run_critic(session, run_id=run.id)
    consultant = await make_admin(session, role=AdminRole.CAREER_CONSULTANT, email="consultant3@test.dev")
    with pytest.raises(DirectionRunHasUnresolvedBlockerError):
        await review.approve_run(session, run_id=run.id, reviewer=consultant)


# ---------------------------------------------------------------- 12, 13, 14


async def test_correction_preserves_original_direction(session, clean_run):
    """#12: correcting a Direction's placement never mutates the
    Direction row itself."""
    from app.db.models_direction import Direction

    consultant = await make_admin(session, role=AdminRole.CAREER_CONSULTANT, email="consultant4@test.dev")
    directions = (await session.execute(select(Direction).where(Direction.run_id == clean_run.id))).scalars().all()
    target = directions[0]
    original_placement = target.placement

    await review.correct_direction_placement(
        session, run_id=clean_run.id, direction_id=target.id, reviewer=consultant,
        corrected_placement="alternative", reason_code=CorrectionReasonCode.WRONG_DIRECTION_PRIORITY,
        comment="should be alternative instead",
    )

    await session.refresh(target)
    assert target.placement == original_placement  # untouched


async def test_correction_is_append_only(session, clean_run):
    """#13: two corrections on the same direction both persist -- neither
    overwrites the other."""
    from app.db.models_direction import Direction

    consultant = await make_admin(session, role=AdminRole.CAREER_CONSULTANT, email="consultant5@test.dev")
    directions = (await session.execute(select(Direction).where(Direction.run_id == clean_run.id))).scalars().all()
    target = directions[0]

    c1 = await review.correct_direction_placement(
        session, run_id=clean_run.id, direction_id=target.id, reviewer=consultant, corrected_placement="alternative",
        reason_code=CorrectionReasonCode.WRONG_DIRECTION_PRIORITY, comment="first correction",
    )
    c2 = await review.correct_direction_placement(
        session, run_id=clean_run.id, direction_id=target.id, reviewer=consultant, corrected_placement="blocked",
        reason_code=CorrectionReasonCode.CONSTRAINT_MISSED, comment="second correction, supersedes the first",
    )
    assert c1.id != c2.id
    rows = (
        await session.execute(select(ConsultantCorrection).where(ConsultantCorrection.direction_id == target.id))
    ).scalars().all()
    assert len(rows) == 2  # both preserved, neither deleted/overwritten


async def test_all_approved_correction_reason_codes_accepted(session, clean_run):
    """#14."""
    consultant = await make_admin(session, role=AdminRole.CAREER_CONSULTANT, email="consultant6@test.dev")
    for code in CorrectionReasonCode:
        correction = await review.flag_problem(
            session, run_id=clean_run.id, reviewer=consultant, reason_code=code, comment=f"testing {code.value}",
        )
        assert correction.reason_code is code


async def test_correction_denormalizes_provenance_versions(session, clean_run):
    consultant = await make_admin(session, role=AdminRole.CAREER_CONSULTANT, email="consultant7@test.dev")
    correction = await review.flag_problem(
        session, run_id=clean_run.id, reviewer=consultant, reason_code=CorrectionReasonCode.CAREER_KNOWLEDGE_PROBLEM,
        comment="KB seems off for this career", artifact_type="knowledge_flag",
    )
    assert correction.methodology_version == clean_run.methodology_version
    assert correction.knowledge_base_version_id == clean_run.knowledge_base_version_id
    assert correction.direction_engine_version == clean_run.direction_engine_version
    assert correction.scoring_config_version == 1
    assert correction.ranking_policy_version == 1


# ---------------------------------------------------------------- 15, 16, 17


async def test_request_changes_does_not_mutate_old_run(session, clean_run):
    """#15."""
    consultant = await make_admin(session, role=AdminRole.CAREER_CONSULTANT, email="consultant8@test.dev")
    original_status = clean_run.status
    original_directions_count = len(
        (await session.execute(select(DirectionRun).where(DirectionRun.id == clean_run.id))).scalars().all()
    )

    result = await review.request_changes(session, run_id=clean_run.id, reviewer=consultant, comment="please redo the constraint handling")
    assert result.status is ReviewStatus.CHANGES_REQUESTED

    await session.refresh(clean_run)
    assert clean_run.status == original_status  # DirectionRun itself untouched
    assert clean_run.is_current is True  # still the current run -- request_changes never demotes it


async def test_regeneration_creates_new_direction_run_and_version(session, world, clean_run):
    """#16."""
    consultant = await make_admin(session, role=AdminRole.CAREER_CONSULTANT, email="consultant9@test.dev")
    await review.request_changes(session, run_id=clean_run.id, reviewer=consultant, comment="redo")

    new_run = await generate_directions(session, user_id=world["user"].id)
    assert new_run.id != clean_run.id
    assert new_run.version == clean_run.version + 1
    assert new_run.is_current is True

    await session.refresh(clean_run)
    assert clean_run.is_current is False  # superseded by the new run, not mutated


async def test_previous_review_remains_attached_to_old_run(session, world, clean_run):
    """#17."""
    consultant = await make_admin(session, role=AdminRole.CAREER_CONSULTANT, email="consultant10@test.dev")
    old_review = await review.request_changes(session, run_id=clean_run.id, reviewer=consultant, comment="redo")

    new_run = await generate_directions(session, user_id=world["user"].id)
    await critic.run_critic(session, run_id=new_run.id)

    await session.refresh(old_review)
    assert old_review.run_id == clean_run.id  # still bound to the OLD run
    assert old_review.status is ReviewStatus.CHANGES_REQUESTED  # untouched by the new run's existence

    new_review = (
        await session.execute(select(DirectionReview).where(DirectionReview.run_id == new_run.id))
    ).scalar_one_or_none()
    assert new_review is None  # a fresh review only gets created on the first consultant action for the new run


# ---------------------------------------------------------------- 18


async def test_get_approved_direction_run_returns_only_approved_version(session, world, clean_run):
    """#18."""
    with pytest.raises(NoApprovedDirectionRunError):
        await review.get_approved_direction_run(session, user_id=world["user"].id)

    consultant = await make_admin(session, role=AdminRole.CAREER_CONSULTANT, email="consultant11@test.dev")
    await review.approve_run(session, run_id=clean_run.id, reviewer=consultant)

    approved = await review.get_approved_direction_run(session, user_id=world["user"].id)
    assert approved.id == clean_run.id


async def test_get_approved_direction_run_rejects_a_changes_requested_run(session, world, clean_run):
    consultant = await make_admin(session, role=AdminRole.CAREER_CONSULTANT, email="consultant12@test.dev")
    await review.request_changes(session, run_id=clean_run.id, reviewer=consultant, comment="not ready")
    with pytest.raises(NoApprovedDirectionRunError):
        await review.get_approved_direction_run(session, user_id=world["user"].id)


async def test_review_state_machine_rejects_re_deciding_a_decided_review(session, clean_run):
    consultant = await make_admin(session, role=AdminRole.CAREER_CONSULTANT, email="consultant13@test.dev")
    await review.approve_run(session, run_id=clean_run.id, reviewer=consultant)
    with pytest.raises(InvalidStateTransitionError):
        await review.reject_run(session, run_id=clean_run.id, reviewer=consultant, comment="changed my mind")
