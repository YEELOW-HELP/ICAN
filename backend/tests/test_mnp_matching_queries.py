"""MNP V1 BLOCK D -- results/compatibility read-contract tests."""

import uuid

from app.db.models_career_card import EntryMode, SourceMode
from app.db.models_identity import IdentityUser
from app.services.career_card_mnp.card import get_or_create_career_card, start_assessment_session
from app.services.career_kb_mnp.seed_alpha import ALPHA_CAREER_CODES, seed_alpha_career_kb
from app.services.matching_mnp.engine import run_match
from app.services.matching_mnp.queries import get_career_compatibility, get_match_run_results
from app.services.resume_parser_mnp.parser import upload_and_parse_resume

SALES_CV = (
    "Досвід роботи\n01.2020 - теперішній час\nМенеджер з продажу\n"
    "Веде переговори з клієнтами, керував командою з 4 осіб\n\nНавички\nПереговори, CRM, Excel\n"
).encode("utf-8")


async def test_match_run_results_view_assembled_correctly(session):
    await seed_alpha_career_kb(session)
    user = IdentityUser(locale="uk")
    session.add(user)
    await session.flush()
    card, _ = await upload_and_parse_resume(session, user_id=user.id, filename="cv.txt", content_bytes=SALES_CV)
    match_run = await run_match(session, career_card_id=card.id)
    await session.commit()

    results = await get_match_run_results(session, match_run.id)
    assert len(results.ranked_top10) <= 10
    assert len(results.ranked_top10) == len(ALPHA_CAREER_CODES)  # none blocked in this data
    assert results.blocked == []
    codes = [c.career_code for c in results.ranked_top10]
    assert codes[0] == "sales_manager"


async def test_career_compatibility_view_includes_gaps_and_route(session):
    await seed_alpha_career_kb(session)
    user = IdentityUser(locale="uk")
    session.add(user)
    await session.flush()
    s = await start_assessment_session(session, user_id=user.id, entry_mode=EntryMode.MANUAL)
    card = await get_or_create_career_card(session, user_id=user.id, assessment_session_id=s.id, source_mode=SourceMode.MANUAL)
    await session.commit()
    match_run = await run_match(session, career_card_id=card.id)
    await session.commit()

    results = await get_match_run_results(session, match_run.id)
    sales_summary = next(c for c in results.ranked_top10 if c.career_code == "sales_manager")

    view = await get_career_compatibility(session, sales_summary.career_match_id)
    assert view.career_code == "sales_manager"
    assert view.market_data_limited is True
    assert len(view.gaps) > 0  # blank card -> every skill requirement is a gap
    assert view.route_type in ("safe", "growth", "transform")
    assert len(view.route_steps) > 0


async def test_matched_skill_labels_are_real_names_not_ids(session):
    """The component's `detail["matched"]` list stores skill_id strings
    internally -- the read contract must resolve them to real Ukrainian
    names before a screen ever sees them."""

    await seed_alpha_career_kb(session)
    user = IdentityUser(locale="uk")
    session.add(user)
    await session.flush()
    card, _ = await upload_and_parse_resume(session, user_id=user.id, filename="cv.txt", content_bytes=SALES_CV)
    match_run = await run_match(session, career_card_id=card.id)
    await session.commit()

    results = await get_match_run_results(session, match_run.id)
    sales_summary = next(c for c in results.ranked_top10 if c.career_code == "sales_manager")
    view = await get_career_compatibility(session, sales_summary.career_match_id)

    assert view.matched_skill_labels  # the sample CV includes real matched skills
    for label in view.matched_skill_labels:
        try:
            uuid.UUID(label)
        except ValueError:
            pass  # expected -- a real label is not a parseable UUID
        else:
            assert False, f"matched_skill_labels leaked a raw skill_id: {label!r}"
    assert view.route_steps[0].order == 1
