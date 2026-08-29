"""MNP V1 BLOCK C -- pure matching-engine unit tests (no DB)."""

from app.services.matching_mnp.feasibility import (
    BLOCKED, LONG_TRANSITION, NEAR_READY, READY_NOW, REACHABLE,
    PersonFactsForFeasibility, RequirementCheckInput, compute_feasibility, resolve_requirement_outcome,
)
from app.services.matching_mnp.gap import (
    ACTION_LEARN, ACTION_PRACTICE, ACTION_REFRAME, STATE_MATCH, STATE_PARTIAL_GAP, STATE_UNKNOWN,
    SkillGapInput, compute_skill_gaps,
)
from app.services.matching_mnp.pure import (
    STATUS_INSUFFICIENT_DATA, STATUS_SCORED,
    ExperienceTransferInput, PersonLevelInput, PreferenceFitInput, RequirementInput,
    compute_experience_transfer, compute_preference_fit, compute_weighted_coverage_fit,
)
from app.services.matching_mnp.ranking import (
    BEST_FOR_ME, CAN_NOW, ComponentValue, compute_overall_score,
)
from app.services.matching_mnp.transition import (
    D0_SAME_CAREER, D2_ADJACENT, D3_TRANSFERABLE, D4_CAREER_CHANGE,
    compute_transition_cost_score, compute_transition_distance, scenario_for_distance,
)
from app.services.matching_mnp.route import build_route_steps


# ---------------------------------------------------------------------------
# Skill Fit (weighted coverage)

def test_skill_fit_no_requirements_is_insufficient():
    result = compute_weighted_coverage_fit([], {})
    assert result.status == STATUS_INSUFFICIENT_DATA


def test_skill_fit_zero_matched_is_insufficient_not_zero_score():
    """UNKNOWN != confirmed absence -- zero comparable data must never
    become a fabricated low score."""

    reqs = [RequirementInput(key="s1", importance="high", required_level="working")]
    result = compute_weighted_coverage_fit(reqs, {})
    assert result.status == STATUS_INSUFFICIENT_DATA


def test_skill_fit_full_match_scores_high():
    reqs = [
        RequirementInput(key="s1", importance="critical", required_level="working"),
        RequirementInput(key="s2", importance="high", required_level="basic"),
    ]
    persons = {
        "s1": PersonLevelInput(key="s1", proficiency_level="strong", evidence_strength=1.0),
        "s2": PersonLevelInput(key="s2", proficiency_level="strong", evidence_strength=1.0),
    }
    result = compute_weighted_coverage_fit(reqs, persons)
    assert result.status == STATUS_SCORED
    assert result.score == 1.0
    assert result.band == "high"
    assert result.confidence_band == "high"  # full coverage


def test_skill_fit_below_required_level_gives_partial_credit():
    reqs = [RequirementInput(key="s1", importance="high", required_level="strong")]
    persons = {"s1": PersonLevelInput(key="s1", proficiency_level="basic", evidence_strength=1.0)}
    result = compute_weighted_coverage_fit(reqs, persons)
    assert result.status == STATUS_SCORED
    assert 0.0 < result.score < 1.0


def test_skill_fit_partial_coverage_lowers_confidence_not_score_directly():
    reqs = [
        RequirementInput(key="s1", importance="high", required_level="working"),
        RequirementInput(key="s2", importance="high", required_level="working"),
    ]
    persons = {"s1": PersonLevelInput(key="s1", proficiency_level="strong", evidence_strength=1.0)}
    result = compute_weighted_coverage_fit(reqs, persons)
    assert result.status == STATUS_SCORED
    assert result.coverage_ratio == 0.5
    assert result.confidence_band in ("medium", "low")


# ---------------------------------------------------------------------------
# Preference Fit

def test_preference_fit_insufficient_below_min_comparable():
    result = compute_preference_fit(PreferenceFitInput(person_values={"autonomy_preference": 0.8}, career_values={"autonomy": 0.7}))
    assert result.status == STATUS_INSUFFICIENT_DATA


def test_preference_fit_perfect_match_scores_1():
    result = compute_preference_fit(PreferenceFitInput(
        person_values={"autonomy_preference": 0.7, "customer_interaction_preference": 0.9},
        career_values={"autonomy": 0.7, "customer_interaction": 0.9},
    ))
    assert result.status == STATUS_SCORED
    assert result.score == 1.0


def test_preference_fit_routine_is_inverted_correctly():
    """Career routine=1.0 (very routine) vs person novelty-preference=1.0
    (wants novelty) should be a POOR match (score near 0), not a good one."""

    result = compute_preference_fit(PreferenceFitInput(
        person_values={"routine_vs_novelty_preference": 1.0, "autonomy_preference": 0.5},
        career_values={"routine": 1.0, "autonomy": 0.5},
    ))
    assert result.status == STATUS_SCORED
    assert result.score < 0.6  # routine mismatch drags the average down


