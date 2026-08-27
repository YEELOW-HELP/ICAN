"""Schema smoke for the Stage 3B tables (Founder decisions E + F + M2).

Proves: the four-output columns exist and persist; the score-component
UNIQUE is (direction_id, output_family, component_key) so one claim can
feed multiple families; ProfileConstraint uses the 12-subtype field;
AI_TRACE persists call metadata idempotently and holds no content.
"""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.ai_gateway import GatewayTrace
from app.db.models_direction import (
    Direction,
    DirectionConstraintCheck,
    DirectionRun,
    DirectionRunStatus,
    DirectionScoreComponent,
    OutputFamily,
    ProfileConstraint,
    QualitativeBand,
    ScoreComponentStatus,
    ConstraintCheckResult,
)
from app.db.models_knowledge import KnowledgeBaseVersion, KnowledgeBaseVersionStatus
from app.db.models_platform import AITrace
from app.db.models_profile import PotentialProfile, ProfileClaim, ProfileDimension, ClaimStatus, ProfileGenerationStatus
from app.services.ai_trace import record_ai_trace
from app.services.direction.config import ensure_experimental_ranking_policy, ensure_experimental_scoring_config
from app.services.direction.versions import (
    CONSTRAINT_TAXONOMY_VERSION,
    DIMENSION_MAPPING_VERSION,
    DIRECTION_ENGINE_VERSION,
    DIRECTION_EVALUATION_MODEL_VERSION,
    EVIDENCE_STANDARD_VERSION,
    METHODOLOGY_VERSION,
    RANKING_POLICY_VERSION,
    SUBDIMENSION_TAXONOMY_VERSION,
)
from tests.profile_test_helpers import make_user


async def _seed_run(session):
    user = await make_user(session)
    kb = KnowledgeBaseVersion(version=1, status=KnowledgeBaseVersionStatus.PUBLISHED, is_current=True)
    session.add(kb)
    profile = PotentialProfile(
        user_id=user.id, session_id=uuid.uuid4(), version=1, status=ProfileGenerationStatus.READY,
        is_current=True, methodology_version="x", prompt_version="y",
    )
    session.add(profile)
    await session.flush()
    cfg = await ensure_experimental_scoring_config(session)
    policy = await ensure_experimental_ranking_policy(session)

    run = DirectionRun(
        user_id=user.id, profile_id=profile.id, knowledge_base_version_id=kb.id,
        scoring_config_id=cfg.id, ranking_policy_id=policy.id, version=1,
        status=DirectionRunStatus.READY, is_current=True,
        methodology_version=METHODOLOGY_VERSION,
        direction_engine_version=DIRECTION_ENGINE_VERSION,
        direction_evaluation_model_version=DIRECTION_EVALUATION_MODEL_VERSION,
        ranking_policy_version=RANKING_POLICY_VERSION,
        dimension_mapping_version=DIMENSION_MAPPING_VERSION,
        subdimension_taxonomy_version=SUBDIMENSION_TAXONOMY_VERSION,
        constraint_taxonomy_version=CONSTRAINT_TAXONOMY_VERSION,
        evidence_standard_version=EVIDENCE_STANDARD_VERSION,
    )
    session.add(run)
    await session.flush()
    return user, profile, kb, run


async def test_direction_persists_four_independent_outputs(session_factory):
    async with session_factory() as session:
        _, _, kb, run = await _seed_run(session)
        career_id = uuid.uuid4()  # no FK enforcement needed for this smoke (sqlite: FKs off by default)

        d = Direction(
            run_id=run.id, career_id=career_id, career_code="software_developer", domain="technology",
            potential_fit_raw_experimental=0.82, potential_fit_band=QualitativeBand.HIGH,
            potential_fit_coverage_ratio=0.43, potential_fit_scored_component_count=3,
            goal_alignment_raw_experimental=None, goal_alignment_band=None,
            goal_alignment_coverage_ratio=0.0, goal_alignment_scored_component_count=0,
            transition_feasibility_raw_experimental=0.5, transition_feasibility_band=QualitativeBand.MEDIUM,
            transition_feasibility_coverage_ratio=0.2, transition_feasibility_scored_component_count=1,
            evidence_confidence_raw_experimental=0.71, evidence_confidence_band=QualitativeBand.HIGH,
            skills_to_verify=["docker", "kubernetes"],
        )
        session.add(d)
        await session.commit()
        await session.refresh(d)

        assert d.potential_fit_band is QualitativeBand.HIGH
        assert d.goal_alignment_band is None  # unknown, stored as NULL -- not LOW
        assert d.transition_feasibility_band is QualitativeBand.MEDIUM
        assert d.evidence_confidence_band is QualitativeBand.HIGH
        assert d.skills_to_verify == ["docker", "kubernetes"]


