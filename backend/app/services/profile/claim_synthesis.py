"""AI System component 3, "Profile Synthesizer" (docs/architecture/04_AI_SYSTEM.md).
Groups a session's Evidence rows into candidate PROFILE_CLAIM proposals --
the LLM's job is semantic grouping/labeling ONLY (which evidence items are
about the same underlying claim, and does the group contain conflicting
signals). Numeric confidence and claim status are decided afterward by
`compute_claim_confidence`, a pure deterministic function (Stage 2 brief
§8: confidence must be auditable, not an LLM's self-reported number).

A claim is never persisted with zero grounding evidence (brief §5/§7's
non-negotiable "claim -> evidence -> source" chain) -- see
app/services/profile/generation.py, which drops any claim proposal whose
evidence_indices don't resolve to at least one real Evidence row.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.ai_gateway import AIGateway
from app.db.models_profile import ClaimStatus, Evidence, ProfileDimension

PROMPT_VERSION = "claim-synthesis-v1"
SYNTHESIS_MODEL = "claude-sonnet-5"

# Deterministic confidence thresholds -- Stage 2 brief §8: "how well
# supported is this claim by available evidence", never a fit/suitability
# score. Tuned to be conservative (HYPOTHESIS is the default outcome for
# anything short of clearly corroborated).
_SUPPORTED_THRESHOLD = 0.6
_HYPOTHESIS_THRESHOLD = 0.25
_CONTRADICTION_PENALTY = 0.4
_CORROBORATION_BONUS_PER_ITEM = 0.05
_CORROBORATION_BONUS_CAP = 0.15
_DIRECT_EVIDENCE_BONUS = 0.1

_SYSTEM_PROMPT = """\
You group normalized evidence observations from a career-assessment \
candidate into profile claims -- statements about the person's \
strengths, interests, values, motivations, skills, traits, work \
preferences, constraints, goals, experience, or relevant contextual \
factors. You do not decide numeric confidence and you do not decide \
career directions -- only which evidence items belong together and \
whether they agree or conflict.

