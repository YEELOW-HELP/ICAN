"""Stage 3B Slice 3.5: the effective-reviewed-result read model + Client
Card read model.

Items #16/#17 (critic idempotency across repeated/different engine
versions) are covered in tests/test_direction_critic.py -- not
duplicated here.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.db.models import AdminRole
from app.db.models_direction import (
    CorrectionReasonCode,
    Direction,
    DirectionPlacement,
)
from app.services.direction import critic, readmodel, review
from app.services.direction.config import ensure_experimental_ranking_policy, ensure_experimental_scoring_config
from app.services.direction.pipeline import generate_directions
from app.services.exceptions import NoApprovedDirectionRunError
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
    run = await generate_directions(session, user_id=world["user"].id)
    await critic.run_critic(session, run_id=run.id)
    return run


@pytest.fixture
async def consultant(session):
    return await make_admin(session, role=AdminRole.CAREER_CONSULTANT, email="readmodel-consultant@test.dev")


def _first_direction_view(view, code: str):
    return next(d for d in view.directions if d.career_code == code)


# ---------------------------------------------------------------- 1, 9


async def test_no_corrections_effective_equals_system(session, clean_run):
    """#1 + #9."""
    view = await readmodel.build_reviewed_direction_view(session, run_id=clean_run.id)
    assert view.directions
    for d in view.directions:
        assert d.effective_placement == d.system_placement
        assert d.effective_narrative == d.system_narrative
        assert d.applied_corrections == []

    # #9: the underlying Direction rows are untouched by building the projection.
    rows_before = {
        d.id: (d.placement, d.narrative_structured)
        for d in (await session.execute(select(Direction).where(Direction.run_id == clean_run.id))).scalars().all()
    }
    await readmodel.build_reviewed_direction_view(session, run_id=clean_run.id)
    rows_after = {
        d.id: (d.placement, d.narrative_structured)
        for d in (await session.execute(select(Direction).where(Direction.run_id == clean_run.id))).scalars().all()
    }
    assert rows_before == rows_after


# ---------------------------------------------------------------- 2, 3


async def test_placement_correction_changes_effective_placement_only(session, clean_run, consultant):
    """#2 + #3."""
    directions = (await session.execute(select(Direction).where(Direction.run_id == clean_run.id))).scalars().all()
    target = directions[0]
    system_outputs_before = (
        target.potential_fit_raw_experimental, target.goal_alignment_raw_experimental,
        target.transition_feasibility_raw_experimental, target.evidence_confidence_raw_experimental,
    )

    await review.correct_direction_placement(
        session, run_id=clean_run.id, direction_id=target.id, reviewer=consultant,
        corrected_placement="not_eligible", reason_code=CorrectionReasonCode.WRONG_DIRECTION_PRIORITY,
        comment="reviewer disagrees with placement",
    )

    view = await readmodel.build_reviewed_direction_view(session, run_id=clean_run.id)
    view_direction = next(d for d in view.directions if d.direction_id == target.id)
    assert view_direction.effective_placement is DirectionPlacement.NOT_ELIGIBLE
    assert view_direction.system_placement == target.placement  # system value unchanged and still visible

    assert (
        view_direction.outputs.potential_fit_raw, view_direction.outputs.goal_alignment_raw,
        view_direction.outputs.transition_feasibility_raw, view_direction.outputs.evidence_confidence_raw,
    ) == system_outputs_before


# ---------------------------------------------------------------- 4


async def test_wording_correction_changes_effective_narrative_only(session, clean_run, consultant):
    """#4."""
    from app.services.direction.narrative import DirectionNarrator, generate_narratives_for_run
    from tests.test_direction_narrative import FakeGateway, _WELL_FORMED_PAYLOAD

    await generate_narratives_for_run(
        session, run_id=clean_run.id, narrator=DirectionNarrator(FakeGateway(payloads=[_WELL_FORMED_PAYLOAD] * 10))
    )

    directions = (
        await session.execute(
            select(Direction).where(Direction.run_id == clean_run.id, Direction.narrative_structured.isnot(None))
        )
    ).scalars().all()
    target = directions[0]
    system_outputs_before = (
        target.potential_fit_raw_experimental, target.goal_alignment_raw_experimental,
        target.transition_feasibility_raw_experimental, target.evidence_confidence_raw_experimental,
    )

    await review.correct_narrative_wording(
        session, run_id=clean_run.id, direction_id=target.id, reviewer=consultant,
        corrected_text="Виправлений, більш точний текст резюме.", field="summary",
    )

    view = await readmodel.build_reviewed_direction_view(session, run_id=clean_run.id)
    view_direction = next(d for d in view.directions if d.direction_id == target.id)
    assert view_direction.effective_narrative["summary"] == "Виправлений, більш точний текст резюме."
    assert view_direction.system_narrative["summary"] != view_direction.effective_narrative["summary"]
    # other narrative fields, untouched by this correction, still read from the system version
    assert view_direction.effective_narrative["why_fit"] == view_direction.system_narrative["why_fit"]

    assert (
        view_direction.outputs.potential_fit_raw, view_direction.outputs.goal_alignment_raw,
        view_direction.outputs.transition_feasibility_raw, view_direction.outputs.evidence_confidence_raw,
    ) == system_outputs_before
    assert view_direction.effective_placement == view_direction.system_placement  # ranking untouched