async def test_one_claim_can_feed_multiple_output_families(session_factory):
    async with session_factory() as session:
        _, _, _, run = await _seed_run(session)
        d = Direction(run_id=run.id, career_id=uuid.uuid4(), career_code="c", domain="technology")
        session.add(d)
        await session.flush()

        session.add(
            DirectionScoreComponent(
                direction_id=d.id, output_family=OutputFamily.POTENTIAL_FIT, component_key="pf_skills_match",
                status=ScoreComponentStatus.SCORED, raw_score=0.7, rationale="match",
            )
        )
        session.add(
            DirectionScoreComponent(
                direction_id=d.id, output_family=OutputFamily.TRANSITION_FEASIBILITY, component_key="tf_skill_gap",
                status=ScoreComponentStatus.SCORED, raw_score=0.9, rationale="gap",
            )
        )
        await session.commit()  # same skill data, two families -- allowed

        # but the same (direction, family, component_key) twice is not
        session.add(
            DirectionScoreComponent(
                direction_id=d.id, output_family=OutputFamily.POTENTIAL_FIT, component_key="pf_skills_match",
                status=ScoreComponentStatus.SCORED, raw_score=0.1, rationale="dup",
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()


async def test_profile_constraint_uses_twelve_subtype_field(session_factory):
    async with session_factory() as session:
        _, profile, _, _ = await _seed_run(session)
        claim = ProfileClaim(
            profile_id=profile.id, dimension=ProfileDimension.CONSTRAINT, label="l",
            normalized_value="cannot relocate", confidence=0.8, status=ClaimStatus.SUPPORTED, generated_by="t",
        )
        session.add(claim)
        await session.flush()
        pc = ProfileConstraint(
            profile_id=profile.id, source_claim_id=claim.id, constraint_subtype="geography",
            constraint_taxonomy_version=CONSTRAINT_TAXONOMY_VERSION, normalized_value="cannot relocate",
            is_hard=False, is_confirmed=False, confidence=0.8,
        )
        session.add(pc)
        await session.commit()
        await session.refresh(pc)
        assert pc.constraint_subtype == "geography"
        assert pc.is_hard is False


async def test_constraint_check_row_persists(session_factory):
    async with session_factory() as session:
        _, _, _, run = await _seed_run(session)
        d = Direction(run_id=run.id, career_id=uuid.uuid4(), career_code="c", domain="x")
        session.add(d)
        await session.flush()
        session.add(
            DirectionConstraintCheck(
                direction_id=d.id, constraint_subtype="credential", result=ConstraintCheckResult.INSUFFICIENT_DATA,
                is_hard=True, explanation="no HARD_FACTUAL requirement",
            )
        )
        await session.commit()


async def test_ai_trace_persists_metadata_only_and_is_idempotent(session_factory):
    async with session_factory() as session:
        trace = GatewayTrace(
            trace_id="trace-abc", task_name="direction_narrative", provider="anthropic", model="claude-sonnet-5",
            prompt_version="direction-narrative-v0.1", input_tokens=100, output_tokens=50, latency_ms=1234.5,
            estimated_cost_usd=0.001, retry_count=0, stop_reason="end_turn",
        )
        row = await record_ai_trace(session, trace=trace, status="ok")
        assert isinstance(row, AITrace)
        assert row.task == "direction_narrative"
        assert row.input_tokens == 100
        # no content fields exist on the model at all
        assert not any(c.name in ("prompt", "messages", "content", "system") for c in AITrace.__table__.columns)

        dup = await record_ai_trace(session, trace=trace, status="ok")
        assert dup is None  # idempotent by trace_id
