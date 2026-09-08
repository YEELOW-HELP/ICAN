"""MNP V1 BLOCK C groundwork -- job title normalization via
MnpCareerAlias, feeding Experience Transfer's domain-proximity signal."""

from app.services.career_kb_mnp.alias_resolution import resolve_job_title_to_career
from app.services.career_kb_mnp.seed_alpha import seed_alpha_career_kb


async def test_resolves_seeded_alias_exact_match(session):
    await seed_alpha_career_kb(session)
    career = await resolve_job_title_to_career(session, "Менеджер з продажу")
    assert career is not None
    assert career.code == "sales_manager"


async def test_resolves_case_and_whitespace_insensitive(session):
    await seed_alpha_career_kb(session)
    career = await resolve_job_title_to_career(session, "  менеджер З продажу  ")
    assert career is not None
    assert career.code == "sales_manager"


async def test_unresolvable_title_returns_none_not_a_guess(session):
    await seed_alpha_career_kb(session)
    career = await resolve_job_title_to_career(session, "Абсолютно унікальна назва посади")
    assert career is None
