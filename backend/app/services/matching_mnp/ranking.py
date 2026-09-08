"""7 Ranking Modes (`MNP_RANKING_MODES_V1`): "each mode uses the same
component data but a different versioned weighting/filter
configuration." No mode recomputes any Fit component -- all 7 read the
exact same `MatchComponent` rows for a `MnpCareerMatch` and differ only
in `MODE_WEIGHTS`. A component with status != SCORED contributes nothing
to the weighted sum AND its weight is excluded from the normalizer, so
missing/insufficient data never drags a career down (mirrors the general
"Confidence gates, never fabricates" principle) -- an all-insufficient
career simply falls back to ranking by Feasibility alone, which is
always computed (rule-based, never "insufficient").

Two modes ("Більше заробляти"/earn_more and "Перспективні"/promising)
are weighted toward Income Potential/Market Attractiveness, which are
INSUFFICIENT_DATA for every career in the current 5-career vertical
slice (no market snapshots exist yet, Founder-mandated: no fabricated
market facts) -- until real `MnpMarketSnapshot` data exists, these two
modes legitimately fall back to the same Feasibility-anchored ordering
as every other mode. This is a disclosed, honest limitation of the
CURRENT DATA, not the ranking mechanism, which is fully implemented and
will differentiate correctly the moment real market data is seeded."""

from __future__ import annotations

from dataclasses import dataclass

FEASIBILITY_SCORE = {
    "ready_now": 1.0, "near_ready": 0.8, "reachable": 0.5, "long_transition": 0.2,
}

BEST_FOR_ME = "best_for_me"
CAN_NOW = "can_now"
USE_MY_EXPERIENCE = "use_my_experience"
EARN_MORE = "earn_more"
TRANSITION_FAST = "transition_fast"
PROMISING = "promising"
NEW_DIRECTION = "new_direction"

RANKING_MODES: dict[str, dict[str, float]] = {
    BEST_FOR_ME: {
        "feasibility": 1.5, "skill_fit": 1.0, "experience_transfer": 1.0, "preference_fit": 1.0,
        "knowledge_fit": 0.5, "values_fit": 0.5, "market_attractiveness": 0.5, "income_potential": 0.5,
        "transition_cost": 0.5,
    },
    CAN_NOW: {"feasibility": 3.0, "skill_fit": 1.0, "transition_cost": 1.0},
    USE_MY_EXPERIENCE: {"experience_transfer": 3.0, "skill_fit": 1.0, "feasibility": 0.5},
    EARN_MORE: {"income_potential": 3.0, "market_attractiveness": 1.0, "feasibility": 0.5},
    TRANSITION_FAST: {"transition_cost": 3.0, "feasibility": 1.5},
    PROMISING: {"market_attractiveness": 3.0, "income_potential": 1.0, "feasibility": 0.5},
    # "Новий напрям": favors novelty over reuse of existing experience --
    # inverted experience_transfer (1 - score) is the only novelty proxy
    # available without RIASEC/interest data (Founder Decisions #22/#23:
    # RIASEC is a secondary signal not yet modeled in BLOCK A/C v0.1;
    # this mode will incorporate it directly once that data exists).
    NEW_DIRECTION: {"skill_fit": 1.5, "preference_fit": 1.0, "knowledge_fit": 0.5, "_novelty": 1.5},
}

RANKING_CONFIG_VERSION = "mnp_ranking_v0.1"


@dataclass(frozen=True)
class ComponentValue:
    status: str  # "scored" | "insufficient_data"
    score: float | None


def compute_overall_score(
    components: dict[str, ComponentValue], feasibility_status: str, *, mode: str,
) -> tuple[float, int]:
    """Returns (overall_score_internal, participating_component_count).
    Never shown to the user (Founder Decision #15) -- ranking/sorting
    only."""

    weights = RANKING_MODES[mode]
    weighted_sum = 0.0
    total_weight = 0.0
    participating = 0

    feasibility_weight = weights.get("feasibility")
    if feasibility_weight and feasibility_status in FEASIBILITY_SCORE:
        weighted_sum += feasibility_weight * FEASIBILITY_SCORE[feasibility_status]
        total_weight += feasibility_weight
        participating += 1

    for key, weight in weights.items():
        if key in ("feasibility", "_novelty"):
            continue
        component = components.get(key)
        if component is None or component.status != "scored" or component.score is None:
            continue
        weighted_sum += weight * component.score
        total_weight += weight
        participating += 1

    novelty_weight = weights.get("_novelty")
    if novelty_weight:
        experience = components.get("experience_transfer")
        if experience is not None and experience.status == "scored" and experience.score is not None:
            weighted_sum += novelty_weight * (1.0 - experience.score)
            total_weight += novelty_weight
            participating += 1

    overall = weighted_sum / total_weight if total_weight > 0 else FEASIBILITY_SCORE.get(feasibility_status, 0.0)
    return overall, participating
