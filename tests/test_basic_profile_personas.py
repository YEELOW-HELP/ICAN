"""Matching V1 M2 -- five engineering test personas (Founder Review test
item #28). These are ENGINEERING FIXTURES exercising the deterministic
arithmetic end-to-end with a recognizable, hand-authored bias pattern --
NOT authoritative Golden Cases and NOT a claim of psychometric validation
(Founder Review §16: "Do NOT claim psychometric validation")."""

import pytest

from app.db.models_basic_assessment import ScaleFamily
from app.db.models_basic_profile import DifferentiationState
from app.services.basic_assessment.attempts import complete_attempt
from app.services.basic_assessment.seed import seed_alpha_long_form
from app.services.basic_profile.calculation import calculate_basic_profile
from app.services.basic_profile.contract import build_basic_profile_result
from tests.helpers_basic_profile import answer_all_items

PERSONAS = {
    "A_technical_investigative": {
        "bias": {("riasec", "R"): 5, ("riasec", "I"): 5, ("riasec", "A"): 1, ("riasec", "S"): 1,
                  ("riasec", "E"): 2, ("riasec", "C"): 3,
                  ("work_style", "autonomy"): 5, ("work_style", "ambiguity_tolerance"): 4},
        "expected_top_riasec": {"R", "I"},
    },
    "B_social_helping": {
        "bias": {("riasec", "S"): 5, ("riasec", "E"): 4, ("riasec", "R"): 1, ("riasec", "I"): 2,
                  ("riasec", "A"): 2, ("riasec", "C"): 2,
                  ("work_values", "impact_helping"): 5, ("work_style", "collaboration"): 5},
        "expected_top_riasec": {"S"},
    },
    "C_entrepreneurial_leadership": {
        "bias": {("riasec", "E"): 5, ("riasec", "C"): 4, ("riasec", "R"): 1, ("riasec", "I"): 2,
                  ("riasec", "A"): 2, ("riasec", "S"): 2,
                  ("work_style", "leadership"): 5, ("work_values", "recognition_status"): 5},
        "expected_top_riasec": {"E"},
    },
    "D_artistic_creative": {
        "bias": {("riasec", "A"): 5, ("riasec", "I"): 3, ("riasec", "R"): 1, ("riasec", "S"): 2,
                  ("riasec", "E"): 2, ("riasec", "C"): 1,
                  ("work_style", "structure_preference"): 1, ("work_style", "ambiguity_tolerance"): 5},
        "expected_top_riasec": {"A"},
    },
    "E_flat_undifferentiated": {
        "bias": {},  # everything defaults to 3 -- deliberately flat
        "expected_top_riasec": None,  # ordering exists but carries no real signal
    },
}


@pytest.mark.parametrize("persona_name", list(PERSONAS.keys()))
async def test_persona_produces_stable_expected_result(session, persona_name):
    persona = PERSONAS[persona_name]
    definition = await seed_alpha_long_form(session)
    attempt, _user = await answer_all_items(session, definition, likert_bias=persona["bias"], default_likert=3)
    await complete_attempt(session, attempt)
    await session.commit()

    profile = await calculate_basic_profile(session, attempt)
    await session.commit()
    result = await build_basic_profile_result(session, profile)

    assert profile.coverage == pytest.approx(1.0)  # every item answered

    if persona_name == "E_flat_undifferentiated":
        assert result.interests.differentiation_state == DifferentiationState.LOW_DIFFERENTIATION.value
    else:
        top_letter = profile.interest_ordering[0]
        assert top_letter in persona["expected_top_riasec"]
        assert result.interests.differentiation_state == DifferentiationState.NORMAL.value

    # Report (visible with pytest -s) -- exactly the fields Founder Review
    # #16 asked to report per persona.
    top_work_style = sorted(
        (s for s in result.work_styles.scales if s.normalized_value is not None),
        key=lambda s: -s.normalized_value,
    )[:3]
    top_values = sorted(
        (s for s in result.work_values.scales if s.normalized_value is not None),
        key=lambda s: -s.normalized_value,
    )[:3]
    env_prefs = sorted(
        (s for s in result.work_environment.scales if s.normalized_value is not None),
        key=lambda s: -s.normalized_value,
    )
    print(
        f"\n[{persona_name}] RIASEC order={profile.interest_ordering} "
        f"top_work_style={[(s.scale_key, round(s.normalized_value, 2)) for s in top_work_style]} "
        f"top_values={[(s.scale_key, round(s.normalized_value, 2)) for s in top_values]} "
        f"environment={[(s.scale_key, round(s.normalized_value, 2)) for s in env_prefs]} "
        f"coverage={profile.coverage} differentiation={result.differentiation_state}"
    )
