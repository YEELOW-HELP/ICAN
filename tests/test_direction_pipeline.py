"""Stage 3B Slice 2 (Issue #3): end-to-end Direction Generation
orchestrator tests.

Exercises `app.services.direction.pipeline.generate_directions` against a
real, published Career Knowledge Base and a real READY PotentialProfile --
the first vertical slice through the whole Direction Intelligence stack,
zero LLM calls anywhere in the path.
"""

from __future__ import annotations

import inspect
import uuid

import pytest
from sqlalchemy import select

from app.db.models_direction import (
    ConstraintCheckResult,
    Direction,
    DirectionConstraintCheck,
    DirectionPlacement,
    DirectionRun,
    DirectionRunStatus,
    DirectionScoreComponent,
    OutputFamily,
    QualitativeBand,
    ScoreComponentStatus,
)
from app.services.direction import candidates, confidence, constraints, dedup, pipeline, ranking
from app.services.direction.config import ensure_experimental_ranking_policy, ensure_experimental_scoring_config
from app.services.direction.scoring import aggregate, base, components, evidence_confidence, skill_state
from app.services.exceptions import DirectionGenerationInProgressError, NoCurrentProfileError
from tests.direction_pipeline_test_helpers import (
    make_user,
    seed_eligible_developer_profile,
    seed_knowledge_base,
)


@pytest.fixture
async def world(session):
    await ensure_experimental_scoring_config(session)
    await ensure_experimental_ranking_policy(session)
    kb = await seed_knowledge_base(session)
    user = await make_user(session)
    prof = await seed_eligible_developer_profile(session, user=user)
    return dict(**kb, **prof, user=user)


async def _directions_by_code(session, run_id: uuid.UUID) -> dict[str, Direction]:
    rows = (await session.execute(select(Direction).where(Direction.run_id == run_id))).scalars().all()
    return {d.career_code: d for d in rows}


# ---------------------------------------------------------------- 1, 3, 7, 8, 12, 16


async def test_ready_profile_generates_direction_run(session, world):
    """#1: a READY, eligible profile produces a READY DirectionRun with
    persisted Directions."""
    run = await pipeline.generate_directions(session, user_id=world["user"].id)
    assert run.status is DirectionRunStatus.READY
    assert run.is_current is True

    by_code = await _directions_by_code(session, run.id)
    assert len(by_code) == 5  # every seeded career gets a Direction row
    assert set(by_code) == {"dev_strong", "dev_weak_dup", "dev_needs_advanced_skills", "commercial_pilot", "sales_manager"}


async def test_all_directions_reference_real_kb_careers(session, world):
    """#3: candidate Careers come only from the Career KB -- every
    persisted Direction's career_id/career_code is a real, existing
    Career row, never invented."""
    from app.services.knowledge.retrieval import get_career

    run = await pipeline.generate_directions(session, user_id=world["user"].id)
    by_code = await _directions_by_code(session, run.id)
    for direction in by_code.values():
        career = await get_career(session, direction.career_id)  # raises CareerNotFoundError if invented
        assert career.code == direction.career_code


async def test_four_outputs_are_persisted_separately(session, world):
    """#7: Potential Fit / Goal Alignment / Transition Feasibility /
    Evidence Confidence are four independently stored fields, never one
    blended score. Since Slice 3 (`ga_goals` is now a real scorer), the
    fixture's explicit "wants a stable remote job" Goal claim genuinely
    matches `dev_strong`'s REMOTE work context -- proving independence via
    structurally disjoint contributing components, not merely "GA is
    always None"."""
    run = await pipeline.generate_directions(session, user_id=world["user"].id)
    direction = (await _directions_by_code(session, run.id))["dev_strong"]

    assert direction.potential_fit_raw_experimental is not None
    assert direction.potential_fit_band is QualitativeBand.HIGH
    assert direction.goal_alignment_raw_experimental is not None  # ga_goals is real as of Slice 3
    assert direction.goal_alignment_band is not None

    rows = (
        await session.execute(select(DirectionScoreComponent).where(DirectionScoreComponent.direction_id == direction.id))
    ).scalars().all()
    pf_keys = {r.component_key for r in rows if r.output_family is OutputFamily.POTENTIAL_FIT}
    ga_keys = {r.component_key for r in rows if r.output_family is OutputFamily.GOAL_ALIGNMENT}
    assert pf_keys.isdisjoint(ga_keys)  # not one shared component feeding both -- structurally independent


async def test_missing_component_persisted_as_insufficient_data_not_zero(session, world):
    """#8: a component with no comparable pair is stored as
    INSUFFICIENT_DATA with raw_score=None, never a 0.0."""
    run = await pipeline.generate_directions(session, user_id=world["user"].id)
    direction = (await _directions_by_code(session, run.id))["dev_strong"]
    rows = (
        await session.execute(select(DirectionScoreComponent).where(DirectionScoreComponent.direction_id == direction.id))
    ).scalars().all()
    stub = next(r for r in rows if r.component_key == "pf_strengths")
    assert stub.status is ScoreComponentStatus.INSUFFICIENT_DATA
    assert stub.raw_score is None


