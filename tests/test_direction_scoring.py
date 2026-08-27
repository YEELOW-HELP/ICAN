"""Founder decisions F + N + P: deterministic four-output scoring.

- components compare one structured pair; missing pair -> INSUFFICIENT_DATA (never 0);
- family aggregation excludes missing components from numerator AND denominator;
- raw = None (not LOW) when too few components are SCORED;
- tf_skill_gap is computed only from ASSESSED skills (PRESENT + CONFIRMED_MISSING);
- nothing here blends families or ranks.
"""

from app.db.models_direction import OutputFamily, QualitativeBand, ScoreComponentStatus
from app.services.direction.config import EXPERIMENTAL_NON_PRODUCTION_SCORING_CONFIG_V1
from app.services.direction.dimensions import CanonicalDimension
from app.services.direction.scoring.aggregate import aggregate_family, band_for
from app.services.direction.scoring.base import CareerSkillRef, ScoreComponentResult
from app.services.direction.scoring.components import COMPONENTS, score_component
from tests.direction_test_helpers import mapped, score_context

_TH = EXPERIMENTAL_NON_PRODUCTION_SCORING_CONFIG_V1["thresholds"]
_W = EXPERIMENTAL_NON_PRODUCTION_SCORING_CONFIG_V1["component_weights"]


# ---------------------------------------------------------------- components


def test_pf_interests_scores_against_curated_characteristic():
    ctx = score_context(
        mapped_claims=[mapped(CanonicalDimension.INTERESTS, term_key="people_facing_work", normalized_value="loves working with people")],
        characteristics={"works_with_people": 0.9},
    )
    r = score_component("pf_interests", ctx)
    assert r.status is ScoreComponentStatus.SCORED
    assert r.raw_score == 0.9


def test_pf_interests_insufficient_when_characteristic_is_uncurated():
    ctx = score_context(
        mapped_claims=[mapped(CanonicalDimension.INTERESTS, term_key="people_facing_work")],
        characteristics={"works_with_people": None},
    )
    r = score_component("pf_interests", ctx)
    assert r.status is ScoreComponentStatus.INSUFFICIENT_DATA
    assert r.raw_score is None


def test_pf_skills_match_is_overlap_only_never_a_gap_penalty():
    ctx = score_context(
        mapped_claims=[mapped(CanonicalDimension.SKILLS, term_key="python", legacy_dimension="skill")],
        career_skills=(
            CareerSkillRef("python", "required"),
            CareerSkillRef("kubernetes", "required"),  # user unknown here -> simply not counted as covered
        ),
    )
    r = score_component("pf_skills_match", ctx)
    assert r.status is ScoreComponentStatus.SCORED
    assert 0.0 < r.raw_score < 1.0  # partial coverage, not a 0 for the unknown skill


def test_pf_work_environment_collaboration_facet():
    ctx = score_context(
        mapped_claims=[
            mapped(
                CanonicalDimension.WORK_ENVIRONMENT,
                subdimension="collaboration_context",
                normalized_value="prefers working in a close team",
                legacy_dimension="work_preference",
            )
        ],
        work_context={"teamwork_level": 0.8},
    )
    r = score_component("pf_work_environment", ctx)
    assert r.status is ScoreComponentStatus.SCORED
    assert r.raw_score == 0.8


def test_tf_skill_gap_uses_only_assessed_skills():
    # 3 required: python PRESENT, sql CONFIRMED_MISSING, docker UNKNOWN.
    ctx = score_context(
        mapped_claims=[
            mapped(CanonicalDimension.SKILLS, term_key="python", claim_status="supported", legacy_dimension="skill"),
            mapped(CanonicalDimension.SKILLS, term_key="sql", claim_status="contradicted", legacy_dimension="skill"),
        ],
        career_skills=(
            CareerSkillRef("python", "required"),
            CareerSkillRef("sql", "required"),
            CareerSkillRef("docker", "required"),
        ),
    )
    r = score_component("tf_skill_gap", ctx)
    assert r.status is ScoreComponentStatus.SCORED
    # assessed = 2 (python, sql); confirmed_missing = 1 -> raw = 1 - 1/2 = 0.5. docker (UNKNOWN) not a penalty.
    assert r.raw_score == 0.5
    assert r.contributing_career_attributes["skills_to_verify"] == ["docker"]


