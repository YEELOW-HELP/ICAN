"""Stage 2 brief §27 SECURITY: a user cannot generate or read another
user's profile. Ownership is enforced by the same get_owned_session
choke point Stage 1 already uses for InterviewSession, plus a dedicated
ownership check on PotentialProfile reads.
"""

import pytest

from app.services.exceptions import AssessmentOwnershipError, NoCurrentProfileError
from app.services.profile.generation import generate_potential_profile, get_current_profile, get_owned_profile
from tests.profile_test_helpers import FakeClaimSynthesizer, FakeEvidenceExtractor, FakeSummarizer, make_complete_session, make_user


async def _generate(session, user, interview_session):
    return await generate_potential_profile(
        session, session_id=interview_session.id, user_id=user.id,
        evidence_extractor=FakeEvidenceExtractor(), claim_synthesizer=FakeClaimSynthesizer(),
        summarizer=FakeSummarizer(),
    )


async def test_intruder_cannot_read_owners_profile_by_id(session_factory):
    async with session_factory() as session:
        owner, interview_session = await make_complete_session(session)
        intruder = await make_user(session)
        profile = await _generate(session, owner, interview_session)

        with pytest.raises(AssessmentOwnershipError):
            await get_owned_profile(session, profile_id=profile.id, user_id=intruder.id)


async def test_owner_can_read_their_own_profile_by_id(session_factory):
    async with session_factory() as session:
        owner, interview_session = await make_complete_session(session)
        profile = await _generate(session, owner, interview_session)

        fetched = await get_owned_profile(session, profile_id=profile.id, user_id=owner.id)
        assert fetched.id == profile.id


async def test_get_current_profile_never_returns_another_users_profile(session_factory):
    async with session_factory() as session:
        owner, interview_session = await make_complete_session(session)
        intruder = await make_user(session)
        await _generate(session, owner, interview_session)

        assert await get_current_profile(session, user_id=intruder.id) is None
        current = await get_current_profile(session, user_id=owner.id)
        assert current is not None
        assert current.user_id == owner.id


async def test_reading_a_nonexistent_profile_raises_not_ownership_confusion(session_factory):
    import uuid

    async with session_factory() as session:
        owner, _ = await make_complete_session(session)
        with pytest.raises(NoCurrentProfileError):
            await get_owned_profile(session, profile_id=uuid.uuid4(), user_id=owner.id)
