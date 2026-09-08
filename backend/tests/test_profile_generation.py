"""Profile generation orchestration (Stage 2 brief §12/§27 PROFILE tests):
COMPLETE -> PROCESSING -> READY, versioning, regeneration, failure/retry.
"""

import pytest

from app.db.models_assessment import AssessmentStatus
from app.db.models_profile import ProfileGenerationStatus
from app.services.exceptions import (
    AssessmentOwnershipError,
    InvalidStateTransitionError,
    ProfileGenerationInProgressError,
)
from app.services.profile.generation import generate_potential_profile, get_current_profile
from tests.profile_test_helpers import (
    ExplodingClaimSynthesizer,
    ExplodingEvidenceExtractor,
    FakeClaimSynthesizer,
    FakeEvidenceExtractor,
    FakeSummarizer,
    make_complete_session,
    make_user,
)


async def test_generation_from_complete_assessment_reaches_ready(session_factory):
    async with session_factory() as session:
        user, interview_session = await make_complete_session(session)

        profile = await generate_potential_profile(
            session, session_id=interview_session.id, user_id=user.id,
            evidence_extractor=FakeEvidenceExtractor(), claim_synthesizer=FakeClaimSynthesizer(),
            summarizer=FakeSummarizer(),
        )

        assert profile.status == ProfileGenerationStatus.READY
        assert profile.version == 1
        assert profile.is_current is True
        assert profile.generated_at is not None
        assert profile.summary_text == "Тестове резюме профілю."

        await session.refresh(interview_session)
        assert interview_session.status == AssessmentStatus.READY


async def test_complete_to_processing_to_ready_sequence(session_factory):
    """Directly observes the InterviewSession transitioning through
    PROCESSING mid-generation, not just the final READY state."""
    async with session_factory() as session:
        user, interview_session = await make_complete_session(session)

        observed_statuses = []

        class ObservingExtractor(FakeEvidenceExtractor):
            async def extract(self, *, question_prompt, raw_answer_text):
                observed_statuses.append(interview_session.status)
                return await super().extract(question_prompt=question_prompt, raw_answer_text=raw_answer_text)

        await generate_potential_profile(
            session, session_id=interview_session.id, user_id=user.id,
            evidence_extractor=ObservingExtractor(), claim_synthesizer=FakeClaimSynthesizer(),
            summarizer=FakeSummarizer(),
        )

        assert all(status == AssessmentStatus.PROCESSING for status in observed_statuses)


async def test_regeneration_creates_version_2_and_preserves_version_1(session_factory):
    async with session_factory() as session:
        user, interview_session = await make_complete_session(session)

        v1 = await generate_potential_profile(
            session, session_id=interview_session.id, user_id=user.id,
            evidence_extractor=FakeEvidenceExtractor(), claim_synthesizer=FakeClaimSynthesizer(),
            summarizer=FakeSummarizer(),
        )
        v2 = await generate_potential_profile(
            session, session_id=interview_session.id, user_id=user.id,
            evidence_extractor=FakeEvidenceExtractor(), claim_synthesizer=FakeClaimSynthesizer(),
            summarizer=FakeSummarizer("Друге резюме."),
        )

        assert v2.version == 2
        assert v2.id != v1.id
        assert v2.is_current is True

        await session.refresh(v1)
        assert v1.is_current is False
        assert v1.status == ProfileGenerationStatus.READY  # history preserved, not deleted/edited

        current = await get_current_profile(session, user_id=user.id)
        assert current.id == v2.id

        # InterviewSession stays READY throughout regeneration -- it does
        # not re-enter PROCESSING (Stage 1's READY-is-terminal invariant
        # is never touched by Stage 2).
        await session.refresh(interview_session)
        assert interview_session.status == AssessmentStatus.READY


async def test_generation_failure_marks_profile_failed_and_leaves_session_processing(session_factory):
    async with session_factory() as session:
        user, interview_session = await make_complete_session(session)

        with pytest.raises(ConnectionError):
            await generate_potential_profile(
                session, session_id=interview_session.id, user_id=user.id,
                evidence_extractor=ExplodingEvidenceExtractor(ConnectionError("provider outage")),
                claim_synthesizer=FakeClaimSynthesizer(), summarizer=FakeSummarizer(),
            )

        await session.refresh(interview_session)
        assert interview_session.status == AssessmentStatus.PROCESSING  # not FAILED -- retry stays possible

        from sqlalchemy import select

        from app.db.models_profile import PotentialProfile

        result = await session.execute(select(PotentialProfile).where(PotentialProfile.session_id == interview_session.id))
        profiles = result.scalars().all()
        assert len(profiles) == 1
        assert profiles[0].status == ProfileGenerationStatus.FAILED
        assert profiles[0].is_current is False
        assert "ConnectionError" in profiles[0].failure_reason
        assert "provider outage" not in profiles[0].failure_reason  # raw exception text never persisted


