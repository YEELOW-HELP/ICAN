"""Stage 3B Slice 3 §8/§9: grounded LLM narrative -- MVP.

Uses `AIGateway` only (the single seam every LLM call in this codebase
goes through). Input is ONLY the deterministic `Direction.explanation_bundle`
built in Slice 2 -- never raw CV/assessment-answer text, never a raw
`ProfileClaim`/`Evidence` row. The bundle already contains nothing but
IDs, bands, rationale strings, and counts (see
`app/services/direction/pipeline.py::_build_explanation_bundle`), so
there is no channel for PII to reach this prompt at all.

The LLM may rewrite structured reasoning into clear text, summarize fit,
explain trade-offs/uncertainty. It may NOT invent career facts, invent
claims/evidence, change scores/ranking, create new careers, or make
salary/market claims -- enforced structurally (the tool schema has no
field for a score or a career name the model could invent its way around)
and, for the salary/market case specifically, by a deterministic
post-generation safety check (`_contains_unsupported_market_claim`) since
free-text fields cannot otherwise be constrained by JSON schema alone.

A malformed or unsafe response is rejected -- the deterministic
`DirectionRun`/`Direction` remain fully valid for consultant review either
way; narrative is a pure add-on, never load-bearing for the backend
result. No persisted `AI_TRACE` is introduced here -- only the existing
`Direction.narrative_trace_id` string and `DirectionRun.narrative_prompt_version`/
`DirectionRun.model` columns (already present since Slice 1).
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_gateway import AIGateway
from app.db.models_direction import Direction, DirectionPlacement, DirectionRun
from app.services.events import emit_event

__all__ = [
    "NARRATIVE_PROMPT_VERSION",
    "NARRATIVE_MODEL",
    "NARRATIVE_FIELDS",
    "NarrativeResult",
    "DirectionNarrator",
    "generate_narratives_for_run",
]

NARRATIVE_PROMPT_VERSION = "direction-narrative-v0.1"
NARRATIVE_MODEL = "claude-sonnet-5"

NARRATIVE_FIELDS: tuple[str, ...] = ("summary", "why_fit", "why_now", "transition", "risks", "what_to_verify")

# A crude but deterministic safety net for "no salary/market claims
# without sourced KB facts" -- the explanation_bundle this prompt is built
# from never contains salary/market data at all in Slice 2/3, so ANY such
# mention in the model's output is by definition unsupported.
_MARKET_CLAIM_PATTERN = re.compile(
    r"(\$|€|₴|\bUSD\b|\bEUR\b|\bUAH\b)|(\bsalary\b|\bзарплат\w*|\bдохід\w*|\bдоход\w*|\bincome\b).{0,20}\d",
    re.IGNORECASE,
)

_SYSTEM_PROMPT = """\
You rewrite ALREADY-DECIDED structured career-direction reasoning into \
clear, honest, second-person text. You are a presentation layer, not a \
decision-maker.

