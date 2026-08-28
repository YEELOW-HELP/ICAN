"""Matching V1 M4 -- full 24-career Alpha catalog run for all 5 M2
engineering personas (Founder Review test items #28-33). Persona bias
maps are imported UNCHANGED from `tests/test_basic_profile_personas.py`
(M2) -- never re-tuned here to make any particular career "win" (Founder
Review §18: "Do NOT tune values after seeing desired careers")."""

import pytest

from app.services.basic_assessment.attempts import complete_attempt
from app.services.basic_assessment.seed import seed_alpha_long_form
from app.services.basic_profile.calculation import calculate_basic_profile
from app.services.career_kb.seed import ALPHA_CAREER_CODES, seed_alpha_career_matching_profiles
from app.services.matching.engine import match_profile_to_careers
from app.services.matching.ranking import rank_matching_results
from tests.helpers_basic_profile import answer_all_items
from tests.test_basic_profile_personas import PERSONAS


async def test_all_24_alpha_careers_processed(session):
    """#28."""
    definition = await seed_alpha_long_form(session)
    attempt, _user = await answer_all_items(session, definition)
    await complete_attempt(session, attempt)
    await session.commit()
    profile = await calculate_basic_profile(session, attempt)
    await session.commit()

    await seed_alpha_career_matching_profiles(session)
    await session.commit()
    results = await match_profile_to_careers(session, profile_id=profile.id)
    await session.commit()
    assert len(results) == len(ALPHA_CAREER_CODES) == 24


@pytest.mark.parametrize("persona_name", list(PERSONAS.keys()))
async def test_persona_ranking_produced(session, persona_name):
    """#29 (technical), #30 (social), #31 (entrepreneurial), #32
    (artistic), #33 (flat persona protected -- see also the dedicated
    assertion below)."""
    persona = PERSONAS[persona_name]
    definition = await seed_alpha_long_form(session)
    attempt, _user = await answer_all_items(session, definition, likert_bias=persona["bias"], default_likert=3)
    await complete_attempt(session, attempt)
    await session.commit()
    profile = await calculate_basic_profile(session, attempt)
    await session.commit()

    await seed_alpha_career_matching_profiles(session)
    await session.commit()
    results = await match_profile_to_careers(session, profile_id=profile.id)
    await session.commit()
    result_ids = [r.id for r in results]
    ranking = await rank_matching_results(session, result_ids, profile_id=profile.id)

    assert len(results) == 24

    if persona_name == "E_flat_undifferentiated":
        # #33: the flat persona must NOT receive an apparently strong
        # Interest Fit anywhere -- every one of the 24 careers' Interest
        # Fit must be LOW_DIFFERENTIATION (never SCORED), so `ranked` is
        # empty and everything lands in `unranked`.
        assert ranking.ranked == []
        assert len(ranking.unranked) + len(ranking.blocked) == 24
        from sqlalchemy import select

        from app.db.models_matching import MatchFamilyResult

        for r in results:
            row = (
                await session.execute(
                    select(MatchFamilyResult).where(
                        MatchFamilyResult.matching_result_id == r.id, MatchFamilyResult.scale_family == "riasec"
                    )
                )
            ).scalar_one()
            # Every mapped career (23 of 24) hits the differentiation guard
            # (LOW_DIFFERENTIATION); the one UNMAPPED career
            # (community_outreach_coordinator) has zero career-side RIASEC
            # components at all, so it correctly hits the EARLIER
            # "no career data" guard (INSUFFICIENT_DATA) instead -- both are
            # non-score states, never SCORED, which is the actual invariant
            # under test.
            assert row.status in ("low_differentiation", "insufficient_data")
            assert row.status != "scored"
            assert row.raw_score is None
    else:
        # A genuinely differentiated persona should produce at least some
        # SCORED Interest Fit results across 23 mapped careers (only
        # community_outreach_coordinator is UNMAPPED / INSUFFICIENT_DATA).
        assert len(ranking.ranked) > 0

    print(
        f"\n[{persona_name}] ranked={[e.career_code for e in ranking.ranked]} "
        f"unranked={[e.career_code for e in ranking.unranked]} blocked={[e.career_code for e in ranking.blocked]}"
    )