async def test_retry_after_failure_succeeds_and_reaches_ready(session_factory):
    async with session_factory() as session:
        user, interview_session = await make_complete_session(session)

        with pytest.raises(RuntimeError):
            await generate_potential_profile(
                session, session_id=interview_session.id, user_id=user.id,
                evidence_extractor=ExplodingEvidenceExtractor(RuntimeError("boom")),
                claim_synthesizer=FakeClaimSynthesizer(), summarizer=FakeSummarizer(),
            )

        profile = await generate_potential_profile(
            session, session_id=interview_session.id, user_id=user.id,
            evidence_extractor=FakeEvidenceExtractor(), claim_synthesizer=FakeClaimSynthesizer(),
            summarizer=FakeSummarizer(),
        )

        assert profile.status == ProfileGenerationStatus.READY
        assert profile.version == 2  # the failed attempt still consumed version 1, permanently

        await session.refresh(interview_session)
        assert interview_session.status == AssessmentStatus.READY


async def test_claim_synthesis_failure_also_marks_profile_failed(session_factory):
    async with session_factory() as session:
        user, interview_session = await make_complete_session(session)

        with pytest.raises(TimeoutError):
            await generate_potential_profile(
                session, session_id=interview_session.id, user_id=user.id,
                evidence_extractor=FakeEvidenceExtractor(),
                claim_synthesizer=ExplodingClaimSynthesizer(TimeoutError("synth timeout")),
                summarizer=FakeSummarizer(),
            )

        from sqlalchemy import select

        from app.db.models_profile import Evidence, PotentialProfile

        # Evidence extracted before the failure is preserved, not rolled
        # back -- partial progress from a failed attempt survives so a
        # retry doesn't re-spend AI calls on already-processed answers.
        evidence_count = (
            await session.execute(select(Evidence).where(Evidence.session_id == interview_session.id))
        ).scalars().all()
        assert len(evidence_count) > 0

        profile = (
            await session.execute(select(PotentialProfile).where(PotentialProfile.session_id == interview_session.id))
        ).scalars().one()
        assert profile.status == ProfileGenerationStatus.FAILED


async def test_cannot_start_second_generation_while_one_is_in_progress(session_factory):
    async with session_factory() as session:
        user, interview_session = await make_complete_session(session)

        from app.db.models_profile import PotentialProfile, ProfileGenerationStatus as Status

        blocking = PotentialProfile(
            user_id=user.id, session_id=interview_session.id, version=1, status=Status.GENERATING,
            is_current=False, methodology_version="potential_dimensions:v1", prompt_version="claim-synthesis-v1",
        )
        session.add(blocking)
        await session.commit()

        with pytest.raises(ProfileGenerationInProgressError):
            await generate_potential_profile(
                session, session_id=interview_session.id, user_id=user.id,
                evidence_extractor=FakeEvidenceExtractor(), claim_synthesizer=FakeClaimSynthesizer(),
                summarizer=FakeSummarizer(),
            )


async def test_cannot_generate_profile_from_a_non_terminal_assessment(session_factory):
    from app.services.assessment.sessions import start_assessment
    from app.services.product_access import grant_manual_access
    from tests.profile_test_helpers import make_admin

    async with session_factory() as session:
        user = await make_user(session)
        admin = await make_admin(session)
        await grant_manual_access(session, user_id=user.id, plan_code="BASIC", granted_by_admin=admin)
        interview_session = await start_assessment(session, user_id=user.id, plan_code="BASIC")  # DRAFT, not COMPLETE

        with pytest.raises(InvalidStateTransitionError):
            await generate_potential_profile(
                session, session_id=interview_session.id, user_id=user.id,
                evidence_extractor=FakeEvidenceExtractor(), claim_synthesizer=FakeClaimSynthesizer(),
                summarizer=FakeSummarizer(),
            )


async def test_user_cannot_generate_another_users_profile(session_factory):
    async with session_factory() as session:
        owner, interview_session = await make_complete_session(session)
        intruder = await make_user(session)

        with pytest.raises(AssessmentOwnershipError):
            await generate_potential_profile(
                session, session_id=interview_session.id, user_id=intruder.id,
                evidence_extractor=FakeEvidenceExtractor(), claim_synthesizer=FakeClaimSynthesizer(),
                summarizer=FakeSummarizer(),
            )
