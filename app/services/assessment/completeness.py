"""Deterministic, server-side completeness/minimum-data policy (Section 13:
"Assessment completion must NOT be decided by the LLM saying 'I think we
have enough.'"). This module never calls the AI Gateway -- it only reads
already-recorded `Answer` rows.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_assessment import Answer
from app.services.assessment.question_bank import QUESTION_BANK, REQUIRED_QUESTION_IDS

LOW_CONFIDENCE_THRESHOLD = 0.5


@dataclass(frozen=True)
class DimensionStatus:
    question_id: str
    state: str  # "missing" | "low_confidence" | "contradiction" | "resolved"
    latest_answer_id: uuid.UUID | None


async def latest_answers_by_question(session: AsyncSession, session_id: uuid.UUID) -> dict[str, Answer]:
    """One row per `question_id`: the most recent `Answer`, per the
    "latest by created_at wins" read convention -- superseded answers are
    never deleted, just outranked."""
    result = await session.execute(select(Answer).where(Answer.session_id == session_id).order_by(Answer.created_at))
    latest: dict[str, Answer] = {}
    for answer in result.scalars():
        latest[answer.question_id] = answer  # later rows overwrite earlier ones -- ascending order
    return latest


async def compute_completeness(session: AsyncSession, session_id: uuid.UUID) -> dict[str, DimensionStatus]:
    latest = await latest_answers_by_question(session, session_id)
    statuses: dict[str, DimensionStatus] = {}
    for question in QUESTION_BANK:
        answer = latest.get(question.question_id)
        if answer is None or answer.extracted_value is None:
            # `extracted_value is None` means this is a still-pending
            # idempotency reservation (app/services/assessment/sessions.py
            # inserts the row before calling the AI Gateway, then fills it
            # in) -- treated as not-yet-answered, never as "resolved",
            # otherwise a concurrent in-flight submission could briefly
            # make a required dimension look satisfied before it actually
            # has a value.
            statuses[question.question_id] = DimensionStatus(question.question_id, "missing", None)
        elif answer.contradicts_previous:
            statuses[question.question_id] = DimensionStatus(question.question_id, "contradiction", answer.id)
        elif answer.confidence is not None and answer.confidence < LOW_CONFIDENCE_THRESHOLD:
            statuses[question.question_id] = DimensionStatus(question.question_id, "low_confidence", answer.id)
        else:
            statuses[question.question_id] = DimensionStatus(question.question_id, "resolved", answer.id)
    return statuses


def minimum_data_satisfied(statuses: dict[str, DimensionStatus]) -> bool:
    """The minimum-data rule: every *required* question must be
    `resolved`. Optional questions being missing/low-confidence never
    blocks completion."""
    return all(statuses[qid].state == "resolved" for qid in REQUIRED_QUESTION_IDS if qid in statuses)


def completeness_summary(statuses: dict[str, DimensionStatus]) -> dict[str, str]:
    """A small JSON-serializable snapshot for `InterviewSession.completeness`."""
    return {qid: status.state for qid, status in statuses.items()}