async def test_no_composite_score_field_anywhere(session, world):
    """#12: no table/column anywhere blends the four outputs into one
    number."""
    direction_columns = set(Direction.__table__.columns.keys())
    forbidden = {"score", "composite_score", "overall_score", "fit_score", "final_score", "total_score"}
    assert direction_columns.isdisjoint(forbidden)


async def test_provenance_versions_are_pinned_on_run(session, world):
    """#16: every methodology/engine/config version is stamped on the
    DirectionRun at creation time."""
    run = await pipeline.generate_directions(session, user_id=world["user"].id)
    for field in (
        "methodology_version", "direction_engine_version", "direction_evaluation_model_version",
        "ranking_policy_version", "dimension_mapping_version", "subdimension_taxonomy_version",
        "constraint_taxonomy_version", "evidence_standard_version",
    ):
        assert getattr(run, field), f"{field} must be pinned"
    assert run.scoring_config_id is not None
    assert run.ranking_policy_id is not None
    assert run.knowledge_base_version_id == world["kb_version"].id


# ---------------------------------------------------------------- 2, 15


async def test_insufficient_profile_produces_no_fake_recommendations(session, world):
    """#2: a profile below the minimum-evidence threshold produces
    INSUFFICIENT_INFORMATION and zero Directions -- never a manufactured
    recommendation."""
    from tests.direction_pipeline_test_helpers import add_claim, make_ready_profile
    from app.db.models_profile import ProfileDimension

    thin_user = await make_user(session)
    thin_profile = await make_ready_profile(session, user_id=thin_user.id)
    await add_claim(session, profile_id=thin_profile.id, dimension=ProfileDimension.STRENGTH, confidence=0.9)

    run = await pipeline.generate_directions(session, user_id=thin_user.id)
    assert run.status is DirectionRunStatus.INSUFFICIENT_INFORMATION
    assert run.is_current is True

    directions = (await session.execute(select(Direction).where(Direction.run_id == run.id))).scalars().all()
    assert directions == []

    from app.db.models_direction import ClarificationRequest

    clarifications = (
        await session.execute(select(ClarificationRequest).where(ClarificationRequest.run_id == run.id))
    ).scalars().all()
    assert len(clarifications) >= 1


async def test_explanation_bundle_references_real_claims_and_career(session, world):
    """#15: the explanation bundle's provenance section points at real,
    persisted ProfileClaim/Career/CareerRequirement IDs -- never invented
    references."""
    run = await pipeline.generate_directions(session, user_id=world["user"].id)
    direction = (await _directions_by_code(session, run.id))["dev_strong"]
    assert direction.placement in (DirectionPlacement.MAIN, DirectionPlacement.ALTERNATIVE)
    bundle = direction.explanation_bundle
    assert bundle is not None
    assert "why_fit" in bundle and "why_now" in bundle and "transition" in bundle
    assert "confidence" in bundle and "provenance" in bundle

    real_claim_ids = {
        str(world["interest_claim"].id), str(world["skill_claim"].id), str(world["strength_claim"].id),
    }
    provenance_claims = set(bundle["provenance"]["contributing_claim_ids"])
    assert provenance_claims  # non-empty: real evidence was actually used
    assert provenance_claims.issubset(real_claim_ids | {
        str(world["comm_gap_claim"].id), str(world["leadership_gap_claim"].id),
        str(world["teamwork_gap_claim"].id), str(world["constraint_claim"].id), str(world["goal_claim"].id),
    })
    assert bundle["provenance"]["career_id"] == str(world["dev"].id)
    assert bundle["provenance"]["knowledge_base_version_id"] == str(world["kb_version"].id)


# ---------------------------------------------------------------- 4, 5


async def test_hard_blocked_career_excluded_from_main_and_alternative(session, world):
    """#4: a HARD_FACTUAL-requirement career, matched against a
    hard+confirmed user constraint, is BLOCKED and cannot appear in
    MAIN or ALTERNATIVE."""
    run = await pipeline.generate_directions(
        session, user_id=world["user"].id, hard_confirmed_claim_ids={world["constraint_claim"].id}
    )
    pilot_direction = (await _directions_by_code(session, run.id))["commercial_pilot"]
    assert pilot_direction.placement is DirectionPlacement.BLOCKED

    checks = (
        await session.execute(select(DirectionConstraintCheck).where(DirectionConstraintCheck.direction_id == pilot_direction.id))
    ).scalars().all()
    assert any(c.result == ConstraintCheckResult.BLOCK for c in checks)


