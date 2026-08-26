"""Founder hardening review item 25 (deferred from Stage 1): a process
crash after creating the Answer idempotency reservation but before AI
extraction may leave a permanently pending Answer. Stage 2 must detect
and recover from this before treating a session's answers as evidence.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.config import settings
from app.db.models_assessment import Answer
from app.services.assessment.sessions import recover_stale_pending_answers
from tests.profile_test_helpers import make_complete_session


async def _insert_pending(session, session_id, *, age_seconds: float, question_id="total_experience", key="stale-1"):
    created_at = datetime.now(timezone.utc) - timedelta(seconds=age_seconds)
    pending = Answer(
        session_id=session_id, question_id=question_id, answer_text="...", extracted_value=None,
        confidence=None, contradicts_previous=False, source="telegram", idempotency_key=key, created_at=created_at,
    )
    session.add(pending)
    await session.commit()
    await session.refresh(pending)
    return pending


async def test_stale_pending_answer_is_detected_and_removed(session_factory):
    async with session_factory() as session:
        _, interview_session = await make_complete_session(session)
        stale = await _insert_pending(session, interview_session.id, age_seconds=settings.pending_answer_stale_after_seconds + 60)

        removed = await recover_stale_pending_answers(session, interview_session.id)

        assert removed == 1
        remaining = await session.get(Answer, stale.id)
        assert remaining is None


async def test_recent_pending_answer_is_not_treated_as_stale(session_factory):
    """A genuinely in-flight reservation (well within the timeout) must
    survive a recovery sweep -- recovery is not allowed to be trigger-happy."""
    async with session_factory() as session:
        _, interview_session = await make_complete_session(session)
        recent = await _insert_pending(session, interview_session.id, age_seconds=1, key="recent-1")

        removed = await recover_stale_pending_answers(session, interview_session.id)

        assert removed == 0
        remaining = await session.get(Answer, recent.id)
        assert remaining is not None


async def test_recovery_only_removes_pending_rows_never_resolved_answers(session_factory):
    async with session_factory() as session:
        _, interview_session = await make_complete_session(session)
        # make_complete_session already left several resolved Answer rows
        before = (await session.execute(select(Answer).where(Answer.session_id == interview_session.id))).scalars().all()
        resolved_count_before = sum(1 for a in before if a.extracted_value is not None)

        await _insert_pending(session, interview_session.id, age_seconds=settings.pending_answer_stale_after_seconds + 60)
        removed = await recover_stale_pending_answers(session, interview_session.id)

        after = (await session.execute(select(Answer).where(Answer.session_id == interview_session.id))).scalars().all()
        resolved_count_after = sum(1 for a in after if a.extracted_value is not None)

        assert removed == 1
        assert resolved_count_after == resolved_count_before  # real answers untouched


async def test_profile_generation_recovers_stale_pending_before_extracting_evidence(session_factory):
    """The end-to-end guarantee: generate_potential_profile must never
    surface a stale pending answer as evidence, and must clean it up as
    part of the normal generation flow (Section 25's actual requirement)."""
    from app.db.models_profile import Evidence
    from app.services.profile.generation import generate_potential_profile
    from tests.profile_test_helpers import FakeClaimSynthesizer, FakeEvidenceExtractor, FakeSummarizer

    async with session_factory() as session:
        user, interview_session = await make_complete_session(session)
        stale = await _insert_pending(session, interview_session.id, age_seconds=settings.pending_answer_stale_after_seconds + 60)

        extractor = FakeEvidenceExtractor()
        await generate_potential_profile(
            session, session_id=interview_session.id, user_id=user.id,
            evidence_extractor=extractor, claim_synthesizer=FakeClaimSynthesizer(), summarizer=FakeSummarizer(),
        )

        assert await session.get(Answer, stale.id) is None
        assert "total_experience" not in extractor.calls
        evidence_sources = (await session.execute(select(Evidence.source_id))).scalars().all()
        assert stale.id not in evidence_sources
