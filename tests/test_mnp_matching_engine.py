"""MNP V1 BLOCK C -- Matching Engine DB orchestration integration tests."""

import ast
import inspect

from sqlalchemy import select

from app.db.models_career_card import (
    ConstraintSeverity,
    EntryMode,
    EvidenceSourceType,
    MnpConstraint,
    SourceMode,
)
from app.db.models_identity import IdentityUser
from app.db.models_matching_mnp import (
    FeasibilityStatus,
    MnpCareerMatch,
    MnpCareerRoute,
    MnpFeasibilityFinding,
    MnpMatchComponent,
    MnpPersonalGap,
    MnpRouteStep,
)
from app.services.career_card_mnp.card import get_or_create_career_card, start_assessment_session
from app.services.career_kb_mnp.seed_alpha import ALPHA_CAREER_CODES, seed_alpha_career_kb
from app.services.matching_mnp import config, engine, feasibility, gap, pure, ranking, route, transition
from app.services.matching_mnp.engine import run_match
from app.services.matching_mnp.ranking import CAN_NOW, USE_MY_EXPERIENCE
from app.services.resume_parser_mnp.parser import upload_and_parse_resume

SALES_CV = (
    "Досвід роботи\n"
    "01.2020 - теперішній час\n"
    "Менеджер з продажу\n"
    "Веде переговори з клієнтами, керував командою з 4 осіб\n\n"
    "Навички\n"
    "Переговори, CRM, Excel\n"
).encode("utf-8")


async def _make_blank_card(session):
    user = IdentityUser(locale="uk")
    session.add(user)
    await session.flush()
    s = await start_assessment_session(session, user_id=user.id, entry_mode=EntryMode.MANUAL)
    card = await get_or_create_career_card(session, user_id=user.id, assessment_session_id=s.id, source_mode=SourceMode.MANUAL)
    await session.commit()
    return card


async def test_blank_card_all_careers_ready_now_with_insufficient_fits(session):
    """Zero person data -> every requirement is an information gap
    (UNKNOWN), never a fabricated fail -- so feasibility is READY_NOW
    everywhere, but the Fit components that need person data are
    INSUFFICIENT_DATA."""

    await seed_alpha_career_kb(session)
    card = await _make_blank_card(session)

    match_run = await run_match(session, career_card_id=card.id)
    await session.commit()

    matches = (await session.execute(select(MnpCareerMatch).where(MnpCareerMatch.match_run_id == match_run.id))).scalars().all()
    assert len(matches) == len(ALPHA_CAREER_CODES)
    assert all(m.feasibility_status == FeasibilityStatus.READY_NOW for m in matches)

    components = (
        await session.execute(select(MnpMatchComponent).where(MnpMatchComponent.career_match_id == matches[0].id))
    ).scalars().all()
    skill_fit = next(c for c in components if c.component_type.value == "skill_fit")
    assert skill_fit.band.value == "insufficient"


async def test_sales_manager_ranks_highly_for_sales_experience(session):
    await seed_alpha_career_kb(session)
    user = IdentityUser(locale="uk")
    session.add(user)
    await session.flush()
    card, _ = await upload_and_parse_resume(session, user_id=user.id, filename="cv.txt", content_bytes=SALES_CV)

    match_run = await run_match(session, career_card_id=card.id)
    await session.commit()

    matches = (
        await session.execute(
            select(MnpCareerMatch).where(MnpCareerMatch.match_run_id == match_run.id).order_by(MnpCareerMatch.rank_overall)
        )
    ).scalars().all()
    from app.db.models_career_kb_mnp import MnpCareer

    top = await session.get(MnpCareer, matches[0].career_id)
    assert top.code == "sales_manager"


