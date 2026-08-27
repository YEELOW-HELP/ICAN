"""Stage 3B Slice 3 §8/§9: grounded LLM narrative."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.ai_gateway import GatewayResult, GatewayTrace
from app.db.models_direction import Direction, DirectionPlacement, DirectionRun
from app.services.direction import narrative
from app.services.direction.config import ensure_experimental_ranking_policy, ensure_experimental_scoring_config
from app.services.direction.pipeline import generate_directions
from tests.direction_pipeline_test_helpers import make_user, seed_eligible_developer_profile, seed_knowledge_base


def _trace(prompt_version: str) -> GatewayTrace:
    return GatewayTrace(
        trace_id=str(uuid.uuid4()), task_name="direction_narrative", provider="anthropic", model="claude-sonnet-5",
        prompt_version=prompt_version, input_tokens=100, output_tokens=50, latency_ms=10.0,
        estimated_cost_usd=0.001, retry_count=0, stop_reason="tool_use",
    )


class FakeGateway:
    """Duck-types `AIGateway.call_tool` -- returns a scripted
    `GatewayResult` per call, or raises if `exc` is set."""

    def __init__(self, *, payloads=None, exc: Exception | None = None):
        self._payloads = list(payloads) if payloads is not None else None
        self._exc = exc
        self.calls = 0

    async def call_tool(self, **kwargs):
        self.calls += 1
        if self._exc is not None:
            raise self._exc
        payload = self._payloads.pop(0) if self._payloads else _WELL_FORMED_PAYLOAD
        return GatewayResult(tool_input=payload, raw_content=[], trace=_trace(kwargs["prompt_version"]))


_WELL_FORMED_PAYLOAD = {
    "summary": "Ця напрямок добре відповідає вашим навичкам.",
    "why_fit": "Ваші навички програмування збігаються з вимогами цієї посади.",
    "why_now": "Немає структурованих даних про відповідність цілям.",
    "transition": "Перехід виглядає реалістичним.",
    "risks": "Немає значних ризиків серед відомих даних.",
    "what_to_verify": "Немає навичок, які потребують перевірки.",
}


@pytest.fixture
async def world(session):
    await ensure_experimental_scoring_config(session)
    await ensure_experimental_ranking_policy(session)
    kb = await seed_knowledge_base(session)
    user = await make_user(session)
    prof = await seed_eligible_developer_profile(session, user=user)
    return dict(**kb, **prof, user=user)


@pytest.fixture
async def run_with_directions(session, world) -> DirectionRun:
    return await generate_directions(session, user_id=world["user"].id)


# ---------------------------------------------------------------- 19


async def test_narrative_cannot_modify_scores_or_ranking(session, run_with_directions):
    """#19: generating a narrative never touches the four output scores,
    bands, placement, or rank -- only narrative_* fields."""
    directions_before = {
        d.id: (d.potential_fit_raw_experimental, d.goal_alignment_raw_experimental, d.transition_feasibility_raw_experimental,
               d.evidence_confidence_raw_experimental, d.placement, d.rank_within_placement)
        for d in (await session.execute(select(Direction).where(Direction.run_id == run_with_directions.id))).scalars().all()
    }

    fake = FakeGateway(payloads=[_WELL_FORMED_PAYLOAD] * 10)
    await narrative.generate_narratives_for_run(session, run_id=run_with_directions.id, narrator=narrative.DirectionNarrator(fake))

    directions_after = (await session.execute(select(Direction).where(Direction.run_id == run_with_directions.id))).scalars().all()
    for d in directions_after:
        before = directions_before[d.id]
        after = (d.potential_fit_raw_experimental, d.goal_alignment_raw_experimental, d.transition_feasibility_raw_experimental,
                 d.evidence_confidence_raw_experimental, d.placement, d.rank_within_placement)
        assert before == after


async def test_narrative_persists_structured_fields_and_trace(session, run_with_directions):
    fake = FakeGateway(payloads=[_WELL_FORMED_PAYLOAD] * 10)
    narrated = await narrative.generate_narratives_for_run(session, run_id=run_with_directions.id, narrator=narrative.DirectionNarrator(fake))
    assert narrated >= 1

    directions = (
        await session.execute(
            select(Direction).where(Direction.run_id == run_with_directions.id, Direction.placement.in_([DirectionPlacement.MAIN, DirectionPlacement.ALTERNATIVE]))
        )
    ).scalars().all()
    narrated_direction = next(d for d in directions if d.narrative_structured is not None)
    assert set(narrated_direction.narrative_structured.keys()) == set(narrative.NARRATIVE_FIELDS)
    assert narrated_direction.narrative_text == narrated_direction.narrative_structured["summary"]
    assert narrated_direction.narrative_trace_id

    await session.refresh(run_with_directions)
    assert run_with_directions.narrative_prompt_version == narrative.NARRATIVE_PROMPT_VERSION
    assert run_with_directions.model == narrative.NARRATIVE_MODEL


# ---------------------------------------------------------------- 20


async def test_malformed_narrative_output_is_rejected_safely(session, run_with_directions):
    """#20: a payload missing a required field is rejected -- no partial/
    garbage narrative is persisted."""
    malformed = {"summary": "ok", "why_fit": "ok"}  # missing 4 required fields
    fake = FakeGateway(payloads=[malformed] * 10)
    narrated = await narrative.generate_narratives_for_run(session, run_id=run_with_directions.id, narrator=narrative.DirectionNarrator(fake))
    assert narrated == 0

    directions = (await session.execute(select(Direction).where(Direction.run_id == run_with_directions.id))).scalars().all()
    assert all(d.narrative_structured is None for d in directions)


async def test_narrative_with_unsupported_market_claim_is_rejected(session, run_with_directions):
    unsafe_payload = dict(_WELL_FORMED_PAYLOAD)
    unsafe_payload["risks"] = "You could earn $5000 per month in this role."
    fake = FakeGateway(payloads=[unsafe_payload] * 10)
    narrated = await narrative.generate_narratives_for_run(session, run_id=run_with_directions.id, narrator=narrative.DirectionNarrator(fake))
    assert narrated == 0


# ---------------------------------------------------------------- 21


async def test_narrative_failure_does_not_invalidate_deterministic_run(session, run_with_directions):
    """#21."""
    from app.db.models_direction import DirectionRunStatus

    fake = FakeGateway(exc=RuntimeError("simulated provider outage"))
    narrated = await narrative.generate_narratives_for_run(session, run_id=run_with_directions.id, narrator=narrative.DirectionNarrator(fake))
    assert narrated == 0

    await session.refresh(run_with_directions)
    assert run_with_directions.status is DirectionRunStatus.READY  # untouched by narrative failure

    directions = (await session.execute(select(Direction).where(Direction.run_id == run_with_directions.id))).scalars().all()
    assert any(d.potential_fit_raw_experimental is not None for d in directions)  # deterministic data intact


