"""Matching V1 M2 -- zero-AI architectural guarantee (Founder Review test
item #26), same pattern as M1's test_basic_assessment_zero_ai.py."""

import ast
import importlib
import inspect
import pkgutil

FORBIDDEN_MODULE_PREFIXES = (
    "app.ai_gateway",
    "app.services.assessment.extraction",
    "app.services.assessment.cv",
    "app.services.assessment.next_question",
)
FORBIDDEN_NAMES = {
    "AIGateway",
    "AnswerExtractor",
    "EvidenceExtractor",
    "ClaimSynthesizer",
    "Summarizer",
}


def _iter_basic_profile_modules():
    import app.services.basic_profile as pkg

    yield pkg
    for _, name, _ in pkgutil.iter_modules(pkg.__path__, pkg.__name__ + "."):
        yield importlib.import_module(name)

    import app.db.models_basic_profile as models_pkg

    yield models_pkg


def test_no_ai_gateway_imports_in_basic_profile_package():
    for module in _iter_basic_profile_modules():
        tree = ast.parse(inspect.getsource(module))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not any(
                    node.module == prefix or node.module.startswith(prefix + ".")
                    for prefix in FORBIDDEN_MODULE_PREFIXES
                ), f"{module.__name__} imports forbidden module {node.module!r}"
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not any(
                        alias.name == prefix or alias.name.startswith(prefix + ".")
                        for prefix in FORBIDDEN_MODULE_PREFIXES
                    ), f"{module.__name__} imports forbidden module {alias.name!r}"


def test_no_ai_backed_class_names_referenced_in_basic_profile_package():
    for module in _iter_basic_profile_modules():
        tree = ast.parse(inspect.getsource(module))
        referenced_names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        referenced_names |= {
            alias.asname or alias.name for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) for alias in node.names
        }
        assert referenced_names.isdisjoint(FORBIDDEN_NAMES), (
            f"{module.__name__} references a forbidden AI-backed name: {referenced_names & FORBIDDEN_NAMES}"
        )


async def test_full_profile_calculation_makes_zero_ai_gateway_calls(session, monkeypatch):
    """Behavioral guard: patch AIGateway.call_tool to raise if ever
    invoked, then calculate a full, real 75-answer profile end-to-end. The
    calculation must still complete."""

    from app.ai_gateway import AIGateway

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("AIGateway.call_tool was invoked from a BASIC profile calculation path")

    monkeypatch.setattr(AIGateway, "call_tool", _fail_if_called)

    from app.services.basic_assessment.attempts import complete_attempt
    from app.services.basic_assessment.seed import seed_alpha_long_form
    from app.services.basic_profile.calculation import calculate_basic_profile
    from tests.helpers_basic_profile import answer_all_items

    definition = await seed_alpha_long_form(session)
    attempt, _user = await answer_all_items(session, definition)
    await complete_attempt(session, attempt)
    await session.commit()

    profile = await calculate_basic_profile(session, attempt)
    await session.commit()

    assert profile.status.value == "ready"