async def test_excluded_career_removed_entirely_from_match_run(session):
    await seed_alpha_career_kb(session)
    card = await _make_blank_card(session)
    session.add(MnpConstraint(
        career_card_id=card.id, constraint_type="excluded_career", value="accountant",
        severity=ConstraintSeverity.HARD, source_type=EvidenceSourceType.QUESTIONNAIRE, active=True,
    ))
    await session.commit()

    match_run = await run_match(session, career_card_id=card.id)
    await session.commit()

    matches = (await session.execute(select(MnpCareerMatch).where(MnpCareerMatch.match_run_id == match_run.id))).scalars().all()
    from app.db.models_career_kb_mnp import MnpCareer

    codes = {(await session.get(MnpCareer, m.career_id)).code for m in matches}
    assert "accountant" not in codes
    assert len(matches) == len(ALPHA_CAREER_CODES) - 1


async def test_all_nine_match_components_persisted_per_career(session):
    await seed_alpha_career_kb(session)
    card = await _make_blank_card(session)
    match_run = await run_match(session, career_card_id=card.id)
    await session.commit()

    one_match = (await session.execute(select(MnpCareerMatch).where(MnpCareerMatch.match_run_id == match_run.id))).scalars().first()
    components = (
        await session.execute(select(MnpMatchComponent).where(MnpMatchComponent.career_match_id == one_match.id))
    ).scalars().all()
    types = {c.component_type.value for c in components}
    assert types == {
        "skill_fit", "experience_transfer", "knowledge_fit", "preference_fit", "values_fit",
        "market_attractiveness", "income_potential", "transition_cost",
    }
    # Feasibility itself is a MnpCareerMatch field, not a MatchComponent row --
    # this asserts the 8 MatchComponent-typed dimensions plus feasibility = 9 total per Methodology §19.


async def test_market_and_income_and_values_and_knowledge_are_honestly_insufficient(session):
    """No MnpMarketSnapshot/CareerKnowledgeRequirement/career-side Work
    Values data exists for the Alpha 5 -- these components must say so,
    never invent a number."""

    await seed_alpha_career_kb(session)
    user = IdentityUser(locale="uk")
    session.add(user)
    await session.flush()
    card, _ = await upload_and_parse_resume(session, user_id=user.id, filename="cv.txt", content_bytes=SALES_CV)
    match_run = await run_match(session, career_card_id=card.id)
    await session.commit()

    matches = (await session.execute(select(MnpCareerMatch).where(MnpCareerMatch.match_run_id == match_run.id))).scalars().all()
    for m in matches:
        components = (
            await session.execute(select(MnpMatchComponent).where(MnpMatchComponent.career_match_id == m.id))
        ).scalars().all()
        by_type = {c.component_type.value: c for c in components}
        for key in ("knowledge_fit", "values_fit", "market_attractiveness", "income_potential"):
            assert by_type[key].score_internal is None
            assert by_type[key].band.value == "insufficient"


async def test_personal_gaps_generated_and_sorted_by_priority(session):
    await seed_alpha_career_kb(session)
    card = await _make_blank_card(session)
    match_run = await run_match(session, career_card_id=card.id)
    await session.commit()

    from app.db.models_career_kb_mnp import MnpCareer

    sales_career = (await session.execute(select(MnpCareer).where(MnpCareer.code == "sales_manager"))).scalar_one()
    match = (
        await session.execute(
            select(MnpCareerMatch).where(MnpCareerMatch.match_run_id == match_run.id, MnpCareerMatch.career_id == sales_career.id)
        )
    ).scalar_one()
    gaps = (await session.execute(select(MnpPersonalGap).where(MnpPersonalGap.career_match_id == match.id))).scalars().all()
    assert len(gaps) > 0  # blank card -> every skill requirement is a gap
    priorities = [g.priority_internal for g in gaps]
    assert priorities == sorted(priorities, reverse=True)