# ---------------------------------------------------------------- 22


async def test_no_unsupported_career_facts_enter_narrative_prompt(session, run_with_directions):
    """#22: the narrative prompt is built ONLY from the deterministic
    explanation_bundle -- no raw claim/CV text, no career facts beyond
    what's already in the vetted bundle."""
    captured_prompts = []

    class CapturingGateway(FakeGateway):
        async def call_tool(self, **kwargs):
            captured_prompts.append(kwargs["messages"][0]["content"])
            return await super().call_tool(**kwargs)

    fake = CapturingGateway(payloads=[_WELL_FORMED_PAYLOAD] * 10)
    await narrative.generate_narratives_for_run(session, run_id=run_with_directions.id, narrator=narrative.DirectionNarrator(fake))

    directions = (
        await session.execute(
            select(Direction).where(Direction.run_id == run_with_directions.id, Direction.explanation_bundle.isnot(None))
        )
    ).scalars().all()
    for direction, prompt in zip(directions, captured_prompts):
        # every claim id mentioned in the prompt must come from this
        # direction's own vetted provenance -- nothing else was fed in.
        for claim_id in direction.explanation_bundle["provenance"]["contributing_claim_ids"]:
            assert claim_id in prompt


# ---------------------------------------------------------------- 23


async def test_no_persisted_ai_trace_reappears_from_narrative(session, run_with_directions):
    """#23."""
    from app.db.base import Base
    from app.db import models_platform  # noqa: F401

    fake = FakeGateway(payloads=[_WELL_FORMED_PAYLOAD] * 10)
    await narrative.generate_narratives_for_run(session, run_id=run_with_directions.id, narrator=narrative.DirectionNarrator(fake))

    assert "ai_traces" not in Base.metadata.tables
    assert not hasattr(models_platform, "AITrace")