Rules (do not break these):
- Every claim MUST reference at least one evidence item by its index. \
Never propose a claim with no supporting evidence.
- Group evidence about the SAME underlying claim together, even if it \
came from different answers.
- If two or more evidence items grouped under one claim genuinely \
conflict (e.g. "enjoys working with people" vs "prefers working alone"), \
set `is_contradictory: true` and still include ALL the conflicting \
evidence indices -- never silently drop or average away a contradiction.
- `dimension` must be exactly one of the allowed values given below.
- Prefer a `term_key` from the provided taxonomy vocabulary if one \
genuinely fits; otherwise leave `term_key` as an empty string and write a \
clear free-text `label` instead. Never invent a term_key that isn't in \
the provided vocabulary.
- `normalized_value` is a short, neutral statement of the claim itself -- \
never a diagnosis, never a guarantee, never invented salary/market facts.
- You must always respond by calling the `synthesize_claims` tool -- \
never plain text. If no evidence supports any coherent claim, call the \
tool with an empty `claims` list.
"""


def _tool_schema() -> dict:
    return {
        "name": "synthesize_claims",
        "description": "Group evidence observations into candidate profile claims with contradiction flags.",
        "input_schema": {
            "type": "object",
            "properties": {
                "claims": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "dimension": {"type": "string", "enum": [d.value for d in ProfileDimension]},
                            "term_key": {"type": "string"},
                            "label": {"type": "string"},
                            "normalized_value": {"type": "string"},
                            "evidence_indices": {"type": "array", "items": {"type": "integer"}},
                            "is_contradictory": {"type": "boolean"},
                        },
                        "required": ["dimension", "label", "normalized_value", "evidence_indices", "is_contradictory"],
                    },
                }
            },
            "required": ["claims"],
        },
    }


@dataclass(frozen=True)
class ClaimProposal:
    dimension: ProfileDimension
    term_key: str | None
    label: str
    normalized_value: str
    evidence_indices: list[int]
    is_contradictory: bool


@dataclass(frozen=True)
class ClaimSynthesisResult:
    proposals: list[ClaimProposal]
    trace_id: str | None


class ClaimSynthesizer:
    def __init__(self, gateway: AIGateway | None = None) -> None:
        self._gateway = gateway or AIGateway()

    async def synthesize(
        self, *, evidence_items: list[Evidence], taxonomy_terms: list[tuple[str, str, str]]
    ) -> ClaimSynthesisResult:
        """`taxonomy_terms` is `(term_key, dimension, label_uk)` tuples --
        the closed vocabulary the model should prefer over inventing new
        terms. Returns an empty result if there is no evidence to
        synthesize from at all, without making a wasted AI Gateway call."""
        if not evidence_items:
            return ClaimSynthesisResult(proposals=[], trace_id=None)

        evidence_lines = [
            f"[{i}] ({item.source_type.value}, {item.evidence_type}, confidence={item.confidence:.2f}): {item.normalized_text}"
            for i, item in enumerate(evidence_items)
        ]
        vocabulary_lines = [f"{term_key} ({dimension}): {label_uk}" for term_key, dimension, label_uk in taxonomy_terms]

        prompt = (
            "Evidence items (indexed):\n"
            + "\n".join(evidence_lines)
            + "\n\nTaxonomy vocabulary (term_key (dimension): label):\n"
            + "\n".join(vocabulary_lines)
        )

        result = await self._gateway.call_tool(
            task_name="claim_synthesis",
            prompt_version=PROMPT_VERSION,
            model=SYNTHESIS_MODEL,
            system=_SYSTEM_PROMPT,
            tools=[_tool_schema()],
            tool_choice={"type": "tool", "name": "synthesize_claims"},
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        proposals = _validate_proposals(result.tool_input, evidence_count=len(evidence_items))
        return ClaimSynthesisResult(proposals=proposals, trace_id=result.trace.trace_id)


def _validate_proposals(payload: dict | None, *, evidence_count: int) -> list[ClaimProposal]:
    if not isinstance(payload, dict):
        return []
    raw_claims = payload.get("claims")
    if not isinstance(raw_claims, list):
        return []

    valid_dimensions = {d.value for d in ProfileDimension}
    proposals: list[ClaimProposal] = []
    for raw in raw_claims:
        if not isinstance(raw, dict):
            continue
        dimension_value = raw.get("dimension")
        label = raw.get("label")
        normalized_value = raw.get("normalized_value")
        indices = raw.get("evidence_indices")
        is_contradictory = raw.get("is_contradictory")
        if dimension_value not in valid_dimensions:
            continue
        if not isinstance(label, str) or not label.strip():
            continue
        if not isinstance(normalized_value, str) or not normalized_value.strip():
            continue
        if not isinstance(indices, list):
            continue
        resolved_indices = sorted({i for i in indices if isinstance(i, int) and 0 <= i < evidence_count})
        if not resolved_indices:
            continue  # a claim with no valid evidence reference is never emitted
        term_key = raw.get("term_key")
        proposals.append(
            ClaimProposal(
                dimension=ProfileDimension(dimension_value),
                term_key=term_key.strip() if isinstance(term_key, str) and term_key.strip() else None,
                label=label.strip(),
                normalized_value=normalized_value.strip(),
                evidence_indices=resolved_indices,
                is_contradictory=bool(is_contradictory),
            )
        )
    return proposals


def compute_claim_confidence(
    supporting_evidence: list[Evidence], *, is_contradictory: bool
) -> tuple[float, ClaimStatus] | None:
    """Pure and deterministic (Stage 2 brief §8) -- considers count of
    supporting evidence, source directness, and contradiction, never an
    LLM's self-reported score. Returns None if there is no evidence at
    all, telling the caller to skip persisting this claim entirely."""
    if not supporting_evidence:
        return None

    if is_contradictory:
        # Retains the conflict rather than averaging it away (brief §7) --
        # confidence is deliberately driven down, never up, by conflicting
        # signals, and the claim is never silently reconciled into one
        # side "winning".
        weakest = min(item.confidence for item in supporting_evidence)
        return round(weakest * (1 - _CONTRADICTION_PENALTY), 2), ClaimStatus.CONTRADICTED

    avg_confidence = sum(item.confidence for item in supporting_evidence) / len(supporting_evidence)
    corroboration_bonus = min(_CORROBORATION_BONUS_CAP, _CORROBORATION_BONUS_PER_ITEM * (len(supporting_evidence) - 1))
    has_direct_evidence = any(item.extraction_method == "deterministic" for item in supporting_evidence)
    direct_bonus = _DIRECT_EVIDENCE_BONUS if has_direct_evidence else 0.0
    confidence = min(1.0, avg_confidence + corroboration_bonus + direct_bonus)

    if confidence >= _SUPPORTED_THRESHOLD and (len(supporting_evidence) >= 2 or has_direct_evidence):
        status = ClaimStatus.SUPPORTED
    elif confidence >= _HYPOTHESIS_THRESHOLD:
        status = ClaimStatus.HYPOTHESIS
    else:
        status = ClaimStatus.INSUFFICIENT_EVIDENCE

    return round(confidence, 2), status
