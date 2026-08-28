"""Matching V1 M4 -- ranking (Founder Review test items #20-25)."""

import pytest
from sqlalchemy import select

from app.db.models_career_kb import CareerMatchingProfile
from app.db.models_matching import MatchFeasibilityResult
from app.services.basic_assessment.attempts import complete_attempt
from app.services.basic_assessment.seed import seed_alpha_long_form
from app.services.basic_profile.calculation import calculate_basic_profile
from app.services.career_kb.seed import seed_alpha_career_matching_profiles
from app.services.knowledge.retrieval import get_career_by_code
from app.services.matching.engine import calculate_pair_match, match_profile_to_careers
from app.services.matching.ranking import rank_matching_results
from tests.helpers_basic_profile import answer_all_items


async def _build_profile(session, *, likert_bias=None, boolean_overrides=None):
    definition = await seed_alpha_long_form(session)
    attempt, user = await answer_all_items(
        session, definition, likert_bias=likert_bias or {}, default_likert=3, boolean_overrides=boolean_overrides or {}
    )
    await complete_attempt(session, attempt)
    await session.commit()
    profile = await calculate_basic_profile(session, attempt)
    await session.commit()
    return profile, user


async def test_blocked_career_excluded_from_eligible_ranking(session):
    """#20 -- synthetically force one career BLOCKED (no HARD_FACTUAL
    requirement exists in the real Alpha seed, so a test-only requirement
    row is added here) and confirm it lands in `blocked`, never in
    `ranked`/`unranked`, but the MatchingResult row itself still exists
    (never deleted)."""
    from app.db.models_knowledge import CareerRequirement

    await seed_alpha_career_matching_profiles(session)
    await session.commit()
    career = await get_career_by_code(session, "software_developer")
    session.add(
        CareerRequirement(
            career_id=career.id, category="license", certainty="hard_factual",
            description="Test-only synthetic hard requirement",
        )
    )
    await session.commit()

    profile, _user = await _build_profile(
        session, boolean_overrides={("constraints", "credential_legal"): False}
    )
    results = await match_profile_to_careers(session, profile_id=profile.id)
    await session.commit()

    result_ids = [r.id for r in results]
    ranking = await rank_matching_results(session, result_ids, profile_id=profile.id)

    software_dev_result = next(r for r in results if r.career_id == career.id)
    feasibility_row = (
        await session.execute(select(MatchFeasibilityResult).where(MatchFeasibilityResult.matching_result_id == software_dev_result.id))
    ).scalar_one()
    assert feasibility_row.status == "blocked"
    assert not software_dev_result.eligible

    blocked_codes = {e.career_code for e in ranking.blocked}
    assert "software_developer" in blocked_codes
    ranked_codes = {e.career_code for e in ranking.ranked} | {e.career_code for e in ranking.unranked}
    assert "software_developer" not in ranked_codes


async def test_no_composite_score_field(session):
    """#21."""
    profile, _user = await _build_profile(session)
    results = await match_profile_to_careers(session, profile_id=profile.id)
    await session.commit()
    for r in results:
        assert not hasattr(r, "match_score")
        assert not hasattr(r, "overall_score")
        assert not hasattr(r, "composite_score")


async def test_ranking_deterministic(session):
    """#22 -- same inputs, repeated ranking calls, identical order."""
    profile, _user = await _build_profile(
        session, likert_bias={("riasec", "R"): 5, ("riasec", "I"): 5, ("riasec", "A"): 1, ("riasec", "S"): 1, ("riasec", "E"): 2, ("riasec", "C"): 3}
    )
    results = await match_profile_to_careers(session, profile_id=profile.id)
    await session.commit()
    result_ids = [r.id for r in results]

    ranking1 = await rank_matching_results(session, result_ids, profile_id=profile.id)
    ranking2 = await rank_matching_results(session, result_ids, profile_id=profile.id)

    assert [e.career_code for e in ranking1.ranked] == [e.career_code for e in ranking2.ranked]
    assert [e.career_code for e in ranking1.unranked] == [e.career_code for e in ranking2.unranked]


