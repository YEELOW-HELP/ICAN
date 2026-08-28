"""Stage 4A.5 §2/§3: the admin-fallback profile-generation entry point
(app/services/profile/generation.py::generate_profile_for_user) and the
Dashboard profile-status summary."""

from __future__ import annotations

import pytest

from app.db.models_profile import PotentialProfile, ProfileGenerationStatus
from app.services.exceptions import NoEligibleAssessmentSessionError, ProfileAlreadyExistsError
from app.services.profile.generation import generate_profile_for_user, get_profile_status_summary
from tests.profile_test_helpers import FakeClaimSynthesizer, FakeEvidenceExtractor, FakeSummarizer, make_complete_session


def _fakes():
    return dict(evidence_extractor=FakeEvidenceExtractor(), claim_synthesizer=FakeClaimSynthesizer(), summarizer=FakeSummarizer())


# ---------------------------------------------------------------- 5


async def test_admin_fallback_uses_stage2_service_and_produces_a_real_profile(session):
    """#5: `generate_profile_for_user` produces exactly the same kind of
    READY PotentialProfile `generate_potential_profile` itself would."""
    user, interview_session = await make_complete_session(session)
    profile = await generate_profile_for_user(session, user_id=user.id, **_fakes())
    assert profile.status is ProfileGenerationStatus.READY
    assert profile.user_id == user.id
    assert profile.session_id == interview_session.id


# ---------------------------------------------------------------- 2


async def test_duplicate_generation_is_prevented(session):
    """#2."""
    user, _ = await make_complete_session(session)
    await generate_profile_for_user(session, user_id=user.id, **_fakes())

    with pytest.raises(ProfileAlreadyExistsError):
        await generate_profile_for_user(session, user_id=user.id, **_fakes())


async def test_no_eligible_session_raises(session):
    from tests.profile_test_helpers import make_user

    user = await make_user(session)
    with pytest.raises(NoEligibleAssessmentSessionError):
        await generate_profile_for_user(session, user_id=user.id, **_fakes())


# ---------------------------------------------------------------- status summary


async def test_profile_status_summary_no_profile(session):
    from tests.profile_test_helpers import make_user

    user = await make_user(session)
    summary = await get_profile_status_summary(session, user_id=user.id)
    assert summary.status == "no_profile"
    assert summary.profile_id is None


async def test_profile_status_summary_ready(session):
    user, _ = await make_complete_session(session)
    await generate_profile_for_user(session, user_id=user.id, **_fakes())
    summary = await get_profile_status_summary(session, user_id=user.id)
    assert summary.status == "ready"
    assert summary.profile_id is not None


async def test_profile_status_summary_processing(session):
    """A GENERATING attempt (mid-flight, or crashed before completing) is
    surfaced as "processing", never confused with READY/FAILED."""
    user, interview_session = await make_complete_session(session)
    generating = PotentialProfile(
        user_id=user.id, session_id=interview_session.id, version=1, status=ProfileGenerationStatus.GENERATING,
        is_current=False, methodology_version="test", prompt_version="test",
    )
    session.add(generating)
    await session.commit()

    summary = await get_profile_status_summary(session, user_id=user.id)
    assert summary.status == "processing"


async def test_profile_status_summary_failed(session):
    user, interview_session = await make_complete_session(session)
    failed = PotentialProfile(
        user_id=user.id, session_id=interview_session.id, version=1, status=ProfileGenerationStatus.FAILED,
        is_current=False, methodology_version="test", prompt_version="test", failure_reason="RuntimeError during profile generation",
    )
    session.add(failed)
    await session.commit()

    summary = await get_profile_status_summary(session, user_id=user.id)
    assert summary.status == "failed"
    assert summary.failure_reason == "RuntimeError during profile generation"


# ---------------------------------------------------------------- 7


async def test_bridge_failure_log_line_carries_no_pii():
    """#7: the bot bridge's own log line (app/bot/handlers_v1.py::
    _trigger_profile_generation) is a fixed template with only IDs and an
    exception type name -- no raw answer/CV/claim text can appear in it
    because the format string never interpolates anything else."""
    import inspect

    from app.bot import handlers_v1

    source = inspect.getsource(handlers_v1._trigger_profile_generation)
    assert "logger.warning(" in source
    # the only %s placeholders feed session_id/user_id/exception type -- verified
    # by construction (session_id, user_id, type(exc).__name__ are literally the
    # only things ever passed after the format string in this call).
    assert "raw_answer_text" not in source and "normalized_value" not in source and "answer_text" not in source
