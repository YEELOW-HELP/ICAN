"""AI System component 2, "Evidence Extractor" (docs/architecture/04_AI_SYSTEM.md).
Turns one open-text answer (or CV-derived answer) into zero or more
normalized Evidence *observations* -- deliberately not the single-value
extraction Stage 1's `AnswerExtractor` already does. One raw answer can
carry several distinct signals (Stage 2 brief §17's example: "I've always
enjoyed organizing events" -> enjoys coordination + has event-organization
experience + prefers people-facing activity), so this is a genuinely
richer pass over the same raw text, via its own AI Gateway task
(`evidence_extraction`, not `hybrid_answer_extraction`).

Structured (fixed-choice) answers never reach this module -- see
app/services/profile/generation.py, which builds their Evidence
deterministically (near-zero cost, same philosophy as Stage 1's
structured questions).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.ai_gateway import AIGateway

PROMPT_VERSION = "evidence-extraction-v1"
EXTRACTION_MODEL = "claude-sonnet-5"
MAX_EVIDENCE_ITEMS_PER_ANSWER = 5

_SYSTEM_PROMPT = """\
You extract normalized evidence observations from one candidate's answer \
in a career-assessment interview. You do not conduct the interview, you \
do not decide what to ask next, and you do not draw personality \
conclusions -- you only extract what the candidate literally stated, as \
short, separable factual observations.

Rules (do not break these):
- Extract ONLY what the candidate actually stated. Never guess, infer \
personality traits, or embellish beyond the literal content of the answer.
- One answer may contain several distinct observations -- extract each as \
its own item, up to a maximum of 5. An answer with only one signal should \
produce only one item; do not pad the list.
- `evidence_type` is a short snake_case tag describing the kind of signal \
(e.g. "enjoys_coordination", "worked_in_sales", "prefers_remote_work").
- `normalized_text` is the observation itself, phrased as a short, neutral \
factual statement -- not a diagnosis, not a personality label.
- `confidence` reflects how clearly and unambiguously the candidate's own \
words support this specific observation -- low for vague or implied \
signals, not for how interesting the observation is.
- Never invent salary, market, or credential facts. Never produce a \
clinical/diagnostic claim.
- You must always respond by calling the `extract_evidence` tool -- never \
plain text. If the answer contains no extractable signal, call the tool \
with an empty `evidence_items` list.
"""

EVIDENCE_EXTRACTION_TOOL_SCHEMA = {
    "name": "extract_evidence",
    "description": "Extract zero or more normalized evidence observations from one candidate answer.",
    "input_schema": {
        "type": "object",
        "properties": {
            "evidence_items": {
                "type": "array",
                "maxItems": MAX_EVIDENCE_ITEMS_PER_ANSWER,
                "items": {
                    "type": "object",
                    "properties": {
                        "evidence_type": {"type": "string"},
                        "normalized_text": {"type": "string"},
                        "confidence": {"type": "number"},
                    },
                    "required": ["evidence_type", "normalized_text", "confidence"],
                },
            }
        },
        "required": ["evidence_items"],
    },
}


@dataclass(frozen=True)
class ExtractedEvidenceItem:
    evidence_type: str
    normalized_text: str
    confidence: float


@dataclass(frozen=True)
class EvidenceExtractionResult:
    items: list[ExtractedEvidenceItem]
    trace_id: str


class EvidenceExtractor:
    """Holds no provider client itself -- all calls go through the AI
    Gateway, same discipline as AnswerExtractor/ScreeningAgent."""

    def __init__(self, gateway: AIGateway | None = None) -> None:
        self._gateway = gateway or AIGateway()

    async def extract(self, *, question_prompt: str, raw_answer_text: str) -> EvidenceExtractionResult:
        result = await self._gateway.call_tool(
            task_name="evidence_extraction",
            prompt_version=PROMPT_VERSION,
            model=EXTRACTION_MODEL,
            system=_SYSTEM_PROMPT,
            tools=[EVIDENCE_EXTRACTION_TOOL_SCHEMA],
            tool_choice={"type": "tool", "name": "extract_evidence"},
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": f"Question asked: {question_prompt}\nCandidate's answer: {raw_answer_text}",
                }
            ],
        )
        return EvidenceExtractionResult(items=_validate_items(result.tool_input), trace_id=result.trace.trace_id)


def _validate_items(payload: dict | None) -> list[ExtractedEvidenceItem]:
    """Never trusts arbitrary LLM prose (Section 14): malformed or missing
    fields on an individual item silently drop that item rather than
    raising -- one bad item must not discard the other, valid items in the
    same response, and a fully malformed response degrades to "no
    evidence found" rather than crashing the whole profile generation."""
    if not isinstance(payload, dict):
        return []
    raw_items = payload.get("evidence_items")
    if not isinstance(raw_items, list):
        return []

    validated: list[ExtractedEvidenceItem] = []
    for raw in raw_items[:MAX_EVIDENCE_ITEMS_PER_ANSWER]:
        if not isinstance(raw, dict):
            continue
        evidence_type = raw.get("evidence_type")
        normalized_text = raw.get("normalized_text")
        confidence = raw.get("confidence")
        if not isinstance(evidence_type, str) or not evidence_type.strip():
            continue
        if not isinstance(normalized_text, str) or not normalized_text.strip():
            continue
        try:
            confidence_value = float(confidence)
        except (TypeError, ValueError):
            continue
        if not (0.0 <= confidence_value <= 1.0):
            continue
        validated.append(
            ExtractedEvidenceItem(evidence_type=evidence_type.strip(), normalized_text=normalized_text.strip(), confidence=confidence_value)
        )
    return validated