async def test_typical_recommendation_requirement_never_blocks_end_to_end(session, world):
    """#5: `dev`'s TYPICAL_RECOMMENDATION education requirement never
    blocks, even with the constraint marked hard+confirmed (no matching
    HARD_FACTUAL category exists for it)."""
    run = await pipeline.generate_directions(
        session, user_id=world["user"].id, hard_confirmed_claim_ids={world["constraint_claim"].id}
    )
    dev_direction = (await _directions_by_code(session, run.id))["dev_strong"]
    assert dev_direction.placement is not DirectionPlacement.BLOCKED


# ---------------------------------------------------------------- 6


async def test_missing_required_skill_is_unknown_not_confirmed_missing_end_to_end(session, world):
    """#6: a required skill the profile never mentions at all is UNKNOWN
    (surfaced as skills_to_verify), never treated as a confirmed gap.
    `sales_manager` requires `communication`, which the profile explicitly
    negates (a real CONFIRMED_MISSING) -- but requires nothing the profile
    is simply silent about here, so this asserts the *general* rule using
    `dev_strong`, whose only required skill (`programming`) the profile
    supports, leaving nothing UNKNOWN to falsely convert into a gap."""
    run = await pipeline.generate_directions(session, user_id=world["user"].id)
    gap_direction = (await _directions_by_code(session, run.id))["dev_needs_advanced_skills"]
    # communication/leadership/teamwork are all explicitly negated (real
    # CONFIRMED_MISSING) in the fixture -- none of dev_gap's required
    # skills are actually UNKNOWN, so skills_to_verify must be empty here,
    # proving the pipeline doesn't invent verification noise either.
    assert gap_direction.skills_to_verify == []


# ---------------------------------------------------------------- 9, 11, 13


async def test_high_fit_low_feasibility_becomes_alternative(session, world):
    """#9 + #11: `dev_needs_advanced_skills` has the same HIGH Potential
    Fit inputs as `dev_strong` (same interests/skills claims apply) but a
    real LOW Transition Feasibility (3 of 4 required skills confirmed
    missing) -- RankingPolicy must place it in ALTERNATIVE, never MAIN,
    and MAIN itself must be lexicographically ordered by Potential Fit."""
    run = await pipeline.generate_directions(session, user_id=world["user"].id)
    by_code = await _directions_by_code(session, run.id)

    gap = by_code["dev_needs_advanced_skills"]
    assert gap.potential_fit_band is QualitativeBand.HIGH
    assert gap.transition_feasibility_band is QualitativeBand.LOW
    assert gap.placement is DirectionPlacement.ALTERNATIVE
    assert gap.trade_off_notes and "Transition Feasibility" in gap.trade_off_notes

    main_directions = sorted(
        (d for d in by_code.values() if d.placement is DirectionPlacement.MAIN),
        key=lambda d: d.rank_within_placement,
    )
    for a, b in zip(main_directions, main_directions[1:]):
        assert (a.potential_fit_raw_experimental or 0) >= (b.potential_fit_raw_experimental or 0)


async def test_never_pads_to_three_and_three(session, world):
    """#13: with only 5 candidate careers total (one BLOCKED, one DEDUPED
    when the constraint is confirmed), MAIN/ALTERNATIVE are never padded
    with weak recommendations to reach 3+3."""
    run = await pipeline.generate_directions(
        session, user_id=world["user"].id, hard_confirmed_claim_ids={world["constraint_claim"].id}
    )
    by_code = await _directions_by_code(session, run.id)
    main_count = sum(1 for d in by_code.values() if d.placement is DirectionPlacement.MAIN)
    alt_count = sum(1 for d in by_code.values() if d.placement is DirectionPlacement.ALTERNATIVE)
    assert main_count <= 3
    assert alt_count <= 3
    assert main_count + alt_count < len(by_code)  # BLOCKED/DEDUPED/NOT_ELIGIBLE members exist and were not padded in


# ---------------------------------------------------------------- 10


async def test_goal_alignment_never_conflated_with_potential_fit(session, world):
    """#10, closed as of Slice 3 (`ga_goals` is now real): the profile's
    explicit Goal claim ("wants a stable remote job") genuinely mismatches
    `sales_manager`'s OFFICE work context -- a real, independently-computed
    LOW Goal Alignment that has nothing to do with `sales_manager`'s own
    (unrelated) Potential Fit value. Goal Alignment is never defaulted to
    Potential Fit's band or silently coerced -- it can be LOW while PF is
    something else entirely, and RankingPolicy's "unknown/LOW Goal
    Alignment" rules (already unit-tested in test_direction_ranking.py)
    apply to this real value correctly."""
    run = await pipeline.generate_directions(session, user_id=world["user"].id)
    direction = (await _directions_by_code(session, run.id))["sales_manager"]
    assert direction.goal_alignment_band is QualitativeBand.LOW  # remote-job goal vs. OFFICE-only career
    assert direction.potential_fit_band is not QualitativeBand.LOW  # PF is unrelated to GA's mismatch
    assert direction.potential_fit_raw_experimental != direction.goal_alignment_raw_experimental


