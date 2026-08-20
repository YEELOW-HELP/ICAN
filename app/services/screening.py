from __future__ import annotations

import logging
from dataclasses import dataclass

from anthropic import AsyncAnthropic

from app.core.config import settings
from app.schemas.profile import PROFILE_TOOL_SCHEMA, ProfileDraft

logger = logging.getLogger(__name__)

# Anthropic's tool `required` list is a strong hint, not a hard guarantee —
# the model occasionally omits a required field. Rather than crash the whole
# turn (and leave the candidate with no reply at all), fall back to a generic
# clarifying question when that happens.
FALLBACK_REPLY = "Вибачте, не зовсім зрозумів. Можете, будь ласка, уточнити чи повторити?"

SCREENING_MODEL = "claude-sonnet-5"

SYSTEM_PROMPT = """\
You are the ICAN screening assistant. You conduct a natural-language interview \
with a job-seeking candidate over Telegram to build a structured profile.

Rules (do not break these):
- Always write `reply_to_user` in Ukrainian, regardless of what language the \
candidate's message or an uploaded CV is written in — unless the candidate has \
explicitly asked you (in the conversation) to switch to a different language.
- Understand free-form text; a single message may contain several facts at once.
- Extract ONLY facts the candidate explicitly stated. Never guess or infer a \
value for education, experience, salary, skills, languages, or any other field. \
If something wasn't stated, leave it null.
- Never re-ask about a fact that is already known from `current_profile` or the \
conversation history, unless the candidate's latest message contradicts it — in \
that case, ask a short clarifying question about the contradiction instead of \
silently overwriting it.
- The `profile` argument is a delta: never repeat a field that is already correct \
in `current_profile`, even a long one (e.g. from a CV). Only include fields that \
are new or changed this turn — always write `reply_to_user` regardless of how \
much or little `profile` contains.
- Ask about ONE of the missing important fields at a time, phrased conversationally \
— never present a rigid numbered questionnaire.
- Important fields to eventually cover: name, country/city, current status, \
education, total experience, previous positions, key skills, languages, desired \
role, desired minimum income + currency, employment format (full-time/part-time), \
work format (onsite/hybrid/remote/flexible), schedule, constraints.
- Once the important fields are known well enough (it's fine if a minor field is \
still missing), stop asking questions: instead write a short, human-readable \
summary of the profile in `reply_to_user` and set `ready_for_confirmation=true`, \
ending with an invitation for the candidate to confirm it's correct or say what \
to fix.
- You must always respond by calling the `update_profile` tool — never plain text.
"""


@dataclass
class ScreeningResult:
    profile: ProfileDraft
    reply_to_user: str
    ready_for_confirmation: bool


class ScreeningAgent:
    """Wraps a single Claude call that both extracts structured facts from the
    candidate's latest message and decides the next thing to say (ТЗ п.6)."""

    def __init__(self, client: AsyncAnthropic | None = None) -> None:
        self._client = client or AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def process_message(
        self,
        history: list[dict[str, str]],
        current_profile: ProfileDraft,
        user_message: str,
    ) -> ScreeningResult:
        context = (
            f"current_profile (already confirmed-known facts, do not re-ask these):\n"
            f"{current_profile.model_dump_json(exclude_none=True)}"
        )

        messages = [
            {"role": "user", "content": context},
            {"role": "assistant", "content": "Understood, I have the current profile in mind."},
            *history,
            {"role": "user", "content": user_message},
        ]

        response = await self._client.messages.create(
            model=SCREENING_MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=[PROFILE_TOOL_SCHEMA],
            tool_choice={"type": "tool", "name": "update_profile"},
            messages=messages,
        )

        tool_use = next((block for block in response.content if block.type == "tool_use"), None)
        payload = tool_use.input if tool_use is not None else {}

        if tool_use is None or "reply_to_user" not in payload:
            logger.warning(
                "Claude tool response missing expected fields (stop_reason=%s): %r",
                response.stop_reason,
                payload,
            )

        merged = current_profile.model_dump()
        for key, value in payload.get("profile", {}).items():
            if value is not None:
                merged[key] = value

        return ScreeningResult(
            profile=ProfileDraft(**merged),
            reply_to_user=payload.get("reply_to_user") or FALLBACK_REPLY,
            ready_for_confirmation=payload.get("ready_for_confirmation", False),
        )


def history_from_messages(messages: list) -> list[dict[str, str]]:
    """Convert stored Message rows into the {role, content} shape the Anthropic API expects."""
    return [
        {"role": "user" if m.role.value == "user" else "assistant", "content": m.content}
        for m in messages
    ]
