from pydantic import BaseModel, Field

# Fields the AI screening agent is allowed to fill in. Kept in one place so the
# Claude tool schema (extraction), the DB model, and the API response can't drift.
PROFILE_FIELDS = [
    "name",
    "country",
    "city",
    "status",
    "education",
    "total_experience",
    "previous_positions",
    "skills",
    "languages",
    "desired_role",
    "desired_min_income",
    "desired_currency",
    "employment_format",
    "work_format",
    "schedule",
    "constraints",
    "other_notes",
]


class ProfileDraft(BaseModel):
    """Partial profile as understood so far. Every field is optional — the AI
    must never invent a value for a fact the user hasn't stated (ТЗ п.4, п.6)."""

    name: str | None = None
    country: str | None = None
    city: str | None = None
    status: str | None = Field(default=None, description="working / not_working / studying / other")
    education: str | None = None
    total_experience: str | None = None
    previous_positions: list[str] | None = None
    skills: list[str] | None = None
    languages: list[str] | None = None
    desired_role: str | None = None
    desired_min_income: str | None = None
    desired_currency: str | None = None
    employment_format: str | None = Field(default=None, description="full-time / part-time / other")
    work_format: str | None = Field(default=None, description="onsite / hybrid / remote / flexible")
    schedule: str | None = None
    constraints: str | None = None
    other_notes: str | None = None


class ProfileOut(ProfileDraft):
    id: int
    user_id: int
    confirmed: bool


# JSON Schema handed to Claude as a tool so extraction results are structured
# instead of free text. Deliberately mirrors ProfileDraft field-for-field.
#
# Property order matters here beyond readability: Claude generates tool-call
# JSON in roughly the declared property order, and `profile` can get large
# (a detailed CV easily fills it with paragraphs of education/experience
# text). Putting `reply_to_user` and `ready_for_confirmation` BEFORE `profile`
# means that if a response ever gets cut off by max_tokens, it's the (already
# known, re-derivable) profile echo that gets truncated — never the reply the
# candidate is waiting for.
PROFILE_TOOL_SCHEMA = {
    "name": "update_profile",
    "description": (
        "Record the candidate's next reply and, separately, any NEW or CHANGED "
        "facts from their latest message. `profile` is a delta, not a full replay: "
        "the caller already has `current_profile` and merges your delta onto it, so "
        "omit any field that is already correct there and hasn't changed this turn — "
        "re-sending unchanged fields (e.g. a long CV-derived education or skills list) "
        "wastes tokens and risks truncating your own reply. Only include a field if the "
        "candidate actually stated it — never guess or infer a value."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "reply_to_user": {
                "type": "string",
                "description": (
                    "The next message to send to the candidate: either a clarifying "
                    "question about missing important fields, or — if enough is known "
                    "— a short human-readable summary of the profile for confirmation."
                ),
            },
            "ready_for_confirmation": {
                "type": "boolean",
                "description": "True once enough core fields are known and reply_to_user is a confirmation summary.",
            },
            "profile": {
                "type": "object",
                "description": "Only NEW or CHANGED fields from this turn — never re-send fields already correct in current_profile.",
                "properties": {
                    "name": {"type": ["string", "null"]},
                    "country": {"type": ["string", "null"]},
                    "city": {"type": ["string", "null"]},
                    "status": {"type": ["string", "null"], "description": "working / not_working / studying / other"},
                    "education": {"type": ["string", "null"]},
                    "total_experience": {"type": ["string", "null"]},
                    "previous_positions": {"type": ["array", "null"], "items": {"type": "string"}},
                    "skills": {"type": ["array", "null"], "items": {"type": "string"}},
                    "languages": {"type": ["array", "null"], "items": {"type": "string"}},
                    "desired_role": {"type": ["string", "null"]},
                    "desired_min_income": {"type": ["string", "null"]},
                    "desired_currency": {"type": ["string", "null"]},
                    "employment_format": {"type": ["string", "null"], "description": "full-time / part-time / other"},
                    "work_format": {"type": ["string", "null"], "description": "onsite / hybrid / remote / flexible"},
                    "schedule": {"type": ["string", "null"]},
                    "constraints": {"type": ["string", "null"]},
                    "other_notes": {"type": ["string", "null"]},
                },
            },
        },
        "required": ["reply_to_user", "ready_for_confirmation", "profile"],
    },
}
