"""The Stage 1 Hybrid question bank -- a small, explicit, versionable set
of dimensions, not the final Taxonomy v1 content (that's Methodology's
future work per docs/engineering/11_TECHNICAL_DEBT_REGISTER.md Item 11).
Content lives here as data, keyed by `question_id` + locale, specifically
so it can grow/change without touching the next-question algorithm
(app/services/assessment/next_question.py) or business logic in general --
see app/services/assessment/content.py for the locale text itself.

`kind="structured"` questions are fixed-choice and never go through the AI
Gateway (near-zero token cost, matching the platform's "Structured mode"
philosophy). `kind="open"` questions are free text and are extracted via
app/services/assessment/extraction.py.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Question:
    question_id: str
    dimension: str
    kind: str  # "structured" | "open"
    required_for_minimum: bool
    choices: tuple[str, ...] | None = None


QUESTION_BANK: tuple[Question, ...] = (
    Question("name", "identity", "open", required_for_minimum=True),
    Question("city", "location", "open", required_for_minimum=True),
    Question(
        "current_status",
        "status",
        "structured",
        required_for_minimum=True,
        choices=("working", "not_working", "studying", "other"),
    ),
    Question("total_experience", "experience", "open", required_for_minimum=False),
    Question("key_skills_or_interests", "skills", "open", required_for_minimum=True),
    Question("desired_direction_hint", "direction", "open", required_for_minimum=True),
    Question(
        "employment_format",
        "preferences",
        "structured",
        required_for_minimum=False,
        choices=("full_time", "part_time", "flexible"),
    ),
    Question("constraints", "constraints", "open", required_for_minimum=False),
)

QUESTIONS_BY_ID: dict[str, Question] = {q.question_id: q for q in QUESTION_BANK}

REQUIRED_QUESTION_IDS: frozenset[str] = frozenset(q.question_id for q in QUESTION_BANK if q.required_for_minimum)
