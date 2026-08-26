"""Evidence Extraction (Stage 2 brief §4/§15/§16/§17, tests per §27
EVIDENCE section). Exercised through generate_potential_profile since
evidence extraction is an internal step of that orchestration, not a
separately public command -- the same way Stage 1 tests validate
next-question selection by inspecting DB rows after calling submit_answer.
"""

from sqlalchemy import select

from app.db.models_profile import Evidence, EvidenceSourceType
from app.services.profile.generation import generate_potential_profile
from tests.profile_test_helpers import FakeClaimSynthesizer, FakeEvidenceExtractor, FakeSummarizer, make_complete_session


async def _generate(session, user, interview_session, evidence_extractor=None):
    return await generate_potential_profile(
        session, session_id=interview_session.id, user_id=user.id,
        evidence_extractor=evidence_extractor or FakeEvidenceExtractor(),
        claim_synthesizer=FakeClaimSynthesizer(), summarizer=FakeSummarizer(),
    )


async def test_structured_answer_becomes_deterministic_evidence_with_no_ai_call(session_factory):
    async with session_factory() as session:
        user, interview_session = await make_complete_session(session)
        extractor = FakeEvidenceExtractor()

        await _generate(session, user, interview_session, extractor)

        result = await session.execute(
            select(Evidence).where(Evidence.session_id == interview_session.id, Evidence.source_type == EvidenceSourceType.STRUCTURED_ANSWER)
        )
        rows = result.scalars().all()
        assert len(rows) == 1  # "current_status" is the only structured required question
        assert rows[0].extraction_method == "deterministic"
        assert rows[0].confidence == 1.0
        assert rows[0].trace_id is None
        assert "current_status" not in extractor.calls  # never sent to the AI Gateway


async def test_open_answer_becomes_llm_extracted_evidence_with_provenance(session_factory):
    async with session_factory() as session:
        user, interview_session = await make_complete_session(session)
        extractor = FakeEvidenceExtractor()

        await _generate(session, user, interview_session, extractor)

        result = await session.execute(
            select(Evidence).where(Evidence.session_id == interview_session.id, Evidence.source_type == EvidenceSourceType.OPEN_ANSWER)
        )
        rows = result.scalars().all()
        assert len(rows) > 0
        for row in rows:
            assert row.extraction_method == "llm_extraction"
            assert row.trace_id is not None  # AI trace/provenance retained
            assert row.taxonomy_version_id is not None


async def test_cv_derived_answer_becomes_cv_sourced_evidence(session_factory):
    from unittest.mock import patch

    import app.services.documents as documents
    from app.services.assessment.cv import upload_cv
    from app.services.assessment.extraction import ExtractionResult
    from app.services.assessment.sessions import complete_assessment, start_assessment, submit_answer
    from app.services.product_access import grant_manual_access
    from tests.profile_test_helpers import make_admin, make_user

    class CVPassExtractor:
        """CV extraction resolves "key_skills_or_interests" confidently;
        everything else the CV pass tries stays below the confidence bar
        so it's left for a normal answer."""

        async def extract(self, *, question_prompt, raw_answer_text, previous_value):
            if question_prompt == "key_skills_or_interests":
                return ExtractionResult("Python, координація команд", 0.9, False)
            return ExtractionResult("", 0.1, False)

    class NormalAnswerExtractor:
        async def extract(self, *, question_prompt, raw_answer_text, previous_value):
            return ExtractionResult(raw_answer_text, 0.9, False)

    async with session_factory() as session:
        user = await make_user(session)
        admin = await make_admin(session)
        await grant_manual_access(session, user_id=user.id, plan_code="BASIC", granted_by_admin=admin)
        interview_session = await start_assessment(session, user_id=user.id, plan_code="BASIC")

        with patch.object(documents, "extract_text", return_value="Python, координація команд, Siemens 2011-2015"):
            await upload_cv(
                session, session_id=interview_session.id, user_id=user.id, filename="cv.pdf",
                content_bytes=b"fake", extractor=CVPassExtractor(),
            )

        remaining = {"name": "Олена", "city": "Київ", "current_status": "working", "desired_direction_hint": "IT"}
        for i, (question_id, text) in enumerate(remaining.items()):
            extractor = None if question_id == "current_status" else NormalAnswerExtractor()
            await submit_answer(
                session, session_id=interview_session.id, user_id=user.id, question_id=question_id,
                raw_text=text, idempotency_key=f"k{i}", source="telegram", extractor=extractor,
            )
        await complete_assessment(session, session_id=interview_session.id, user_id=user.id)

        await _generate(session, user, interview_session, FakeEvidenceExtractor())

        result = await session.execute(
            select(Evidence).where(Evidence.session_id == interview_session.id, Evidence.source_type == EvidenceSourceType.CV)
        )
        cv_evidence = result.scalars().all()
        assert len(cv_evidence) > 0


async def test_no_duplicate_evidence_on_regeneration(session_factory):
    async with session_factory() as session:
        user, interview_session = await make_complete_session(session)
        extractor = FakeEvidenceExtractor()

        await _generate(session, user, interview_session, extractor)
        first_call_count = len(extractor.calls)

        await _generate(session, user, interview_session, extractor)

        result = await session.execute(select(Evidence).where(Evidence.session_id == interview_session.id))
        all_evidence = result.scalars().all()
        source_pairs = [(e.source_type, e.source_id, e.evidence_type) for e in all_evidence]
        assert len(source_pairs) == len(set(source_pairs))  # no duplicates
        assert len(extractor.calls) == first_call_count  # regeneration made zero new AI calls -- evidence reused


async def test_pending_answer_is_never_turned_into_evidence(session_factory):
    """A stale/pending Answer reservation (extracted_value IS NULL) must
    never become Evidence -- proven by inserting one directly and
    confirming generation ignores it entirely."""
    from app.db.models_assessment import Answer

    async with session_factory() as session:
        user, interview_session = await make_complete_session(session)

        pending = Answer(
            session_id=interview_session.id, question_id="total_experience", answer_text="...",
            extracted_value=None, confidence=None, contradicts_previous=False,
            source="telegram", idempotency_key="pending-key",
        )
        session.add(pending)
        await session.commit()

        extractor = FakeEvidenceExtractor()
        await _generate(session, user, interview_session, extractor)

        assert "total_experience" not in extractor.calls
        result = await session.execute(select(Evidence).where(Evidence.session_id == interview_session.id))
        for row in result.scalars().all():
            assert row.source_id != pending.id
