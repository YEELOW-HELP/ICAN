"""Founder hardening review, item 1: two concurrent submit_answer calls
carrying the same idempotency_key must result in exactly one AI Gateway
call -- not one-per-caller-that-loses-later. submit_answer now inserts a
reservation (an Answer row with extracted_value=None) under
UNIQUE(session_id, idempotency_key) *before* calling the AI Gateway; the
loser of that insert never reaches the extractor at all.

Like tests/test_identity.py's
test_resolve_identity_recovers_when_a_concurrent_request_wins_the_race,
this uses a deterministic monkeypatch to force the exact race rather
than relying on true asyncio-level concurrency over the test suite's
single shared SQLite connection, which does not reliably reproduce a
DB-level race (see tests/test_migrations_postgres.py's real-Postgres CI
job for genuine concurrency).
"""

import asyncio

from app.core.security import hash_password
from app.db.models import AdminRole, AdminUser
from app.db.models_identity import IdentityUser
from app.services.assessment.extraction import ExtractionResult
from app.services.assessment.sessions import start_assessment, submit_answer
from app.services.product_access import grant_manual_access


class FakeExtractor:
    def __init__(self, results):
        self._results = list(results)
        self.calls = 0

    async def extract(self, *, question_prompt, raw_answer_text, previous_value):
        self.calls += 1
        return self._results.pop(0)


async def _make_user_with_basic_access(session):
    user = IdentityUser()
    session.add(user)
    await session.flush()
    admin = AdminUser(email="admin@test.dev", password_hash=hash_password("pw"), role=AdminRole.ADMIN)
    session.add(admin)
    await session.commit()
    await session.refresh(user)
    await session.refresh(admin)
    await grant_manual_access(session, user_id=user.id, plan_code="BASIC", granted_by_admin=admin)
    return user


async def test_concurrent_identical_submission_makes_exactly_one_ai_call_already_resolved_winner(
    session_factory, monkeypatch
):
    """The straightforward case: by the time the "loser" call's reservation
    insert runs, the winner has already fully finished (extracted_value is
    set). The loser must find it immediately and never call its own
    extractor."""
    import app.services.assessment.sessions as sessions_module

    async with session_factory() as session:
        user = await _make_user_with_basic_access(session)
        interview_session = await start_assessment(session, user_id=user.id, plan_code="BASIC")

        winner_extractor = FakeExtractor([ExtractionResult("Kyiv", 0.9, False)])
        winner = await submit_answer(
            session, session_id=interview_session.id, user_id=user.id, question_id="city",
            raw_text="Київ", idempotency_key="race-key", source="telegram", extractor=winner_extractor,
        )
        assert winner_extractor.calls == 1

        call_count = {"n": 0}
        real_lookup = sessions_module.find_answer_by_idempotency_key

        async def _report_missing_once_then_real(session, session_id, idempotency_key):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return None  # pretend the early idempotency check found nothing
            return await real_lookup(session, session_id, idempotency_key)

        monkeypatch.setattr(sessions_module, "find_answer_by_idempotency_key", _report_missing_once_then_real)

        loser_extractor = FakeExtractor([ExtractionResult("SHOULD NOT BE USED", 0.9, False)])
        loser_result = await submit_answer(
            session, session_id=interview_session.id, user_id=user.id, question_id="city",
            raw_text="Київ (again)", idempotency_key="race-key", source="telegram", extractor=loser_extractor,
        )

        assert loser_extractor.calls == 0  # the whole point: no duplicate AI call
        assert loser_result.id == winner.id
        assert loser_result.extracted_value == "Kyiv"


