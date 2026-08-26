"""Shared fixtures/fakes for Stage 2 (Evidence + Potential Profile) tests
-- mirrors the FakeExtractor pattern already established for Stage 1's
AnswerExtractor tests."""

from __future__ import annotations

from app.core.security import hash_password
from app.db.models import AdminRole, AdminUser
from app.db.models_identity import IdentityUser
from app.services.assessment.extraction import ExtractionResult
from app.services.assessment.sessions import complete_assessment, start_assessment, submit_answer
from app.services.product_access import grant_manual_access
from app.services.profile.claim_synthesis import ClaimProposal, ClaimSynthesisResult
from app.services.profile.evidence_extraction import EvidenceExtractionResult, ExtractedEvidenceItem
from app.services.profile.summary import ProfileSummaryResult

REQUIRED_ANSWERS = {
    "name": "Олена",
    "city": "Київ",
    "current_status": "working",
    "key_skills_or_interests": "Люблю організовувати заходи та координувати людей",
    "desired_direction_hint": "IT або управління проєктами",
}


class FakeAnswerExtractor:
    def __init__(self, results=None):
        self._results = list(results) if results is not None else None
        self.calls = 0

    async def extract(self, *, question_prompt, raw_answer_text, previous_value):
        self.calls += 1
        if self._results is not None:
            return self._results.pop(0)
        return ExtractionResult(raw_answer_text, 0.9, False)


class FakeEvidenceExtractor:
    """Returns one evidence item per call by default, or a scripted
    mapping keyed by question_prompt (== question_id here)."""

    def __init__(self, items_by_question: dict[str, list[ExtractedEvidenceItem]] | None = None):
        self._items_by_question = items_by_question or {}
        self.calls: list[str] = []

    async def extract(self, *, question_prompt, raw_answer_text):
        self.calls.append(question_prompt)
        items = self._items_by_question.get(
            question_prompt,
            [ExtractedEvidenceItem(evidence_type=f"signal_{question_prompt}", normalized_text=raw_answer_text, confidence=0.8)],
        )
        return EvidenceExtractionResult(items=items, trace_id=f"trace-evidence-{len(self.calls)}")


class ExplodingEvidenceExtractor:
    def __init__(self, exc: Exception):
        self._exc = exc
        self.calls = 0

    async def extract(self, *, question_prompt, raw_answer_text):
        self.calls += 1
        raise self._exc


class FakeClaimSynthesizer:
    """By default proposes one claim per evidence item, 1:1, in the
    "strength" dimension -- callers needing specific grouping/contradiction
    scenarios pass an explicit `proposals_fn(evidence_items) -> list[ClaimProposal]`."""

    def __init__(self, proposals_fn=None):
        self._proposals_fn = proposals_fn
        self.calls = 0

    async def synthesize(self, *, evidence_items, taxonomy_terms):
        self.calls += 1
        if self._proposals_fn is not None:
            proposals = self._proposals_fn(evidence_items)
        else:
            from app.db.models_profile import ProfileDimension

            proposals = [
                ClaimProposal(
                    dimension=ProfileDimension.STRENGTH,
                    term_key=None,
                    label=f"Claim from {item.evidence_type}",
                    normalized_value=item.normalized_text,
                    evidence_indices=[i],
                    is_contradictory=False,
                )
                for i, item in enumerate(evidence_items)
            ]
        return ClaimSynthesisResult(proposals=proposals, trace_id="trace-claims-1")


class ExplodingClaimSynthesizer:
    def __init__(self, exc: Exception):
        self._exc = exc

    async def synthesize(self, *, evidence_items, taxonomy_terms):
        raise self._exc


class FakeSummarizer:
    def __init__(self, text: str = "Тестове резюме профілю."):
        self._text = text
        self.calls = 0

    async def summarize(self, *, claims, locale="uk"):
        self.calls += 1
        return ProfileSummaryResult(summary_text=self._text, trace_id="trace-summary-1")


async def make_admin(session, role=AdminRole.ADMIN, email="profile-admin@test.dev") -> AdminUser:
    admin = AdminUser(email=email, password_hash=hash_password("pw"), role=role)
    session.add(admin)
    await session.commit()
    await session.refresh(admin)
    return admin


async def make_user(session) -> IdentityUser:
    user = IdentityUser()
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def make_complete_session(session, *, plan_code: str = "BASIC"):
    """Creates a user with access, answers every required Hybrid question,
    and completes the assessment -- returns (user, interview_session) with
    interview_session.status == COMPLETE, ready for profile generation."""
    user = await make_user(session)
    admin = await make_admin(session)
    await grant_manual_access(session, user_id=user.id, plan_code=plan_code, granted_by_admin=admin)
    interview_session = await start_assessment(session, user_id=user.id, plan_code=plan_code)

    for i, (question_id, text) in enumerate(REQUIRED_ANSWERS.items()):
        extractor = None if question_id == "current_status" else FakeAnswerExtractor([ExtractionResult(text, 0.9, False)])
        await submit_answer(
            session, session_id=interview_session.id, user_id=user.id, question_id=question_id,
            raw_text=text, idempotency_key=f"seed-{i}", source="telegram", extractor=extractor,
        )

    await complete_assessment(session, session_id=interview_session.id, user_id=user.id)
    await session.refresh(interview_session)
    return user, interview_session