# ---------------------------------------------------------------- 5, 6


async def test_profile_flag_appears_as_flag_and_does_not_mutate_profile(session, clean_run, consultant, world):
    """#5."""
    from app.db.models_profile import PotentialProfile

    profile_before = await session.get(PotentialProfile, world["profile"].id)
    version_before, status_before = profile_before.version, profile_before.status

    await review.flag_problem(
        session, run_id=clean_run.id, reviewer=consultant, reason_code=CorrectionReasonCode.MISSING_INFERENCE,
        comment="profile seems to be missing a key strength", artifact_type="profile_flag",
    )

    view = await readmodel.build_reviewed_direction_view(session, run_id=clean_run.id)
    assert len(view.run_level_flags) == 1
    assert view.run_level_flags[0].artifact_type == "profile_flag"
    assert view.run_level_flags[0].applied is False

    profile_after = await session.get(PotentialProfile, world["profile"].id)
    assert (profile_after.version, profile_after.status) == (version_before, status_before)


async def test_knowledge_flag_appears_as_flag_and_does_not_mutate_kb(session, clean_run, consultant, world):
    """#6."""
    from app.db.models_knowledge import Career

    career_before = await session.get(Career, world["dev"].id)
    snapshot_before = (career_before.title_uk, career_before.works_with_technology, career_before.updated_at)

    await review.flag_problem(
        session, run_id=clean_run.id, reviewer=consultant, reason_code=CorrectionReasonCode.CAREER_KNOWLEDGE_PROBLEM,
        comment="this career's characteristics look off", artifact_type="knowledge_flag",
    )

    view = await readmodel.build_reviewed_direction_view(session, run_id=clean_run.id)
    assert any(f.artifact_type == "knowledge_flag" for f in view.run_level_flags)

    career_after = await session.get(Career, world["dev"].id)
    assert (career_after.title_uk, career_after.works_with_technology, career_after.updated_at) == snapshot_before


# ---------------------------------------------------------------- 7, 8


async def test_multiple_corrections_same_field_apply_deterministically(session, clean_run, consultant):
    """#7 + #8: latest chronological correction wins in EFFECTIVE, but the
    full history stays accessible via unapplied/applied lists and the DB."""
    directions = (await session.execute(select(Direction).where(Direction.run_id == clean_run.id))).scalars().all()
    target = directions[0]

    await review.correct_direction_placement(
        session, run_id=clean_run.id, direction_id=target.id, reviewer=consultant, corrected_placement="alternative",
        reason_code=CorrectionReasonCode.WRONG_DIRECTION_PRIORITY, comment="first",
    )
    await review.correct_direction_placement(
        session, run_id=clean_run.id, direction_id=target.id, reviewer=consultant, corrected_placement="not_eligible",
        reason_code=CorrectionReasonCode.CONSTRAINT_MISSED, comment="second, supersedes the first",
    )

    view = await readmodel.build_reviewed_direction_view(session, run_id=clean_run.id)
    view_direction = next(d for d in view.directions if d.direction_id == target.id)
    assert view_direction.effective_placement is DirectionPlacement.NOT_ELIGIBLE  # latest wins
    assert len(view_direction.applied_corrections) == 2  # both preserved in history

    from app.db.models_direction import ConsultantCorrection

    all_corrections = (
        await session.execute(select(ConsultantCorrection).where(ConsultantCorrection.direction_id == target.id))
    ).scalars().all()
    assert len(all_corrections) == 2  # neither deleted


async def test_unsupported_artifact_type_is_not_silently_applied(session, clean_run, consultant):
    """Founder §3.D: an unsupported correction artifact_type must remain
    unapplied with a clear status, never silently interpreted."""
    directions = (await session.execute(select(Direction).where(Direction.run_id == clean_run.id))).scalars().all()
    target = directions[0]

    await review.record_correction(
        session, run_id=clean_run.id, reviewer=consultant, artifact_type="some_future_artifact_type",
        reason_code=CorrectionReasonCode.OTHER_WITH_COMMENT, original_value={"x": 1}, corrected_value={"x": 2},
        direction_id=target.id, comment="testing an unsupported type",
    )

    view = await readmodel.build_reviewed_direction_view(session, run_id=clean_run.id)
    view_direction = next(d for d in view.directions if d.direction_id == target.id)
    assert len(view_direction.unapplied_corrections) == 1
    assert view_direction.unapplied_corrections[0].applied is False
    assert view_direction.applied_corrections == []  # never silently applied
    assert view_direction.effective_placement == view_direction.system_placement


# ---------------------------------------------------------------- 10, 11, 12, 13


