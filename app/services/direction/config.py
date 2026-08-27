"""Versioned configuration for the four-output Direction Evaluation engine
(Founder decisions D, F, H, N) and the SEPARATE RankingPolicy (decisions
O, G, A).

Every V1 `ScoringConfig` / `RankingPolicy` is `is_experimental=True`. The
weights and thresholds here are ENGINEERING PLACEHOLDERS for pipeline
validation -- NOT methodology-approved, never presented as validated. The
v0.1 weights are deliberately all-equal per output family: the honest
representation of "no validated weighting exists yet".

`RankingPolicy` never contains a blended/composite career score -- only
eligibility rules, band gates, lexicographic precedence, tie-breakers,
pool sizes, missing-output semantics (see MNP_RANKING_POLICY_V0.1.md).

Seeding is idempotent application-level `ensure_*` (the
`ensure_seed_taxonomy` precedent), not baked into the migration.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_direction import PolicyStatus, RankingPolicy, ScoringConfig
from app.services.direction.versions import (
    METHODOLOGY_VERSION,
    RANKING_POLICY_VERSION,
)
from app.services.exceptions import NoActiveRankingPolicyError, NoActiveScoringConfigError

__all__ = [
    "POTENTIAL_FIT_COMPONENTS",
    "GOAL_ALIGNMENT_COMPONENTS",
    "TRANSITION_FEASIBILITY_COMPONENTS",
    "EVIDENCE_CONFIDENCE_SIGNALS",
    "ALL_COMPONENTS_BY_FAMILY",
    "EXPERIMENTAL_NON_PRODUCTION_SCORING_CONFIG_V1",
    "EXPERIMENTAL_NON_PRODUCTION_RANKING_POLICY_V1",
    "ensure_experimental_scoring_config",
    "ensure_experimental_ranking_policy",
    "get_active_scoring_config",
    "get_active_ranking_policy",
]

# --- Component keys per output family (Career Fit / Direction Eval Model section 3) ---

POTENTIAL_FIT_COMPONENTS: tuple[str, ...] = (
    "pf_interests",
    "pf_strengths",
    "pf_skills_match",
    "pf_work_style",
    "pf_work_environment",
    "pf_values_general",
    "pf_experience_relevance",
)

GOAL_ALIGNMENT_COMPONENTS: tuple[str, ...] = (
    "ga_goals",
    "ga_motivation",
    "ga_decision_relevant_values",
)

TRANSITION_FEASIBILITY_COMPONENTS: tuple[str, ...] = (
    "tf_skill_gap",
    "tf_abilities_learning",
    "tf_career_adaptability",
    "tf_constraint_load",
    "tf_requirement_barriers",
)

# Evidence Confidence is computed by a dedicated function, not a weighted
# mean -- these are its audit sub-signals, recorded as score components
# with output_family = evidence_confidence.
EVIDENCE_CONFIDENCE_SIGNALS: tuple[str, ...] = (
    "ec_claim_confidence",
    "ec_evidence_tier",
    "ec_source_diversity",
    "ec_fit_output_coverage",
    "ec_contradiction_load",
    "ec_kb_completeness",
)

ALL_COMPONENTS_BY_FAMILY: dict[str, tuple[str, ...]] = {
    "potential_fit": POTENTIAL_FIT_COMPONENTS,
    "goal_alignment": GOAL_ALIGNMENT_COMPONENTS,
    "transition_feasibility": TRANSITION_FEASIBILITY_COMPONENTS,
    "evidence_confidence": EVIDENCE_CONFIDENCE_SIGNALS,
}

_SCORING_CONFIG_VERSION_V1 = 1
_RANKING_POLICY_VERSION_V1 = 1


EXPERIMENTAL_NON_PRODUCTION_SCORING_CONFIG_V1: dict = {
    "version": _SCORING_CONFIG_VERSION_V1,
    "label": "experimental-non-production-v1",
    "is_experimental": True,
    "methodology_version": METHODOLOGY_VERSION,
    # ALL EQUAL per family -- deliberately not a validated weighting (Founder decision F).
    "component_weights": {
        "potential_fit": {k: 1.0 for k in POTENTIAL_FIT_COMPONENTS},
        "goal_alignment": {k: 1.0 for k in GOAL_ALIGNMENT_COMPONENTS},
        "transition_feasibility": {k: 1.0 for k in TRANSITION_FEASIBILITY_COMPONENTS},
    },
    "enabled_components": {
        "potential_fit": list(POTENTIAL_FIT_COMPONENTS),
        "goal_alignment": list(GOAL_ALIGNMENT_COMPONENTS),
        "transition_feasibility": list(TRANSITION_FEASIBILITY_COMPONENTS),
    },
    "thresholds": {
        # Minimum-profile gate (Founder decision H).
        "min_supported_claims": 4,
        "min_canonical_dimensions": 3,
        # Family aggregation -- min SCORED components for a family to yield a
        # non-None raw (Founder decision F). v0.1: 1 for every family.
        "min_scored_components": {
            "potential_fit": 1,
            "goal_alignment": 1,
            "transition_feasibility": 1,
        },
        # Band cutoffs -- shared by all four outputs (Evidence Standard 2.3).
        "band_high_cutoff": 0.66,
        "band_medium_cutoff": 0.33,
        # Evidence Confidence formula constants (Career Fit / Direction Eval Model section 6).
        "ec_tier_bonus": {"E1": 0.0, "E2": 0.05, "E3": 0.10},
        "ec_diversity_bonus_2": 0.05,
        "ec_diversity_bonus_3plus": 0.10,
        "ec_coverage_bonus_per_extra_output": 0.05,
        "ec_coverage_bonus_cap": 0.10,
        "ec_contradiction_penalty_per_item": 0.10,
        "ec_contradiction_penalty_cap": 0.30,
        "ec_kb_incompleteness_penalty_factor": 0.15,
        # Candidate selection (plan section 7) -- NOT ranking.
        "candidate_shortlist_cap": 25,
    },
    "notes": (
        "EXPERIMENTAL / NON-PRODUCTION. Engineering placeholder weights + thresholds for "
        "Stage 3B four-output pipeline validation. Not methodology-approved. Weights are all "
        "equal per family on purpose (no validated weighting exists). Do not cite as validated."
    ),
}


# RankingPolicy v0.1 -- Founder decision A. NO composite score anywhere in here.
EXPERIMENTAL_NON_PRODUCTION_RANKING_POLICY_V1: dict = {
    "version": _RANKING_POLICY_VERSION_V1,
    "label": "experimental-non-production-v1",
    "is_experimental": True,
    "methodology_version": RANKING_POLICY_VERSION,
    "policy": {
        # 1. eligibility -- hard gate
        "exclude_hard_blocked": True,
        # 2. MAIN eligibility band gates
        "main_eligibility": {
            "potential_fit_min_band": "medium",
            "goal_alignment_forbidden_bands_when_known": ["low"],
            "transition_feasibility_forbidden_bands_when_known": ["low"],
            "evidence_confidence_min_band": "medium",
            "unknown_goal_or_feasibility_is_not_low": True,  # Founder decision A.2
        },
        # 3. MAIN ordering -- lexicographic, None last, NO composite
        "ordering_precedence": [
            {"key": "potential_fit_raw", "direction": "desc", "none": "last"},
            {"key": "goal_alignment_raw", "direction": "desc", "none": "last"},
            {"key": "transition_feasibility_raw", "direction": "desc", "none": "last"},
            {"key": "evidence_confidence_raw", "direction": "desc", "none": "last"},
            {"key": "career_code", "direction": "asc", "none": "last"},
        ],
        # 4. ALTERNATIVE pool
        "alternative_eligibility": {
            "potential_fit_min_band": "medium",
            "allow_low_goal_alignment": True,
            "allow_low_transition_feasibility": True,
            "surface_trade_off": True,
        },
        # 5. pool sizes -- never pad
        "main_max": 3,
        "alternative_max": 3,
        "never_pad": True,
        # 6. missing-output semantics
        "missing_potential_fit_or_evidence_confidence_disqualifies": True,
        # 7. dedup / diversity -- WARNING only, no numeric threshold (Founder decisions I/J)
        "dedup_similarity_threshold": None,
        "diversity_is_warning_only": True,
    },
    "notes": (
        "EXPERIMENTAL / NON-PRODUCTION. RankingPolicy v0.1 per Founder decision A. Contains NO "
        "blended/composite career score -- only eligibility rules, band gates, lexicographic "
        "precedence, pool sizes, missing-output semantics. Not calibrated."
    ),
}


async def ensure_experimental_scoring_config(session: AsyncSession) -> ScoringConfig:
    existing = (
        await session.execute(select(ScoringConfig).where(ScoringConfig.version == _SCORING_CONFIG_VERSION_V1))
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    spec = EXPERIMENTAL_NON_PRODUCTION_SCORING_CONFIG_V1
    cfg = ScoringConfig(
        version=spec["version"],
        label=spec["label"],
        status=PolicyStatus.ACTIVE,
        is_experimental=True,
        methodology_version=spec["methodology_version"],
        component_weights=spec["component_weights"],
        thresholds=spec["thresholds"],
        enabled_components=spec["enabled_components"],
        notes=spec["notes"],
    )
    session.add(cfg)
    await session.commit()
    await session.refresh(cfg)
    return cfg


async def ensure_experimental_ranking_policy(session: AsyncSession) -> RankingPolicy:
    existing = (
        await session.execute(select(RankingPolicy).where(RankingPolicy.version == _RANKING_POLICY_VERSION_V1))
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    spec = EXPERIMENTAL_NON_PRODUCTION_RANKING_POLICY_V1
    policy = RankingPolicy(
        version=spec["version"],
        label=spec["label"],
        status=PolicyStatus.ACTIVE,
        is_experimental=True,
        methodology_version=spec["methodology_version"],
        policy=spec["policy"],
        notes=spec["notes"],
    )
    session.add(policy)
    await session.commit()
    await session.refresh(policy)
    return policy


async def get_active_scoring_config(session: AsyncSession) -> ScoringConfig:
    cfg = (
        await session.execute(select(ScoringConfig).where(ScoringConfig.status == PolicyStatus.ACTIVE))
    ).scalar_one_or_none()
    if cfg is None:
        raise NoActiveScoringConfigError("no ACTIVE ScoringConfig -- call ensure_experimental_scoring_config first")
    return cfg


async def get_active_ranking_policy(session: AsyncSession) -> RankingPolicy:
    policy = (
        await session.execute(select(RankingPolicy).where(RankingPolicy.status == PolicyStatus.ACTIVE))
    ).scalar_one_or_none()
    if policy is None:
        raise NoActiveRankingPolicyError("no ACTIVE RankingPolicy -- call ensure_experimental_ranking_policy first")
    return policy
