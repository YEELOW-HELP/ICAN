"""AI System component 6, "Narrative Generator" (docs/architecture/04_AI_SYSTEM.md),
scoped to Stage 2's internal preview only (brief §18/§19): turns the final
claims of one profile version into a short Ukrainian human-readable
summary ("ХТО Я"). This is a presentation artifact, never canonical truth
-- the canonical source stays Evidence + ProfileClaim rows; regenerating
the summary text never changes what a claim actually says.

Never adds career-direction recommendations (Stage 3 territory) and never
exposes raw numeric confidence -- claims are bucketed to
high/medium/low before they ever reach the prompt, per Stage 2 brief §8
("do not expose fake precision such as 87.36%.\")
"""

from __future__ import annotations

from dataclasses import dataclass

from app.ai_gateway import AIGateway
from app.db.models_profile import ClaimStatus, ProfileClaim

PROMPT_VERSION = "profile-summary-v1"
SUMMARY_MODEL = "claude-sonnet-5"


def confidence_bucket(status: ClaimStatus) -> str:
    """Deterministic status -> user-facing bucket mapping -- never a raw
    float in front of a person (brief §8)."""
    return {
        ClaimStatus.SUPPORTED: "high",
        ClaimStatus.HYPOTHESIS: "medium",
        ClaimStatus.INSUFFICIENT_EVIDENCE: "low",
        ClaimStatus.CONTRADICTED: "contradictory",
    }[status]


_SYSTEM_PROMPT = """\
You write a short, warm, honest summary in Ukrainian of a career-assessment \
candidate's profile, based ONLY on the structured claims given to you. You \
are writing a presentation of already-decided facts, not deciding new ones.

Rules (do not break these):
- Use ONLY the claims given to you. Never add a trait, interest, skill, or \
constraint that isn't in the list.
- Never recommend or mention specific career directions, professions, \
salaries, employers, or educational institutions -- that is out of scope \
for this summary entirely.
- Never state a diagnosis or a guarantee about the person's future.
- A claim marked "contradictory" must be presented as an open question or \
tension, not resolved one way or the other.
- A claim marked "low" confidence should be phrased tentatively (e.g. \
"можливо", "є натяк на") rather than as a settled fact.
- Write in Ukrainian, in second person, addressed to the candidate directly.
- You must always respond by calling the `write_summary` tool -- never \
plain text.
"""

_TOOL_SCHEMA = {
    "name": "write_summary",
    "description": "Write the Ukrainian human-readable profile summary text.",
    "input_schema": {
        "type": "object",
        "properties": {"summary_text": {"type": "string"}},
        "required": ["summary_text"],
    },
}


@dataclass(frozen=True)
class ProfileSummaryResult:
    summary_text: str
    trace_id: str | None


class ProfileSummarizer:
    def __init__(self, gateway: AIGateway | None = None) -> None:
        self._gateway = gateway or AIGateway()

    async def summarize(self, *, claims: list[ProfileClaim], locale: str = "uk") -> ProfileSummaryResult:
        if not claims:
            return ProfileSummaryResult(summary_text="", trace_id=None)

        claim_lines = [
            f"- [{claim.dimension.value}] {claim.label}: {claim.normalized_value} "
            f"(confidence: {confidence_bucket(claim.status)})"
            for claim in claims
        ]
        prompt = "Claims:\n" + "\n".join(claim_lines)

        result = await self._gateway.call_tool(
            task_name="profile_summary",
            prompt_version=PROMPT_VERSION,
            model=SUMMARY_MODEL,
            system=_SYSTEM_PROMPT,
            tools=[_TOOL_SCHEMA],
            tool_choice={"type": "tool", "name": "write_summary"},
            max_tokens=1536,
            messages=[{"role": "user", "content": prompt}],
        )
        payload = result.tool_input or {}
        summary_text = payload.get("summary_text")
        return ProfileSummaryResult(
            summary_text=summary_text.strip() if isinstance(summary_text, str) else "",
            trace_id=result.trace.trace_id,
        )
