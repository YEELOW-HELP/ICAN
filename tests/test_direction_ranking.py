"""Founder decision A: RankingPolicy v0.1 -- a SEPARATE versioned decision
layer with NO composite score.

- hard-blocked careers are excluded from eligibility;
- MAIN needs Potential Fit >= MEDIUM and Evidence Confidence >= MEDIUM;
  Goal Alignment / Transition Feasibility must not be LOW *when known*;
- unknown Goal Alignment / Feasibility is NOT LOW -> still MAIN-eligible, with a warning;
- MAIN ordering is lexicographic (PF, GA, TF, EC), None last;
- never pad -- fewer than 3+3 is fine;
- an ALTERNATIVE may carry LOW GA/TF, surfaced as a trade-off.
"""

from app.db.models_direction import DirectionPlacement, QualitativeBand
from app.services.direction.config import EXPERIMENTAL_NON_PRODUCTION_RANKING_POLICY_V1
from app.services.direction.ranking import rank_directions
from tests.direction_test_helpers import bundle

_POLICY = EXPERIMENTAL_NON_PRODUCTION_RANKING_POLICY_V1["policy"]

_HI = QualitativeBand.HIGH
_MED = QualitativeBand.MEDIUM
_LOW = QualitativeBand.LOW


def _placement(results, code):
    return next(r for r in results if r.career_code == code)


def test_hard_blocked_is_excluded_from_eligibility():
    results = rank_directions([bundle("blocked", hard_blocked=True)], policy=_POLICY)
    assert _placement(results, "blocked").placement is DirectionPlacement.BLOCKED


def test_ranking_policy_contains_no_composite_score_key():
    # Guard: the policy must not smuggle in a weighted blend of the four outputs.
    flat = str(_POLICY).lower()
    for forbidden in ("composite", "0.5 * potential", "weighted_sum", "blended_score"):
        assert forbidden not in flat


def test_main_requires_potential_fit_and_evidence_confidence_medium_or_above():
    low_pf = bundle("low_pf", pf=(0.2, _LOW))
    low_ec = bundle("low_ec", ec=(0.2, _LOW))
    ok = bundle("ok", pf=(0.8, _HI), ec=(0.7, _HI))
    results = rank_directions([low_pf, low_ec, ok], policy=_POLICY)
    assert _placement(results, "ok").placement is DirectionPlacement.MAIN
    assert _placement(results, "low_pf").placement is not DirectionPlacement.MAIN
    assert _placement(results, "low_ec").placement is not DirectionPlacement.MAIN


def test_low_known_goal_alignment_disqualifies_main_but_low_pf_still_allows_alternative_only_if_pf_medium():
    low_ga = bundle("low_ga", pf=(0.8, _HI), ga=(0.1, _LOW), ec=(0.7, _HI))
    results = rank_directions([low_ga], policy=_POLICY)
    p = _placement(results, "low_ga")
    assert p.placement is DirectionPlacement.ALTERNATIVE  # PF >= MEDIUM -> alternative
    assert "LOW Goal Alignment" in (p.trade_off_notes or "")


def test_unknown_goal_alignment_is_not_low_still_main_with_warning():
    unknown_ga = bundle("unk_ga", pf=(0.9, _HI), ga=(None, None), tf=(0.6, _MED), ec=(0.8, _HI))
    results = rank_directions([unknown_ga], policy=_POLICY)
    p = _placement(results, "unk_ga")
    assert p.placement is DirectionPlacement.MAIN
    assert "goal_alignment_unknown" in p.coverage_warnings


def test_main_ordering_is_lexicographic_pf_then_ga_then_tf_then_ec():
    a = bundle("a", pf=(0.9, _HI), ga=(0.5, _MED), tf=(0.9, _HI), ec=(0.9, _HI))
    b = bundle("b", pf=(0.9, _HI), ga=(0.8, _HI), tf=(0.1, _LOW), ec=(0.1, _LOW))  # LOW tf -> not MAIN
    c = bundle("c", pf=(0.95, _HI), ga=(0.4, _MED), tf=(0.4, _MED), ec=(0.6, _MED))
    results = [r for r in rank_directions([a, b, c], policy=_POLICY) if r.placement is DirectionPlacement.MAIN]
    order = [r.career_code for r in sorted(results, key=lambda r: r.rank_within_placement)]
    assert order == ["c", "a"]  # c wins on PF; b excluded (LOW tf)


def test_none_sorts_last_within_a_tier():
    known = bundle("known", pf=(0.8, _HI), ga=(0.5, _MED), tf=(0.7, _HI), ec=(0.8, _HI))
    unknown = bundle("unknown", pf=(0.8, _HI), ga=(None, None), tf=(0.7, _HI), ec=(0.8, _HI))
    results = [r for r in rank_directions([unknown, known], policy=_POLICY) if r.placement is DirectionPlacement.MAIN]
    order = [r.career_code for r in sorted(results, key=lambda r: r.rank_within_placement)]
    assert order == ["known", "unknown"]  # equal PF; known GA beats None


def test_never_pads_pools():
    results = rank_directions([bundle("only_one", pf=(0.8, _HI), ec=(0.8, _HI))], policy=_POLICY)
    mains = [r for r in results if r.placement is DirectionPlacement.MAIN]
    alts = [r for r in results if r.placement is DirectionPlacement.ALTERNATIVE]
    assert len(mains) == 1
    assert len(alts) == 0  # nothing invented to reach 3+3


def test_pools_are_capped_at_three_each():
    bundles = [bundle(f"m{i}", pf=(0.9 - i * 0.01, _HI), ec=(0.8, _HI)) for i in range(8)]
    results = rank_directions(bundles, policy=_POLICY)
    assert sum(1 for r in results if r.placement is DirectionPlacement.MAIN) == 3
    assert sum(1 for r in results if r.placement is DirectionPlacement.ALTERNATIVE) == 3


def test_ranking_never_blocks_a_career_only_the_hard_gate_does():
    # A career with terrible scores but hard gate PASS is NOT_ELIGIBLE, never BLOCKED.
    weak = bundle("weak", pf=(0.1, _LOW), ga=(0.1, _LOW), tf=(0.1, _LOW), ec=(0.1, _LOW))
    results = rank_directions([weak], policy=_POLICY)
    assert _placement(results, "weak").placement is DirectionPlacement.NOT_ELIGIBLE