def test_tf_skill_gap_insufficient_when_all_required_skills_unknown():
    ctx = score_context(
        mapped_claims=[],
        career_skills=(CareerSkillRef("python", "required"), CareerSkillRef("sql", "required")),
    )
    r = score_component("tf_skill_gap", ctx)
    assert r.status is ScoreComponentStatus.INSUFFICIENT_DATA
    assert r.raw_score is None
    assert set(r.contributing_career_attributes["skills_to_verify"]) == {"python", "sql"}


def test_all_stub_components_return_insufficient_data_not_zero():
    ctx = score_context()
    stub_keys = [
        "pf_strengths", "pf_work_style", "pf_values_general", "pf_experience_relevance",
        "ga_goals", "ga_motivation", "ga_decision_relevant_values",
        "tf_abilities_learning", "tf_career_adaptability", "tf_constraint_load", "tf_requirement_barriers",
    ]
    for key in stub_keys:
        r = score_component(key, ctx)
        assert r.status is ScoreComponentStatus.INSUFFICIENT_DATA, key
        assert r.raw_score is None, key


# ---------------------------------------------------------------- aggregation


def _scored(key, family, raw):
    return ScoreComponentResult(key, family, ScoreComponentStatus.SCORED, raw, "r")


def _insuff(key, family):
    return ScoreComponentResult(key, family, ScoreComponentStatus.INSUFFICIENT_DATA, None, "r")


def test_missing_components_excluded_from_numerator_and_denominator():
    results = [
        _scored("pf_interests", OutputFamily.POTENTIAL_FIT, 0.8),
        _insuff("pf_strengths", OutputFamily.POTENTIAL_FIT),
        _insuff("pf_values_general", OutputFamily.POTENTIAL_FIT),
    ]
    out = aggregate_family(OutputFamily.POTENTIAL_FIT, results, weights=_W["potential_fit"], thresholds=_TH)
    assert out.raw == 0.8  # only the SCORED component -- missing ones did not drag it to 0.27
    assert out.scored_component_count == 1
    assert out.enabled_component_count == 3
    assert out.coverage_ratio == 1 / 3


def test_family_raw_is_none_when_below_min_scored():
    th = dict(_TH)
    th["min_scored_components"] = {"potential_fit": 2}
    results = [
        _scored("pf_interests", OutputFamily.POTENTIAL_FIT, 0.9),
        _insuff("pf_strengths", OutputFamily.POTENTIAL_FIT),
    ]
    out = aggregate_family(OutputFamily.POTENTIAL_FIT, results, weights=_W["potential_fit"], thresholds=th)
    assert out.raw is None
    assert out.band is None  # unknown, NOT low
    assert out.coverage_ratio == 0.5


def test_band_cutoffs():
    assert band_for(0.9, _TH) is QualitativeBand.HIGH
    assert band_for(0.5, _TH) is QualitativeBand.MEDIUM
    assert band_for(0.1, _TH) is QualitativeBand.LOW
    assert band_for(None, _TH) is None


def test_weighted_mean_is_deterministic():
    results = [
        _scored("pf_interests", OutputFamily.POTENTIAL_FIT, 0.6),
        _scored("pf_skills_match", OutputFamily.POTENTIAL_FIT, 0.8),
    ]
    out = aggregate_family(OutputFamily.POTENTIAL_FIT, results, weights=_W["potential_fit"], thresholds=_TH)
    assert out.raw == 0.7  # equal weights
    assert out.band is QualitativeBand.HIGH


def test_config_registers_a_scorer_for_every_enabled_component():
    for family, keys in EXPERIMENTAL_NON_PRODUCTION_SCORING_CONFIG_V1["enabled_components"].items():
        for key in keys:
            assert key in COMPONENTS, f"{family}:{key} has no registered scorer"