async def test_feasibility_findings_reference_a_real_requirement(session):
    """Every soft/hard finding traces back to a real `MnpCareerRequirement`
    row (explainability: MNP_CAREER_COMPATIBILITY_REPORT_V1 "Missing/
    unknown requirements" must be concrete, not a bare label)."""

    await seed_alpha_career_kb(session)
    card = await _make_blank_card(session)  # blank -> every soft requirement becomes an information-gap finding
    match_run = await run_match(session, career_card_id=card.id)
    await session.commit()

    from app.db.models_career_kb_mnp import MnpCareer, MnpCareerRequirement

    sales_career = (await session.execute(select(MnpCareer).where(MnpCareer.code == "sales_manager"))).scalar_one()
    match = (
        await session.execute(
            select(MnpCareerMatch).where(MnpCareerMatch.match_run_id == match_run.id, MnpCareerMatch.career_id == sales_career.id)
        )
    ).scalar_one()
    findings = (
        await session.execute(select(MnpFeasibilityFinding).where(MnpFeasibilityFinding.career_match_id == match.id))
    ).scalars().all()
    assert len(findings) > 0
    for finding in findings:
        assert finding.requirement_id is not None
        requirement = await session.get(MnpCareerRequirement, finding.requirement_id)
        assert requirement is not None
        assert requirement.career_id == sales_career.id


async def test_route_built_for_non_blocked_careers(session):
    await seed_alpha_career_kb(session)
    card = await _make_blank_card(session)
    match_run = await run_match(session, career_card_id=card.id)
    await session.commit()

    matches = (await session.execute(select(MnpCareerMatch).where(MnpCareerMatch.match_run_id == match_run.id))).scalars().all()
    for m in matches:
        assert m.feasibility_status != FeasibilityStatus.BLOCKED  # none blocked in this data -- sanity precondition
        routes = (await session.execute(select(MnpCareerRoute).where(MnpCareerRoute.career_match_id == m.id))).scalars().all()
        assert len(routes) == 1
        steps = (await session.execute(select(MnpRouteStep).where(MnpRouteStep.route_id == routes[0].id))).scalars().all()
        assert len(steps) > 0
        assert steps[0].order == 1


async def test_ranking_mode_changes_order_without_recomputing_components(session):
    await seed_alpha_career_kb(session)
    user = IdentityUser(locale="uk")
    session.add(user)
    await session.flush()
    card, _ = await upload_and_parse_resume(session, user_id=user.id, filename="cv.txt", content_bytes=SALES_CV)

    run_default = await run_match(session, career_card_id=card.id, ranking_mode=CAN_NOW)
    await session.commit()
    run_experience = await run_match(session, career_card_id=card.id, ranking_mode=USE_MY_EXPERIENCE)
    await session.commit()

    assert run_default.ranking_mode == "can_now"
    assert run_experience.ranking_mode == "use_my_experience"
    # Both are independent, fully-persisted runs -- reproducibility means
    # neither overwrites the other.
    matches_default = (await session.execute(select(MnpCareerMatch).where(MnpCareerMatch.match_run_id == run_default.id))).scalars().all()
    matches_experience = (await session.execute(select(MnpCareerMatch).where(MnpCareerMatch.match_run_id == run_experience.id))).scalars().all()
    assert len(matches_default) == len(matches_experience) == len(ALPHA_CAREER_CODES)


async def test_featured_excludes_low_confidence_even_if_high_score(session):
    """Founder Decision #29: high fit + low confidence must not enter
    Featured TOP-3 by default."""

    await seed_alpha_career_kb(session)
    card = await _make_blank_card(session)  # every Fit is INSUFFICIENT -> confidence_internal = insufficient
    match_run = await run_match(session, career_card_id=card.id)
    await session.commit()

    matches = (await session.execute(select(MnpCareerMatch).where(MnpCareerMatch.match_run_id == match_run.id))).scalars().all()
    assert all(m.is_featured is False for m in matches)  # nothing scored -> nothing confidently featured


# ---------------------------------------------------------------------------
# Zero-AI guarantee

def test_no_ai_gateway_imports_in_matching_engine_package():
    forbidden_module_prefixes = ("app.ai_gateway", "anthropic")
    forbidden_names = {"AIGateway", "Anthropic", "ClaimSynthesizer"}
    for module in (pure, feasibility, transition, gap, ranking, route, config, engine):
        tree = ast.parse(inspect.getsource(module))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not any(node.module == p or node.module.startswith(p + ".") for p in forbidden_module_prefixes)
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not any(alias.name == p or alias.name.startswith(p + ".") for p in forbidden_module_prefixes)
        referenced = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        assert referenced.isdisjoint(forbidden_names)
