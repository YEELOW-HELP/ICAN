"""Founder decisions F + O + G: versioned EXPERIMENTAL ScoringConfig and
the SEPARATE versioned RankingPolicy. Idempotent seeding, one ACTIVE row,
weights all-equal per family, ranking policy carries no composite score.
"""

import pytest

from app.db.models_direction import PolicyStatus
from app.services.direction.config import (
    ALL_COMPONENTS_BY_FAMILY,
    EXPERIMENTAL_NON_PRODUCTION_RANKING_POLICY_V1,
    EXPERIMENTAL_NON_PRODUCTION_SCORING_CONFIG_V1,
    ensure_experimental_ranking_policy,
    ensure_experimental_scoring_config,
    get_active_ranking_policy,
    get_active_scoring_config,
)
from app.services.exceptions import NoActiveRankingPolicyError, NoActiveScoringConfigError


async def test_scoring_config_seed_is_idempotent_and_active(session_factory):
    async with session_factory() as session:
        a = await ensure_experimental_scoring_config(session)
        b = await ensure_experimental_scoring_config(session)
        assert a.id == b.id
        assert a.status is PolicyStatus.ACTIVE
        assert a.is_experimental is True
        active = await get_active_scoring_config(session)
        assert active.id == a.id


async def test_ranking_policy_seed_is_idempotent_and_active(session_factory):
    async with session_factory() as session:
        a = await ensure_experimental_ranking_policy(session)
        b = await ensure_experimental_ranking_policy(session)
        assert a.id == b.id
        assert a.status is PolicyStatus.ACTIVE
        assert a.is_experimental is True


async def test_get_active_raises_when_unseeded(session_factory):
    async with session_factory() as session:
        with pytest.raises(NoActiveScoringConfigError):
            await get_active_scoring_config(session)
        with pytest.raises(NoActiveRankingPolicyError):
            await get_active_ranking_policy(session)


def test_v1_weights_are_all_equal_per_family():
    for family, weights in EXPERIMENTAL_NON_PRODUCTION_SCORING_CONFIG_V1["component_weights"].items():
        assert set(weights.values()) == {1.0}, family


def test_config_is_flagged_experimental_and_not_calibrated():
    assert EXPERIMENTAL_NON_PRODUCTION_SCORING_CONFIG_V1["is_experimental"] is True
    assert "not methodology-approved" in EXPERIMENTAL_NON_PRODUCTION_SCORING_CONFIG_V1["notes"].lower()
    assert EXPERIMENTAL_NON_PRODUCTION_RANKING_POLICY_V1["is_experimental"] is True


def test_ranking_policy_has_no_composite_or_blended_score_field():
    policy = EXPERIMENTAL_NON_PRODUCTION_RANKING_POLICY_V1["policy"]
    keys = str(policy).lower()
    for forbidden in ("composite", "blended", "weighted_sum", "overall_score", "career_score"):
        assert forbidden not in keys


def test_four_families_present_evidence_confidence_is_signals_not_weighted():
    assert set(ALL_COMPONENTS_BY_FAMILY) == {
        "potential_fit", "goal_alignment", "transition_feasibility", "evidence_confidence"
    }
    # evidence_confidence has no weights entry -- it is computed by a dedicated function, not a weighted mean
    assert "evidence_confidence" not in EXPERIMENTAL_NON_PRODUCTION_SCORING_CONFIG_V1["component_weights"]
