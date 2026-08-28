"""Matching V1 M3 -- Work.ua binding rule, zero-AI, offline-fixture
guarantees (Founder Review test items #18, #27, #28, #29)."""

import ast
import importlib
import inspect
import pkgutil

FORBIDDEN_MODULE_PREFIXES = ("app.ai_gateway",)
FORBIDDEN_NAMES = {"AIGateway", "AnswerExtractor", "EvidenceExtractor", "ClaimSynthesizer", "Summarizer"}
# Concrete scraping/import artifacts -- deliberately NOT the bare string
# "work.ua", since that phrase legitimately appears in compliance-
# documentation comments/docstrings explaining that Work.ua is excluded.
FORBIDDEN_WORKUA_ARTIFACTS = (
    "workua.com", "requests.get(", "requests.post(", "beautifulsoup", "scrapy", "selenium", "bs4",
)


def _iter_career_kb_modules():
    import app.services.career_kb as pkg

    yield pkg
    for _, name, _ in pkgutil.iter_modules(pkg.__path__, pkg.__name__ + "."):
        yield importlib.import_module(name)

    import app.db.models_career_kb as models_pkg

    yield models_pkg


def test_no_ai_gateway_imports_in_career_kb_package():
    """#18 (no AI vector creation)."""
    for module in _iter_career_kb_modules():
        tree = ast.parse(inspect.getsource(module))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not any(
                    node.module == prefix or node.module.startswith(prefix + ".") for prefix in FORBIDDEN_MODULE_PREFIXES
                ), f"{module.__name__} imports forbidden module {node.module!r}"
        referenced_names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        assert referenced_names.isdisjoint(FORBIDDEN_NAMES), f"{module.__name__} references {referenced_names & FORBIDDEN_NAMES}"


def test_no_workua_scraper_or_import_exists():
    """#27 -- no module anywhere under app.services.career_kb contains a
    Work.ua scraper/importer artifact. (Mentioning "Work.ua" in a
    docstring to document that it is deliberately excluded is fine and
    expected -- see e.g. models_career_kb.py's ExternalSourceSystem
    docstring; this test flags actual scraping code, not that comment.)"""
    for module in _iter_career_kb_modules():
        source = inspect.getsource(module).lower()
        for token in FORBIDDEN_WORKUA_ARTIFACTS:
            assert token not in source, f"{module.__name__} contains a forbidden scraping artifact ({token!r})"


async def test_no_workua_market_data_stored(session):
    """#28 -- the Alpha seed creates zero CareerFact rows with
    is_market_sensitive=True, and its one KnowledgeSource is O*NET, not
    Work.ua."""
    from sqlalchemy import select

    from app.db.models_knowledge import CareerFact, KnowledgeSource
    from app.services.career_kb.seed import seed_alpha_career_matching_profiles

    await seed_alpha_career_matching_profiles(session)
    await session.commit()

    sources = (await session.execute(select(KnowledgeSource))).scalars().all()
    onet_sources = [s for s in sources if s.publisher == "O*NET"]
    assert onet_sources
    assert all(s.publisher != "Work.ua" for s in sources)

    market_facts = (
        (await session.execute(select(CareerFact).where(CareerFact.is_market_sensitive.is_(True)))).scalars().all()
    )
    assert market_facts == []  # M3 creates zero market-sensitive facts


async def test_offline_fixture_requires_no_network(session):
    """#29 -- the entire Alpha seed runs from `load_onet_source()`'s
    in-memory fixture; sanity-check that the fixture module makes no HTTP
    client calls."""
    import inspect as _inspect

    import app.services.career_kb.onet_alpha_fixture as fixture_module

    source = _inspect.getsource(fixture_module)
    for forbidden in ("requests.", "httpx.", "urllib.request", "aiohttp."):
        assert forbidden not in source

    # And the actual seed runs to completion with no network access needed --
    # already proven by every other test in this suite using the plain
    # in-memory sqlite `session` fixture with no network mocking required.
    from app.services.career_kb.seed import seed_alpha_career_matching_profiles

    profiles = await seed_alpha_career_matching_profiles(session)
    await session.commit()
    assert profiles