Rules (do not break these):
- Use ONLY the structured data given to you (bands, rationale strings, \
gap/skills-to-verify lists, trade-off notes). Never add a fact, claim, \
skill, requirement, or piece of evidence that isn't in the data.
- Never invent or imply a salary, wage, market-demand, or hiring-outlook \
figure -- none of that data is given to you, so you have no basis for it.
- Never invent a new career, career code, or company/employer.
- Never state or imply a numeric score, percentage, or rank -- only the \
qualitative bands (LOW/MEDIUM/HIGH) already given to you.
- If a section has no real underlying data (e.g. no Goal Alignment \
signal), say so honestly and briefly rather than inventing content.
- Write in Ukrainian, in second person, addressed to the candidate directly.
- You must always respond by calling the `write_direction_narrative` tool \
-- never plain text.
"""

_TOOL_SCHEMA = {
    "name": "write_direction_narrative",
    "description": "Write the structured, user-friendly narrative for one career direction.",
    "input_schema": {
        "type": "object",
        "properties": {field: {"type": "string"} for field in NARRATIVE_FIELDS},
        "required": list(NARRATIVE_FIELDS),
    },
}


@dataclass(frozen=True)
class NarrativeResult:
    structured: dict[str, str]
    trace_id: str
    model: str
    prompt_version: str


def _contains_unsupported_market_claim(structured: dict[str, str]) -> bool:
    return any(_MARKET_CLAIM_PATTERN.search(text) for text in structured.values())


def _is_well_formed(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    for field in NARRATIVE_FIELDS:
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            return False
    return True


class DirectionNarrator:
    def __init__(self, gateway: AIGateway | None = None) -> None:
        self._gateway = gateway or AIGateway()

    async def narrate(self, *, explanation_bundle: dict, career_title: str, locale: str = "uk") -> NarrativeResult | None:
        """Returns `None` (never raises for a malformed/unsafe LLM
        response) so the caller can leave the Direction's narrative fields
        untouched and move on -- narrative failure never invalidates the
        deterministic run."""
        import json

        prompt = (
            f"Career: {career_title}\n\nStructured explanation data (JSON, already vetted -- "
            f"use ONLY this):\n{json.dumps(explanation_bundle, default=str, ensure_ascii=False)}"
        )

        result = await self._gateway.call_tool(
            task_name="direction_narrative",
            prompt_version=NARRATIVE_PROMPT_VERSION,
            model=NARRATIVE_MODEL,
            system=_SYSTEM_PROMPT,
            tools=[_TOOL_SCHEMA],
            tool_choice={"type": "tool", "name": "write_direction_narrative"},
            max_tokens=1536,
            messages=[{"role": "user", "content": prompt}],
        )
        payload = result.tool_input
        if not _is_well_formed(payload):
            return None
        structured = {field: payload[field].strip() for field in NARRATIVE_FIELDS}
        if _contains_unsupported_market_claim(structured):
            return None
        return NarrativeResult(
            structured=structured, trace_id=result.trace.trace_id, model=NARRATIVE_MODEL, prompt_version=NARRATIVE_PROMPT_VERSION
        )


async def generate_narratives_for_run(
    session: AsyncSession, *, run_id: uuid.UUID, narrator: DirectionNarrator | None = None, locale: str = "uk"
) -> int:
    """Generates a narrative for every MAIN/ALTERNATIVE Direction in the
    run that has an `explanation_bundle` (Slice 2 only builds one for
    those placements). Per-direction failures are isolated -- one
    direction's narrative failing never stops the others or invalidates
    the deterministic run. Returns the count of directions successfully
    narrated."""
    narrator = narrator or DirectionNarrator()
    run = await session.get(DirectionRun, run_id)
    directions = (
        await session.execute(
            select(Direction).where(
                Direction.run_id == run_id, Direction.placement.in_([DirectionPlacement.MAIN, DirectionPlacement.ALTERNATIVE])
            )
        )
    ).scalars().all()

    narrated = 0
    for direction in directions:
        if not direction.explanation_bundle:
            continue
        try:
            result = await narrator.narrate(
                explanation_bundle=direction.explanation_bundle, career_title=direction.career_code, locale=locale
            )
        except Exception as exc:
            emit_event(
                "direction_narrative_failed", run_id=str(run_id), direction_id=str(direction.id), error_type=type(exc).__name__,
            )
            continue

        if result is None:
            emit_event(
                "direction_narrative_failed", run_id=str(run_id), direction_id=str(direction.id), error_type="malformed_or_unsafe_output",
            )
            continue

        direction.narrative_structured = result.structured
        direction.narrative_text = result.structured["summary"]
        direction.narrative_locale = locale
        direction.narrative_trace_id = result.trace_id
        narrated += 1
        emit_event(
            "direction_narrative_generated", run_id=str(run_id), direction_id=str(direction.id), trace_id=result.trace_id,
        )

    if narrated and run is not None:
        run.narrative_prompt_version = NARRATIVE_PROMPT_VERSION
        run.model = NARRATIVE_MODEL
    await session.commit()
    return narrated