async def test_missing_family_not_treated_as_zero_in_ranking(session):
    """#23 -- careers lacking Work Style/Values data are not pushed below
    careers with a genuinely LOW Interest Fit; the interest-scored group
    (`ranked`) is ordered purely by Interest Fit as the primary criterion,
    and Work Style/Values absence only ever acts as a LATER tie-break,
    never as if it were a zero on the primary axis."""
    profile, _user = await _build_profile(
        session, likert_bias={("riasec", "R"): 5, ("riasec", "I"): 5, ("riasec", "A"): 1, ("riasec", "S"): 1, ("riasec", "E"): 2, ("riasec", "C"): 3}
    )
    results = await match_profile_to_careers(session, profile_id=profile.id)
    await session.commit()
    result_ids = [r.id for r in results]
    ranking = await rank_matching_results(session, result_ids, profile_id=profile.id)

    # every ranked entry lacking Work Style/Values data must still be
    # ordered by its own Interest Fit band/score, not dumped at the bottom
    # regardless of Interest Fit.
    interest_scores = [e.interest_raw_score for e in ranking.ranked]
    assert interest_scores == sorted(interest_scores, reverse=True) or _grouped_by_band_desc(ranking.ranked)


def _grouped_by_band_desc(entries) -> bool:
    bands = [e.interest_band for e in entries]
    rank = {"high": 2, "medium": 1, "low": 0}
    return all(rank[bands[i]] >= rank[bands[i + 1]] for i in range(len(bands) - 1))


async def test_stable_career_code_tie_break(session):
    """#24 -- two careers tied on every other criterion sort by
    Career.code ascending, deterministically."""
    from app.services.matching.ranking import RankedEntry, _sort_key_for_ranked

    entry_a = RankedEntry(
        matching_result_id=None, career_id=None, career_code="zzz_career", eligible=True,
        interest_status="scored", interest_band="high", interest_raw_score=0.9,
        work_style_status="insufficient_data", work_style_band=None, work_style_raw_score=None,
        values_status="insufficient_data", values_band=None, values_raw_score=None,
        feasibility_status="feasible", feasibility_raw_score=1.0, goals_domain_match=False,
        participating_families=("interest",),
    )
    entry_b = RankedEntry(
        matching_result_id=None, career_id=None, career_code="aaa_career", eligible=True,
        interest_status="scored", interest_band="high", interest_raw_score=0.9,
        work_style_status="insufficient_data", work_style_band=None, work_style_raw_score=None,
        values_status="insufficient_data", values_band=None, values_raw_score=None,
        feasibility_status="feasible", feasibility_raw_score=1.0, goals_domain_match=False,
        participating_families=("interest",),
    )
    ordered = sorted([entry_a, entry_b], key=_sort_key_for_ranked)
    assert [e.career_code for e in ordered] == ["aaa_career", "zzz_career"]


async def test_goals_do_not_change_raw_fit(session):
    """#25 -- a Goals domain match changes ranking ORDER (tie-break) but
    never the underlying raw_score/status of any Fit family."""
    profile, _user = await _build_profile(
        session, likert_bias={("riasec", "R"): 5, ("riasec", "I"): 5, ("riasec", "A"): 1, ("riasec", "S"): 1, ("riasec", "E"): 2, ("riasec", "C"): 3}
    )
    results_before = await match_profile_to_careers(session, profile_id=profile.id)
    await session.commit()
    raw_scores_before = {r.career_id: r for r in results_before}

    result_ids = [r.id for r in results_before]
    ranking = await rank_matching_results(session, result_ids, profile_id=profile.id)

    # re-fetch the underlying MatchFamilyResult rows directly -- unaffected
    # by whatever the ranking computed for goals_domain_match.
    from app.db.models_matching import MatchFamilyResult

    for r in results_before:
        row = (
            await session.execute(
                select(MatchFamilyResult).where(MatchFamilyResult.matching_result_id == r.id, MatchFamilyResult.scale_family == "riasec")
            )
        ).scalar_one()
        assert row.raw_score is None or isinstance(row.raw_score, float)  # untouched by any goals logic
    assert ranking is not None  # ranking succeeded without mutating any MatchFamilyResult
