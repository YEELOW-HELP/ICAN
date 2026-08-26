"""Turns one free-text answer into a structured (value, confidence,
contradiction) triple, via the existing AI Gateway -- never a direct
provider call (docs/architecture/04_AI_SYSTEM.md's non-negotiable rule,
already respected by app/ai_gateway.py). This is a *new* task
(`hybrid_answer_extraction`), tagged with its own prompt version
(`hybrid-assessment-v1`), distinct from legacy screening's
`legacy-screening-v1` -- the two must stay independently comparable/
evaluable, not silently merged.

Structured (fixed-choice) questions never reach this module at all --
see app/services/assessment/sessions.py, which resolves them
deterministically from the chosen option with zero LLM cost, exactly like
today's ICAN 1.1 Structured-mode philosophy.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.ai_gateway import AIGateway

PROMPT_VERSION = "hybrid-assessment-v1"
EXTRACTION_MODEL = "claude-sonnet-5"

_SYSTEM_PROMPT = """\
You extract one specific fact from a job/career-assessment candidate's answer \
to a single question. You do not conduct the interview and you do not decide \
what to ask next -- only extract from the text given to you.

Rules (do not break these):
- Extract ONLY what the candidate actually stated. Never guess, infer, or \
embellish beyond the literal content of their answer.
- `confidence` reflects how clearly and unambiguously the answer addresses \
the question -- low confidence for vague, evasive, or off-topic answers, \
not for how interesting or detailed the answer is.
- `contradicts_previous` is true only if a previously known value is given \
and the new answer genuinely conflicts with it (not just adds detail).
- You must always respond by calling the `extract_answer` tool -- never plain text.
"""

EXTRACTION_TOOL_SCHEMA = {
    "name": "extract_answer",
    "description": "Extract a structured value, a confidence score, and a contradiction flag from one candidate answer to one specific question.",
    "input_schema": {
        "type": "object",
        "properties": {
            "extracted_value": {
                "type": "string",
                "description": "The fact as literally stated by the candidate, normalized for readability but not embellished.",
            },
            "confidence": {
                "type": "number",
                "description": "0.0-1.0: how clearly and unambiguously this answer addresses the question.",
            },
            "contradicts_previous": {
                "type": "boolean",
                "description": "True only if a previously known value was provided and this answer genuinely conflicts with it.",
            },
        },
        "required": ["extracted_value", "confidence", "contradicts_previous"],
    },
}


@dataclass(frozen=True)
class ExtractionResult:
    extracted_value: str
    confidence: float
    contradicts_previous: bool


class AnswerExtractor:
    """Holds no provider client itself -- all calls go through the AI
    Gateway, same discipline as app/services/screening.py's ScreeningAgent."""

    def __init__(self, gateway: AIGateway | None = None) -> None:
        self._gateway = gateway or AIGateway()

    async def extract(
        self,
        *,
        question_prompt: str,
        raw_answer_text: str,
        previous_value: str | None,
    ) -> ExtractionResult:
        context_lines = [f"Question asked: {question_prompt}", f"Candidate's answer: {raw_answer_text}"]
        if previous_value is not None:
            context_lines.append(f"Previously known value for this question (if any): {previous_value}")

        result = await self._gateway.call_tool(
            task_name="hybrid_answer_extraction",
            prompt_version=PROMPT_VERSION,
            model=EXTRACTION_MODEL,
            system=_SYSTEM_PROMPT,
            tools=[EXTRACTION_TOOL_SCHEMA],
            tool_choice={"type": "tool", "name": "extract_answer"},
            max_tokens=1024,
            messages=[{"role": "user", "content": "\n".join(context_lines)}],
        )

        payload = result.tool_input or {}
        return ExtractionResult(
            extracted_value=payload.get("extracted_value") or raw_answer_text,
            confidence=float(payload.get("confidence", 0.0) or 0.0),
            contradicts_previous=bool(payload.get("contradicts_previous", False)),
        )
