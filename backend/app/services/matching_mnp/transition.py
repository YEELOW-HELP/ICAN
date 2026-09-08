"""Transition Distance classification (`MNP_TRANSITION_DISTANCE_V1`).
Determinants used in v0.1: domain proximity (from Experience Transfer's
job-title/family resolution) and Skill Fit. `MNP_CAREER_PROFILE_SCHEMA_V1`
§21's optional Career Level ladder (ENTRY/MIDDLE/SENIOR/...) is not
modeled in BLOCK A's schema yet, so **D1 Progression is not
distinguished from D0 in this version** -- a documented, disclosed
simplification, not a silent gap. D5 Fundamental Retraining only fires
when a HARD education-category requirement exists for the target career
(a real mandatory-formal-retraining signal); none of the 5 Alpha careers
carry a HARD education requirement, so D5 legitimately never appears for
this vertical slice."""

from __future__ import annotations

D0_SAME_CAREER = "d0_same_career"
D1_PROGRESSION = "d1_progression"
D2_ADJACENT = "d2_adjacent"
D3_TRANSFERABLE = "d3_transferable"
D4_CAREER_CHANGE = "d4_career_change"
D5_FUNDAMENTAL_RETRAINING = "d5_fundamental_retraining"

_HIGH_MEDIUM_BANDS = ("high", "medium")


def compute_transition_distance(
    *, domain_label: str, skill_fit_band: str | None, requires_hard_new_education: bool,
) -> str:
    if domain_label == "same_career":
        return D0_SAME_CAREER

    strong_skill_overlap = skill_fit_band in _HIGH_MEDIUM_BANDS

    if domain_label == "same_family":
        return D2_ADJACENT if strong_skill_overlap else D3_TRANSFERABLE

    # domain_label == "unrelated_domain"
    if strong_skill_overlap:
        return D3_TRANSFERABLE
    if requires_hard_new_education:
        return D5_FUNDAMENTAL_RETRAINING
    return D4_CAREER_CHANGE


_DISTANCE_RANK = {
    D0_SAME_CAREER: 0, D1_PROGRESSION: 1, D2_ADJACENT: 2, D3_TRANSFERABLE: 3, D4_CAREER_CHANGE: 4,
    D5_FUNDAMENTAL_RETRAINING: 5,
}


def compute_transition_cost_score(*, distance: str, soft_gap_count: int) -> float:
    """A deterministic proxy (MNP_MATCHING_MATH_V1 Transition Cost has no
    time/financial estimation model in v0.1 -- disclosed simplification):
    higher distance + more open skill gaps = higher cost = LOWER score
    (this is a "how cheap is the transition" score, so it can be ranked
    the same directional way as every other Fit component -- high score
    is good)."""

    raw = _DISTANCE_RANK[distance] + min(soft_gap_count, 5)
    return max(0.0, 1.0 - raw / 10.0)


def scenario_for_distance(distance: str) -> str:
    """SAFE/GROWTH/TRANSFORM (MNP_ROUTE_ENGINE_V1 "Scenarios") as a
    direct function of Transition Distance -- the lowest-cost, most
    reuse-heavy framing for D0-D2, the most demanding for D4-D5."""

    if distance in (D0_SAME_CAREER, D1_PROGRESSION, D2_ADJACENT):
        return "safe"
    if distance == D3_TRANSFERABLE:
        return "growth"
    return "transform"