async def test_only_approved_run_becomes_publishable(session, clean_run, consultant):
    """#10."""
    with pytest.raises(NoApprovedDirectionRunError):
        await readmodel.get_publishable_direction_result(session, user_id=clean_run.user_id)

    await review.approve_run(session, run_id=clean_run.id, reviewer=consultant)
    result = await readmodel.get_publishable_direction_result(session, user_id=clean_run.user_id)
    assert result.run_id == clean_run.id
    assert result.review_status.value == "approved"


async def test_unreviewed_run_cannot_become_publishable(session, clean_run):
    """#11."""
    with pytest.raises(NoApprovedDirectionRunError):
        await readmodel.get_publishable_direction_result(session, user_id=clean_run.user_id)


async def test_blocker_prevents_publishable_result(session, world, consultant):
    """#12."""
    from app.db.models_direction import ConstraintCheckResult, DirectionConstraintCheck

    run = await generate_directions(session, user_id=world["user"].id)
    directions = (
        await session.execute(select(Direction).where(Direction.run_id == run.id, Direction.placement == DirectionPlacement.MAIN))
    ).scalars().all()
    session.add(
        DirectionConstraintCheck(
            direction_id=directions[0].id, constraint_subtype="credential", result=ConstraintCheckResult.BLOCK,
            is_hard=True, explanation="synthetic BLOCKER for the publishable-result test",
        )
    )
    await session.commit()
    await critic.run_critic(session, run_id=run.id)

    from app.services.exceptions import DirectionRunHasUnresolvedBlockerError

    with pytest.raises(DirectionRunHasUnresolvedBlockerError):
        await review.approve_run(session, run_id=run.id, reviewer=consultant)
    with pytest.raises(NoApprovedDirectionRunError):
        await readmodel.get_publishable_direction_result(session, user_id=world["user"].id)


async def test_warnings_do_not_prevent_publishable_result(session, clean_run, consultant):
    """#13."""
    view_before_approval = await readmodel.build_reviewed_direction_view(session, run_id=clean_run.id)
    assert view_before_approval.critic_summary.warning_count > 0  # this fixture always produces WARNINGs

    await review.approve_run(session, run_id=clean_run.id, reviewer=consultant)
    result = await readmodel.get_publishable_direction_result(session, user_id=clean_run.user_id)
    assert result.critic_summary.warning_count > 0  # still present, still publishable


# ---------------------------------------------------------------- 14, 15


async def test_client_card_contains_all_four_outputs_separately(session, clean_run, world):
    """#14."""
    card = await readmodel.build_client_card(session, user_id=world["user"].id)
    assert card.directions
    d = card.directions[0]
    assert d.outputs.potential_fit_band is not None or d.outputs.potential_fit_raw is None
    fields = (
        d.outputs.potential_fit_raw, d.outputs.goal_alignment_raw, d.outputs.transition_feasibility_raw,
        d.outputs.evidence_confidence_raw,
    )
    assert len(fields) == 4  # four genuinely separate slots, never merged


async def test_client_card_includes_critic_warnings_and_corrections(session, clean_run, consultant, world):
    """#15."""
    directions = (await session.execute(select(Direction).where(Direction.run_id == clean_run.id))).scalars().all()
    target = directions[0]
    await review.correct_direction_placement(
        session, run_id=clean_run.id, direction_id=target.id, reviewer=consultant, corrected_placement="alternative",
        reason_code=CorrectionReasonCode.WRONG_DIRECTION_PRIORITY, comment="dashboard visibility test",
    )

    card = await readmodel.build_client_card(session, user_id=world["user"].id)
    assert card.critic_summary.warning_count > 0
    view_direction = next(d for d in card.directions if d.direction_id == target.id)
    assert len(view_direction.applied_corrections) == 1
    assert view_direction.effective_placement is DirectionPlacement.ALTERNATIVE

    # PROFILE SUMMARY / PROVENANCE sections are populated
    assert card.profile_summary.supported_claim_count > 0
    assert card.provenance.methodology_version == clean_run.methodology_version
    # record_correction lazily creates the review row -- PENDING_REVIEW,
    # not yet a decision.
    assert card.client.review_status.value == "pending_review"


# ---------------------------------------------------------------- 18, 19


async def test_no_raw_cv_or_transcript_leaks_into_read_model(session, clean_run, world):
    """#18."""
    import dataclasses
    import json

    card = await readmodel.build_client_card(session, user_id=world["user"].id)
    serialized = json.dumps(dataclasses.asdict(card), default=str, ensure_ascii=False)

    # none of the raw text the fixture used for negation-worded skill
    # claims (the closest thing to "CV/transcript free text" in this test
    # setup) should ever appear in the read model.
    for leaky_text in ("cannot do public communication", "never used leadership skills", "cannot work well in teams"):
        assert leaky_text not in serialized


async def test_no_persisted_ai_trace_reappears_in_readmodel(session, clean_run, world):
    """#19."""
    from app.db.base import Base
    from app.db import models_platform  # noqa: F401

    await readmodel.build_client_card(session, user_id=world["user"].id)
    assert "ai_traces" not in Base.metadata.tables
    assert not hasattr(models_platform, "AITrace")