# ---------------------------------------------------------------------------
# Experience Transfer

def test_experience_transfer_no_experience_insufficient():
    result = compute_experience_transfer(ExperienceTransferInput(
        has_any_experience=False, matches_target_career=False, matches_target_family=False,
        has_management_experience=False, target_career_needs_management=False,
    ))
    assert result.status == STATUS_INSUFFICIENT_DATA


def test_experience_transfer_same_career_scores_highest():
    same = compute_experience_transfer(ExperienceTransferInput(
        has_any_experience=True, matches_target_career=True, matches_target_family=True,
        has_management_experience=False, target_career_needs_management=False,
    ))
    unrelated = compute_experience_transfer(ExperienceTransferInput(
        has_any_experience=True, matches_target_career=False, matches_target_family=False,
        has_management_experience=False, target_career_needs_management=False,
    ))
    assert same.score > unrelated.score
    assert same.band == "high"


def test_experience_transfer_never_penalizes_missing_management_when_not_needed():
    result = compute_experience_transfer(ExperienceTransferInput(
        has_any_experience=True, matches_target_career=True, matches_target_family=True,
        has_management_experience=False, target_career_needs_management=False,
    ))
    assert result.score == 1.0  # domain=1.0, management neutral=1.0 since not needed


def test_experience_transfer_penalizes_missing_management_when_needed():
    with_mgmt = compute_experience_transfer(ExperienceTransferInput(
        has_any_experience=True, matches_target_career=False, matches_target_family=False,
        has_management_experience=True, target_career_needs_management=True,
    ))
    without_mgmt = compute_experience_transfer(ExperienceTransferInput(
        has_any_experience=True, matches_target_career=False, matches_target_family=False,
        has_management_experience=False, target_career_needs_management=True,
    ))
    assert with_mgmt.score > without_mgmt.score


# ---------------------------------------------------------------------------
# Feasibility

def test_feasibility_no_requirements_ready_now():
    result = compute_feasibility([], PersonFactsForFeasibility())
    assert result.status == READY_NOW


def test_feasibility_hard_requirement_missing_fact_is_information_gap_not_blocked():
    """A HARD requirement with NO person data at all is UNKNOWN, never a
    fabricated BLOCKED."""

    reqs = [RequirementCheckInput(category="education", hardness="hard", value="master", description="Потрібна магістратура")]
    result = compute_feasibility(reqs, PersonFactsForFeasibility())
    assert result.status != BLOCKED
    assert "Потрібна магістратура" in result.information_gaps


def test_feasibility_hard_requirement_contradicted_by_fact_blocks():
    reqs = [RequirementCheckInput(category="education", hardness="hard", value="master", description="Потрібна магістратура")]
    facts = PersonFactsForFeasibility(education_levels={"bachelor"}, has_any_education_data=True)
    result = compute_feasibility(reqs, facts)
    assert result.status == BLOCKED
    assert "Потрібна магістратура" in result.hard_blockers


def test_feasibility_soft_requirement_gap_never_blocks():
    reqs = [RequirementCheckInput(category="experience", hardness="soft", value="5_year", description="5 років досвіду")]
    facts = PersonFactsForFeasibility(total_experience_months=12)
    result = compute_feasibility(reqs, facts)
    assert result.status != BLOCKED
    assert result.status in (NEAR_READY, REACHABLE)


def test_feasibility_ladder_reflects_soft_gap_count():
    facts = PersonFactsForFeasibility()  # nothing known -> everything is an information gap, not a soft gap
    one_gap = compute_feasibility(
        [RequirementCheckInput(category="experience", hardness="soft", value="1_year", description="d1")],
        PersonFactsForFeasibility(total_experience_months=0),
    )
    many_gaps = compute_feasibility(
        [
            RequirementCheckInput(category="experience", hardness="soft", value="5_year", description=f"d{i}")
            for i in range(4)
        ],
        PersonFactsForFeasibility(total_experience_months=0),
    )
    assert one_gap.status == NEAR_READY
    assert many_gaps.status == LONG_TRANSITION


def test_language_requirement_below_level_gaps_not_blocks_when_soft():
    reqs = [RequirementCheckInput(category="language", hardness="soft", value="en:b2", description="Англійська B2")]
    facts = PersonFactsForFeasibility(language_levels={"en": "b1"})
    result = compute_feasibility(reqs, facts)
    assert "Англійська B2" in result.soft_gaps


def test_credential_requirement_pass_when_named_credential_present():
    reqs = [RequirementCheckInput(category="credential", hardness="soft", value="pmi", description="Сертифікат PMI")]
    facts = PersonFactsForFeasibility(credential_names_normalized={"сертифікат з управління проектами pmi"}, has_any_credential_data=True)
    result = compute_feasibility(reqs, facts)
    assert result.soft_gaps == [] and result.hard_blockers == []


# ---------------------------------------------------------------------------
# Transition Distance / Cost / Scenario

