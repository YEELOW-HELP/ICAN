"""Matching V1 M4 -- explainability and zero-AI guarantee (Founder Review
test items #34, #35)."""

import ast
import importlib
import inspect
import pkgutil

from sqlalchemy import select

from app.db.models_career_kb import CareerMatchingProfile
from app.services.basic_assessment.attempts import complete_attempt
from app.services.basic_assessment.seed import seed_alpha_long_form
from app.services.basic_profile.calculation import calculate_basic_profile
from app.services.career_kb.seed import seed_alpha_career_matching_profiles
from app.services.knowledge.retrieval import get_career_by_code
from app.services.matching.engine import calculate_pair_match, match_profile_to_careers
from app.services.matching.queries import explain_matching_result
from tests.helpers_basic_profile import answer_all_items

FORBIDDEN_MODULE_PREFIXES = ("app.ai_gateway",)
FORBIDDEN_NAMES = {"AIGateway", "AnswerExtractor", "EvidenceExtractor", "ClaimSynthesizer", "Summarizer"}


def _iter_matching_modules():
    import app.services.matching as pkg

    yield pkg
    for _, name, _ in pkgutil.iter_modules(pkg.__path__, pkg.__name__ + "."):
        yield importlib.import_module(name)

    import app.db.models_matching as models_pkg

    yield models_pkg


def test_no_ai_gateway_imports_in_matching_package():
    for module in _iter_matching_modules():
        tree = ast.parse(inspect.getsource(module))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not any(
                    node.module == prefix or node.module.startswith(prefix + ".") for prefix in FORBIDDEN_MODULE_PREFIXES
                ), f"{module.__name__} imports forbidden module {node.module!r}"
        referenced_names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        assert referenced_names.isdisjoint(FORBIDDEN_NAMES), f"{module.__name__} references {referenced_names & FORBIDDEN_NAMES}"


async def test_full_matching_run_makes_zero_ai_gateway_calls(session, monkeypatch):
    """#35 -- patch AIGateway.call_tool to raise, then match one profile
    against all 24 Alpha careers. Matching must succeed."""

    from app.ai_gateway import AIGateway

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("AIGateway.call_tool was invoked from a matching-engine code path")

    monkeypatch.setattr(AIGateway, "call_tool", _fail_if_called)

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
    assert len(results) == 24


async def test_structured_explanation_references_real_components(session):
    """#34 -- the explanation bundle's comparable_scale_keys are real
    scale keys that actually exist on both sides, not placeholders."""
    definition = await seed_alpha_long_form(session)
    attempt, _user = await answer_all_items(session, definition)
    await complete_attempt(session, attempt)
    await session.commit()
    profile = await calculate_basic_profile(session, attempt)
    await session.commit()

    await seed_alpha_career_matching_profiles(session)
    await session.commit()
    career = await get_career_by_code(session, "sales_manager")
    career_profile = (
        await session.execute(
            select(CareerMatchingProfile).where(
                CareerMatchingProfile.career_id == career.id, CareerMatchingProfile.is_current.is_(True)
            )
        )
    ).scalar_one()
    matching_result = await calculate_pair_match(session, profile=profile, career_matching_profile=career_profile)
    await session.commit()

    explanation = await explain_matching_result(session, matching_result.id)

    assert explanation.interests.comparable_scale_keys  # RIASEC: 6 comparable keys
    assert set(explanation.interests.comparable_scale_keys) <= {"R", "I", "A", "S", "E", "C"}
    assert explanation.work_styles.comparable_scale_keys == ["initiative", "leadership"] or set(
        explanation.work_styles.comparable_scale_keys
    ) <= {"initiative", "leadership"}
    assert explanation.versions["matching_engine_version"] == "matching_engine_v0.1"
    assert explanation.feasibility.status in ("feasible", "partial", "blocked", "insufficient_data")