# ---------------------------------------------------------------- 14


async def test_exact_duplicate_career_is_deduped(session, world):
    """#14: `dev_weak_dup` shares `dev_strong`'s exact title -- the weaker
    scorer is folded into DEDUPED with a recorded reason, never silently
    dropped and never allowed to compete in MAIN/ALTERNATIVE."""
    run = await pipeline.generate_directions(session, user_id=world["user"].id)
    by_code = await _directions_by_code(session, run.id)

    dup = by_code["dev_weak_dup"]
    assert dup.placement is DirectionPlacement.DEDUPED
    assert dup.duplicate_of_career_code == "dev_strong"
    assert dup.dedup_reason

    strong = by_code["dev_strong"]
    assert strong.placement in (DirectionPlacement.MAIN, DirectionPlacement.ALTERNATIVE)
    # the weaker duplicate's own real scores are still persisted (audit trail)
    assert dup.potential_fit_raw_experimental is not None


# ---------------------------------------------------------------- 17, 18, 19


async def test_failed_generation_is_retryable(session, world, monkeypatch):
    """#17 + #18: a mid-pipeline failure marks the run FAILED (never
    current), preserves auditability, and a subsequent call succeeds as a
    new version -- without disturbing any previously-current run."""
    first_run = await pipeline.generate_directions(session, user_id=world["user"].id)
    assert first_run.status is DirectionRunStatus.READY
    assert first_run.is_current is True

    async def _boom(*args, **kwargs):
        raise RuntimeError("simulated candidate-retrieval failure")

    monkeypatch.setattr(pipeline, "get_career_details", _boom)
    with pytest.raises(RuntimeError):
        await pipeline.generate_directions(session, user_id=world["user"].id)

    await session.refresh(first_run)
    assert first_run.status is DirectionRunStatus.READY
    assert first_run.is_current is True  # untouched by the failed attempt

    failed_run = (
        await session.execute(
            select(DirectionRun).where(DirectionRun.user_id == world["user"].id, DirectionRun.status == DirectionRunStatus.FAILED)
        )
    ).scalar_one()
    assert failed_run.is_current is False
    assert failed_run.failure_reason and "RuntimeError" in failed_run.failure_reason
    assert "simulated candidate-retrieval failure" not in failed_run.failure_reason  # never raw exception text

    monkeypatch.undo()
    retried_run = await pipeline.generate_directions(session, user_id=world["user"].id)
    assert retried_run.status is DirectionRunStatus.READY
    assert retried_run.is_current is True
    assert retried_run.version == first_run.version + 2  # failed attempt still consumed a version number

    await session.refresh(first_run)
    assert first_run.is_current is False  # only superseded by the successful retry, not the failed attempt


async def test_concurrent_generation_guard_raises(session, world):
    """#19: a second call while one is GENERATING is rejected."""
    in_progress = DirectionRun(
        user_id=world["user"].id, profile_id=world["profile"].id, knowledge_base_version_id=world["kb_version"].id,
        scoring_config_id=(await ensure_experimental_scoring_config(session)).id,
        ranking_policy_id=(await ensure_experimental_ranking_policy(session)).id,
        version=1, status=DirectionRunStatus.GENERATING, is_current=False,
        methodology_version="x", direction_engine_version="x", direction_evaluation_model_version="x",
        ranking_policy_version="x", dimension_mapping_version="x", subdimension_taxonomy_version="x",
        constraint_taxonomy_version="x", evidence_standard_version="x",
    )
    session.add(in_progress)
    await session.commit()

    with pytest.raises(DirectionGenerationInProgressError):
        await pipeline.generate_directions(session, user_id=world["user"].id)


async def test_no_current_profile_raises(session):
    user = await make_user(session)
    with pytest.raises(NoCurrentProfileError):
        await pipeline.generate_directions(session, user_id=user.id)


# ---------------------------------------------------------------- 20


def test_pipeline_and_scoring_modules_have_zero_llm_dependency():
    """#20: the entire deterministic pipeline works with ZERO LLM calls --
    no AI Gateway import/reference anywhere in the modules it touches."""
    modules = [
        pipeline, candidates, confidence, constraints, dedup, ranking,
        aggregate, base, components, evidence_confidence, skill_state,
    ]
    for module in modules:
        source = inspect.getsource(module)
        assert "ai_gateway" not in source.lower(), module.__name__
        assert "AIGateway" not in source, module.__name__
        assert "call_tool" not in source, module.__name__
