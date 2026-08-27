"""Stage 3B Slice 3 §1: real Goal Alignment v0.1 (`ga_goals`).

Explicit Goals claims ONLY, matched against structured Career KB data
ONLY -- never inferred from CV, current occupation, Interests, or Values.
"""

from app.db.models_direction import ScoreComponentStatus
from app.services.direction.dimensions import CanonicalDimension
from app.services.direction.scoring.components import score_component
from tests.direction_test_helpers import mapped, score_context


def test_explicit_goal_matched_to_career_domain_produces_real_score():
    """#1: a real explicit Goal claim comparable to structured KB data
    (career domain) produces a SCORED Goal Alignment component."""
    ctx = score_context(
        mapped_claims=[
            mapped(CanonicalDimension.GOALS, term_key=None, normalized_value="I want to work in technology", legacy_dimension="goal")
        ],
        career_domain="technology",
    )
    r = score_component("ga_goals", ctx)
    assert r.status is ScoreComponentStatus.SCORED
    assert r.raw_score == 1.0


def test_explicit_goal_mismatched_domain_is_a_real_zero_not_insufficient():
    ctx = score_context(
        mapped_claims=[
            mapped(CanonicalDimension.GOALS, term_key=None, normalized_value="I want to work in sales", legacy_dimension="goal")
        ],
        career_domain="technology",
    )
    r = score_component("ga_goals", ctx)
    assert r.status is ScoreComponentStatus.SCORED
    assert r.raw_score == 0.0  # a real, comparable mismatch -- not the same as "no data"


def test_explicit_goal_work_format_matched_against_work_context():
    ctx = score_context(
        mapped_claims=[
            mapped(CanonicalDimension.GOALS, term_key=None, normalized_value="I want to work remotely", legacy_dimension="goal")
        ],
        work_context={"setting": "remote"},
    )
    r = score_component("ga_goals", ctx)
    assert r.status is ScoreComponentStatus.SCORED
    assert r.raw_score == 1.0


def test_explicit_leadership_goal_matched_against_responsibility_level():
    ctx = score_context(
        mapped_claims=[
            mapped(CanonicalDimension.GOALS, term_key=None, normalized_value="I want a leadership role managing a team", legacy_dimension="goal")
        ],
        work_context={"responsibility_level": 0.8},
    )
    r = score_component("ga_goals", ctx)
    assert r.status is ScoreComponentStatus.SCORED
    assert r.raw_score == 0.8


def test_unmatchable_goal_remains_insufficient_data():
    """#2: a Goals claim that cannot be compared to any structured Career
    KB attribute stays INSUFFICIENT_DATA -- never guessed, never zero."""
    ctx = score_context(
        mapped_claims=[
            mapped(CanonicalDimension.GOALS, term_key=None, normalized_value="I want to feel more fulfilled in life", legacy_dimension="goal")
        ],
        career_domain="technology",
        work_context={},
    )
    r = score_component("ga_goals", ctx)
    assert r.status is ScoreComponentStatus.INSUFFICIENT_DATA
    assert r.raw_score is None


def test_no_goals_claims_at_all_is_insufficient_data():
    ctx = score_context(mapped_claims=[])
    r = score_component("ga_goals", ctx)
    assert r.status is ScoreComponentStatus.INSUFFICIENT_DATA
    assert r.raw_score is None


def test_does_not_infer_goal_from_interests_or_values():
    """#3: a strong INTERESTS claim and a VALUES claim, with no GOALS
    claim at all, must never feed ga_goals -- system does not infer a
    goal from Interests/Values (or, by the same mechanism, from CV or
    current occupation, neither of which is even a canonical dimension
    ga_goals reads)."""
    ctx = score_context(
        mapped_claims=[
            mapped(CanonicalDimension.INTERESTS, term_key="technical_problem_solving", normalized_value="loves technology", legacy_dimension="interest"),
            mapped(CanonicalDimension.VALUES, term_key=None, normalized_value="values working in technology", legacy_dimension="value"),
        ],
        career_domain="technology",
    )
    r = score_component("ga_goals", ctx)
    assert r.status is ScoreComponentStatus.INSUFFICIENT_DATA
    assert r.raw_score is None
    assert r.contributing_claim_ids == ()


def test_general_work_values_are_not_double_counted_in_goal_alignment():
    """Founder: "General Work Values must still NOT be double-counted in
    Goal Alignment." A VALUES claim mentioning a domain keyword must not
    leak into ga_goals even when a real GOALS claim is also present."""
    ctx = score_context(
        mapped_claims=[
            mapped(CanonicalDimension.GOALS, term_key=None, normalized_value="I want to work in technology", legacy_dimension="goal"),
            mapped(CanonicalDimension.VALUES, term_key=None, normalized_value="values technology and innovation deeply", legacy_dimension="value"),
        ],
        career_domain="technology",
    )
    r = score_component("ga_goals", ctx)
    assert r.status is ScoreComponentStatus.SCORED
    # exactly one signal (the GOALS claim) -- the VALUES claim contributed nothing
    assert len(r.contributing_claim_ids) == 1