def test_transition_distance_same_career_is_d0():
    assert compute_transition_distance(domain_label="same_career", skill_fit_band="low", requires_hard_new_education=False) == D0_SAME_CAREER


def test_transition_distance_same_family_high_skill_is_adjacent():
    assert compute_transition_distance(domain_label="same_family", skill_fit_band="high", requires_hard_new_education=False) == D2_ADJACENT


def test_transition_distance_unrelated_low_skill_is_career_change():
    assert compute_transition_distance(domain_label="unrelated_domain", skill_fit_band="low", requires_hard_new_education=False) == D4_CAREER_CHANGE


def test_transition_distance_unrelated_high_skill_is_transferable():
    assert compute_transition_distance(domain_label="unrelated_domain", skill_fit_band="high", requires_hard_new_education=False) == D3_TRANSFERABLE


def test_transition_cost_lower_for_closer_distance():
    close = compute_transition_cost_score(distance=D0_SAME_CAREER, soft_gap_count=0)
    far = compute_transition_cost_score(distance=D4_CAREER_CHANGE, soft_gap_count=4)
    assert close > far


def test_scenario_mapping():
    assert scenario_for_distance(D0_SAME_CAREER) == "safe"
    assert scenario_for_distance(D3_TRANSFERABLE) == "growth"
    assert scenario_for_distance(D4_CAREER_CHANGE) == "transform"


# ---------------------------------------------------------------------------
# Gap / Priority

def test_gap_match_produces_no_result():
    reqs = [SkillGapInput(skill_key="s1", skill_label="Excel", importance="high", required_level="working", requirement_type="must_have", person_proficiency="strong")]
    assert compute_skill_gaps(reqs) == []


def test_gap_unknown_produces_learn_action():
    reqs = [SkillGapInput(skill_key="s1", skill_label="Excel", importance="high", required_level="working", requirement_type="must_have", person_proficiency=None)]
    gaps = compute_skill_gaps(reqs)
    assert gaps[0].state == STATE_UNKNOWN
    assert gaps[0].action == ACTION_LEARN


def test_gap_partial_produces_practice_action():
    reqs = [SkillGapInput(skill_key="s1", skill_label="Excel", importance="high", required_level="strong", requirement_type="must_have", person_proficiency="basic")]
    gaps = compute_skill_gaps(reqs)
    assert gaps[0].state == STATE_PARTIAL_GAP
    assert gaps[0].action == ACTION_PRACTICE


def test_gap_differentiator_always_reframe():
    reqs = [SkillGapInput(skill_key="s1", skill_label="Leadership", importance="medium", required_level="working", requirement_type="differentiator", person_proficiency=None)]
    gaps = compute_skill_gaps(reqs)
    assert gaps[0].action == ACTION_REFRAME


def test_gaps_sorted_by_priority_descending():
    reqs = [
        SkillGapInput(skill_key="low", skill_label="Low", importance="low", required_level="working", requirement_type="optional", person_proficiency=None),
        SkillGapInput(skill_key="critical", skill_label="Critical", importance="critical", required_level="working", requirement_type="must_have", person_proficiency=None),
    ]
    gaps = compute_skill_gaps(reqs)
    assert gaps[0].reference_key == "critical"


# ---------------------------------------------------------------------------
# Ranking

def test_overall_score_missing_components_excluded_not_penalized():
    components_full = {
        "skill_fit": ComponentValue("scored", 0.9), "experience_transfer": ComponentValue("scored", 0.9),
        "preference_fit": ComponentValue("scored", 0.9),
    }
    components_partial = {"skill_fit": ComponentValue("scored", 0.9)}
    score_full, _ = compute_overall_score(components_full, "ready_now", mode=BEST_FOR_ME)
    score_partial, _ = compute_overall_score(components_partial, "ready_now", mode=BEST_FOR_ME)
    assert abs(score_full - score_partial) < 0.05  # both dominated by the same high scores, not dragged down


def test_can_now_mode_prioritizes_feasibility_over_skill_fit():
    components = {"skill_fit": ComponentValue("scored", 0.3)}
    ready_score, _ = compute_overall_score(components, "ready_now", mode=CAN_NOW)
    blocked_like_score, _ = compute_overall_score(components, "long_transition", mode=CAN_NOW)
    assert ready_score > blocked_like_score


# ---------------------------------------------------------------------------
# Route

def test_route_includes_target_role_step():
    steps = build_route_steps(career_label="Менеджер з продажу", matched_skill_labels=["Переговори"], gaps=[])
    assert any(s.step_type == "target_role" for s in steps)
    assert steps[-1].step_type == "next_step"


def test_route_orders_steps_sequentially():
    steps = build_route_steps(career_label="X", matched_skill_labels=["A"], gaps=[])
    orders = [s.order for s in steps]
    assert orders == sorted(orders)
    assert orders == list(range(1, len(orders) + 1))
