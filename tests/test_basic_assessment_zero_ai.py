"""Matching V1 M1 -- zero-AI architectural guarantee (Founder Review test
item #19). Mirrors the AST-based import-inspection pattern already used
for the Direction Intelligence readmodel privacy guard
(tests/test_direction_readmodel.py) rather than a fragile substring scan.

If a future change accidentally imports `app.ai_gateway` (or any PRO
Hybrid AI-backed extraction/synthesis module) from anywhere under
`app/services/basic_assessment/` or `app/db/models_basic_assessment.py`,
this test fails the build."""

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


def _iter_basic_assessment_modules():
    import app.services.basic_assessment as pkg

    yield pkg
    for _, name, _ in pkgutil.iter_modules(pkg.__path__, pkg.__name__ + "."):
        yield importlib.import_module(name)

    import app.db.models_basic_assessment as models_pkg

    yield models_pkg


def test_no_ai_gateway_imports_in_basic_assessment_package():
    for module in _iter_basic_assessment_modules():
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


def test_no_ai_backed_class_names_referenced_in_basic_assessment_package():
    for module in _iter_basic_assessment_modules():
        tree = ast.parse(inspect.getsource(module))
        referenced_names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        referenced_names |= {
            alias.asname or alias.name for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) for alias in node.names
        }
        assert referenced_names.isdisjoint(FORBIDDEN_NAMES), (
            f"{module.__name__} references a forbidden AI-backed name: "
            f"{referenced_names & FORBIDDEN_NAMES}"
        )


async def test_full_basic_flow_makes_zero_ai_gateway_calls(session, monkeypatch):
    """Behavioral guard, not just static analysis: patch AIGateway.call_tool
    to raise if ever invoked, then drive a complete BASIC attempt
    end-to-end (seed -> start -> answer every item -> complete) and assert
    it never fires."""

    from app.ai_gateway import AIGateway

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("AIGateway.call_tool was invoked from a BASIC_STRUCTURED code path")

    monkeypatch.setattr(AIGateway, "call_tool", _fail_if_called)

    from sqlalchemy import select

    from app.db.models_identity import IdentityUser
    from app.services.basic_assessment.attempts import complete_attempt, get_or_create_active_attempt, submit_answer
    from app.services.basic_assessment.definitions import get_active_items
    from app.services.basic_assessment.seed import seed_alpha_long_form
    from app.db.models_basic_assessment import AssessmentItemOption, ResponseType

    definition = await seed_alpha_long_form(session)
    user = IdentityUser()
    session.add(user)
    await session.flush()

    attempt = await get_or_create_active_attempt(session, user_id=user.id, definition=definition)
    items = await get_active_items(session, definition)

    for idx, item in enumerate(items):
        if item.response_type == ResponseType.LIKERT_5:
            await submit_answer(session, attempt=attempt, item=item, idempotency_key=f"i{idx}", numeric_value=3)
        elif item.response_type == ResponseType.BOOLEAN:
            await submit_answer(session, attempt=attempt, item=item, idempotency_key=f"i{idx}", boolean_value=True)
        elif item.response_type in (ResponseType.SINGLE_CHOICE, ResponseType.MULTI_CHOICE):
            options = (
                await session.execute(select(AssessmentItemOption).where(AssessmentItemOption.item_id == item.id))
            ).scalars().all()
            option_key = options[0].option_key
            await submit_answer(
                session, attempt=attempt, item=item, idempotency_key=f"i{idx}", selected_option_keys=[option_key]
            )
        elif item.response_type == ResponseType.NUMERIC:
            await submit_answer(session, attempt=attempt, item=item, idempotency_key=f"i{idx}", numeric_value=1)

    await complete_attempt(session, attempt)
    await session.commit()
    assert attempt.status.value == "completed"
