"""Adaptive next-question selection (Stage 1 -- Issue #1 Part 4's approved
design). Selection is entirely deterministic/server-side; the AI Gateway
is never consulted for *which* question to ask, only (separately, in
app/services/assessment/extraction.py) for extracting structured content
out of a free-text answer already given. This keeps "traceable reason"
and "prevent endless questioning" fully auditable without depending on an
LLM's judgment for either.

Priority when multiple dimensions need attention: contradiction >
low_confidence > missing, in question-bank declared order within each
tier. Already-`resolved` dimensions are never reselected.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models_assessment import QuestionSelection, SelectionReason
from app.services.assessment.completeness import compute_completeness, minimum_data_satisfied
from app.services.assessment.question_bank import QUESTION_BANK, Question, QUESTIONS_BY_ID

_STATE_TO_REASON = {
    "contradiction": SelectionReason.CONTRADICTION,
    "low_confidence": SelectionReason.LOW_CONFIDENCE,
    "missing": SelectionReason.MISSING,
}
_PRIORITY_ORDER = ("contradiction", "low_confidence", "missing")


@dataclass(frozen=True)
class NextQuestionResult:
    question: Question | None  # None means: ready to complete (or safety cap reached)
    reason: SelectionReason | None
    ready_for_completion: bool
    terminated_by_safety_cap: bool = False


async def get_next_question(session: AsyncSession, session_id: uuid.UUID) -> NextQuestionResult:
    statuses = await compute_completeness(session, session_id)

    asked_count = (
        await session.execute(select(func.count()).select_from(QuestionSelection).where(QuestionSelection.session_id == session_id))
    ).scalar_one()
    if asked_count >= settings.max_assessment_questions:
        # Safety valve: never ask forever, even under repeated contradictions.
        # Mirrors legacy ScreeningAgent's max_screening_turns cap.
        return NextQuestionResult(
            question=None, reason=None, ready_for_completion=True, terminated_by_safety_cap=True
        )

    for state in _PRIORITY_ORDER:
        for question in QUESTION_BANK:
            if statuses[question.question_id].state != state:
                continue
            # Optional dimensions are only proactively (re-)surfaced once
            # something has actually been said about them and it came back
            # contradictory/low-confidence -- a merely *missing* optional
            # question is never selected just because it's missing. This
            # is what keeps the interview within its ~20-30 minute target
            # instead of exhaustively working through the whole bank: once
            # every *required* dimension resolves, the interview is
            # completion-eligible even if optional dimensions were never
            # touched (see minimum_data_satisfied, which only checks
            # required questions).
            if state == "missing" and not question.required_for_minimum:
                continue
            await _record_selection(session, session_id, question.question_id, _STATE_TO_REASON[state])
            return NextQuestionResult(question=question, reason=_STATE_TO_REASON[state], ready_for_completion=False)

    # Nothing left to ask that would change completion eligibility.
    assert minimum_data_satisfied(statuses), "no question left to ask but minimum-data rule is not satisfied"
    return NextQuestionResult(question=None, reason=None, ready_for_completion=True)


async def _record_selection(session: AsyncSession, session_id: uuid.UUID, question_id: str, reason: SelectionReason) -> None:
    session.add(QuestionSelection(session_id=session_id, question_id=question_id, reason=reason))
    await session.commit()


async def mark_question_answered(session: AsyncSession, *, session_id: uuid.UUID, question_id: str, answer_id: uuid.UUID) -> None:
    """Links the most recent unanswered QuestionSelection for this
    question_id to the Answer that resolved it -- keeps the "relationship
    to resulting answer" requirement real, not inferred after the fact."""
    from datetime import datetime, timezone

    result = await session.execute(
        select(QuestionSelection)
        .where(
            QuestionSelection.session_id == session_id,
            QuestionSelection.question_id == question_id,
            QuestionSelection.answered_at.is_(None),
        )
        .order_by(QuestionSelection.selected_at.desc())
        .limit(1)
    )
    selection = result.scalar_one_or_none()
    if selection is not None:
        selection.answered_at = datetime.now(timezone.utc)
        selection.answer_id = answer_id
        await session.commit()
