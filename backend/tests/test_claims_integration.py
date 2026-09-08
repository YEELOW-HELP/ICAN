"""Claim persistence through the full pipeline (Stage 2 brief §27 CLAIMS:
evidence links preserved, unsupported claim rejected/not emitted, "why do
we think this" explainability).
"""

from sqlalchemy import select

from app.db.models_profile import ClaimStatus, ProfileClaim, ProfileClaimEvidence, ProfileDimension
from app.services.profile.claim_synthesis import ClaimProposal
from app.services.profile.generation import explain_claim, generate_potential_profile
from tests.profile_test_helpers import FakeClaimSynthesizer, FakeEvidenceExtractor, FakeSummarizer, make_complete_session


async def test_claim_with_multiple_evidence_links_preserved(session_factory):
    async with session_factory() as session:
        user, interview_session = await make_complete_session(session)

        def group_all_into_one_claim(evidence_items):
            return [
                ClaimProposal(
                    dimension=ProfileDimension.STRENGTH, term_key=None, label="Координація",
                    normalized_value="Схильність координувати", evidence_indices=list(range(len(evidence_items))),
                    is_contradictory=False,
                )
            ]

        await generate_potential_profile(
            session, session_id=interview_session.id, user_id=user.id,
            evidence_extractor=FakeEvidenceExtractor(), claim_synthesizer=FakeClaimSynthesizer(group_all_into_one_claim),
            summarizer=FakeSummarizer(),
        )

        claim = (await session.execute(select(ProfileClaim))).scalars().one()
        links = (await session.execute(select(ProfileClaimEvidence).where(ProfileClaimEvidence.claim_id == claim.id))).scalars().all()
        assert len(links) > 1  # multiple evidence items support this one claim

        evidence_via_explain = await explain_claim(session, claim_id=claim.id)
        assert len(evidence_via_explain) == len(links)  # "why do we think this" resolves the same set


async def test_claim_referencing_no_evidence_is_never_persisted(session_factory):
    async with session_factory() as session:
        user, interview_session = await make_complete_session(session)

        def propose_ungrounded_claim(evidence_items):
            return [
                ClaimProposal(
                    dimension=ProfileDimension.TRAIT, term_key=None, label="Вигадана риса",
                    normalized_value="Нічим не підтверджено", evidence_indices=[], is_contradictory=False,
                )
            ]

        await generate_potential_profile(
            session, session_id=interview_session.id, user_id=user.id,
            evidence_extractor=FakeEvidenceExtractor(), claim_synthesizer=FakeClaimSynthesizer(propose_ungrounded_claim),
            summarizer=FakeSummarizer(),
        )

        claims = (await session.execute(select(ProfileClaim))).scalars().all()
        assert all(c.label != "Вигадана риса" for c in claims)


async def test_claim_referencing_out_of_range_evidence_index_is_dropped(session_factory):
    """A hallucinated evidence_indices value (pointing past the real
    evidence list) must be dropped by validation, not crash or silently
    accept a fabricated grounding."""
    async with session_factory() as session:
        user, interview_session = await make_complete_session(session)

        def propose_out_of_range(evidence_items):
            return [
                ClaimProposal(
                    dimension=ProfileDimension.SKILL, term_key=None, label="Помилкове посилання",
                    normalized_value="...", evidence_indices=[9999], is_contradictory=False,
                )
            ]

        await generate_potential_profile(
            session, session_id=interview_session.id, user_id=user.id,
            evidence_extractor=FakeEvidenceExtractor(), claim_synthesizer=FakeClaimSynthesizer(propose_out_of_range),
            summarizer=FakeSummarizer(),
        )

        claims = (await session.execute(select(ProfileClaim))).scalars().all()
        assert all(c.label != "Помилкове посилання" for c in claims)


async def test_contradictory_claim_retains_both_conflicting_evidence_items(session_factory):
    async with session_factory() as session:
        user, interview_session = await make_complete_session(session)

        def propose_contradiction(evidence_items):
            if len(evidence_items) < 2:
                return []
            return [
                ClaimProposal(
                    dimension=ProfileDimension.WORK_PREFERENCE, term_key=None, label="Командна робота проти самотньої",
                    normalized_value="Суперечливі сигнали щодо командної роботи",
                    evidence_indices=[0, 1], is_contradictory=True,
                )
            ]

        await generate_potential_profile(
            session, session_id=interview_session.id, user_id=user.id,
            evidence_extractor=FakeEvidenceExtractor(), claim_synthesizer=FakeClaimSynthesizer(propose_contradiction),
            summarizer=FakeSummarizer(),
        )

        claim = (
            await session.execute(select(ProfileClaim).where(ProfileClaim.label == "Командна робота проти самотньої"))
        ).scalars().one()
        assert claim.status == ClaimStatus.CONTRADICTED

        links = (await session.execute(select(ProfileClaimEvidence).where(ProfileClaimEvidence.claim_id == claim.id))).scalars().all()
        assert len(links) == 2  # both sides of the contradiction are retained, not one dropped