async def test_concurrent_identical_submission_waits_for_a_still_in_flight_winner(session_factory, monkeypatch):
    """The harder case: the reservation insert conflicts with a winner that
    has NOT finished extraction yet. The loser must wait (poll) rather
    than give up or call its own extractor, and must return the winner's
    real result once it resolves."""
    import app.db.models_assessment as models_assessment
    import app.services.assessment.sessions as sessions_module
    from sqlalchemy import select

    async with session_factory() as session:
        user = await _make_user_with_basic_access(session)
        interview_session = await start_assessment(session, user_id=user.id, plan_code="BASIC")

        # Simulate "winner" having reserved the row but not yet finished
        # extraction -- exactly the state submit_answer leaves it in
        # between its reservation commit and its final update.
        pending = models_assessment.Answer(
            session_id=interview_session.id, question_id="city", answer_text="Київ",
            extracted_value=None, confidence=None, contradicts_previous=False,
            source="telegram", idempotency_key="race-key-2",
        )
        session.add(pending)
        await session.commit()

        call_count = {"n": 0}
        real_lookup = sessions_module.find_answer_by_idempotency_key

        async def _report_missing_once_then_real(session, session_id, idempotency_key):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return None
            return await real_lookup(session, session_id, idempotency_key)

        monkeypatch.setattr(sessions_module, "find_answer_by_idempotency_key", _report_missing_once_then_real)

        resolved_by_winner = {"done": False}

        async def _resolve_winner_on_first_poll():
            if not resolved_by_winner["done"]:
                resolved_by_winner["done"] = True
                result = await session.execute(select(models_assessment.Answer).where(models_assessment.Answer.id == pending.id))
                row = result.scalar_one()
                row.extracted_value = "Kyiv"
                row.confidence = 0.9
                await session.commit()
            await asyncio.sleep(0)  # yield control without actually waiting

        monkeypatch.setattr(sessions_module, "_poll_delay", _resolve_winner_on_first_poll)

        loser_extractor = FakeExtractor([ExtractionResult("SHOULD NOT BE USED", 0.9, False)])
        loser_result = await submit_answer(
            session, session_id=interview_session.id, user_id=user.id, question_id="city",
            raw_text="Київ (again)", idempotency_key="race-key-2", source="telegram", extractor=loser_extractor,
        )

        assert loser_extractor.calls == 0
        assert loser_result.id == pending.id
        assert loser_result.extracted_value == "Kyiv"
        assert resolved_by_winner["done"] is True


async def test_ai_failure_deletes_the_reservation_so_a_genuine_retry_can_proceed(session_factory):
    """If extraction genuinely fails, the reservation must not linger as a
    permanent phantom "answered but empty" row -- a fresh attempt (even
    with the same idempotency_key, e.g. Telegram redelivering the same
    update after the bot recovers) must be able to actually try again."""
    import pytest

    from app.services.assessment.extraction import ExtractionResult

    class ExplodingThenWorkingExtractor:
        def __init__(self):
            self.calls = 0

        async def extract(self, *, question_prompt, raw_answer_text, previous_value):
            self.calls += 1
            if self.calls == 1:
                raise ConnectionError("provider outage")
            return ExtractionResult("Kyiv", 0.9, False)

    async with session_factory() as session:
        user = await _make_user_with_basic_access(session)
        interview_session = await start_assessment(session, user_id=user.id, plan_code="BASIC")
        extractor = ExplodingThenWorkingExtractor()

        with pytest.raises(ConnectionError):
            await submit_answer(
                session, session_id=interview_session.id, user_id=user.id, question_id="city",
                raw_text="Київ", idempotency_key="retry-key", source="telegram", extractor=extractor,
            )

        # same idempotency_key, genuine retry after the failure
        answer = await submit_answer(
            session, session_id=interview_session.id, user_id=user.id, question_id="city",
            raw_text="Київ", idempotency_key="retry-key", source="telegram", extractor=extractor,
        )
        assert extractor.calls == 2
        assert answer.extracted_value == "Kyiv"

        from sqlalchemy import func, select

        from app.db.models_assessment import Answer

        count = (
            await session.execute(
                select(func.count()).select_from(Answer).where(
                    Answer.session_id == interview_session.id, Answer.idempotency_key == "retry-key"
                )
            )
        ).scalar_one()
        assert count == 1  # no leftover phantom reservation from the failed attempt
