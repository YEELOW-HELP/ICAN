"""Stage 2 profile-generation orchestration (Issue #2, brief §12):

Evidence Extraction -> Evidence normalization -> Profile Claims ->
Confidence/provenance -> Potential Profile version -> Summary.

## InterviewSession.status vs PotentialProfile.status

These are deliberately two separate state machines, not one:

- `InterviewSession.status` transitions `COMPLETE -> PROCESSING -> READY`
  exactly ONCE per session, marking "this assessment's data collection
  phase has concluded and produced at least one profile." Stage 1's state
  machine (app/services/assessment/state_machine.py) makes `READY` and
  `FAILED` fully terminal with zero legal outgoing transitions -- a
  hardened, tested Stage 1 invariant this module does not touch or
  weaken. Once `READY`, `InterviewSession.status` never changes again,
  even across many later profile regenerations.
- `PotentialProfile.status` (`GENERATING` -> `READY` | `FAILED`) is the
  per-attempt, per-version lifecycle. Every generation attempt --
  the first one, a retry, or a later regeneration -- is its own
  permanent, versioned row. A FAILED attempt's row is never deleted
  (audit trail) and is never marked `is_current`.

If a generation attempt fails, `InterviewSession.status` is deliberately
LEFT AT `PROCESSING` (not moved to `FAILED`) -- mirroring Stage 1's own
`submit_answer` precedent ("a provider failure must not... move the
session to FAILED; it stays ACTIVE for the next attempt"). This is what
makes retry actually possible: a session sitting at `PROCESSING` is
exactly eligible to call `generate_potential_profile` again. Moving
`InterviewSession` to `FAILED` would make it permanently terminal per
Stage 1's own hardened test (`test_failed_is_terminal_no_outgoing_transition_exists`)
and would make retry impossible without breaking that guarantee --
so Stage 2 does not do that automatically. `PROCESSING -> FAILED` remains
a real, legal, tested transition on `InterviewSession` (unchanged from
Stage 1), reserved for a deliberate administrative "give up entirely" via
`fail_session()` -- never invoked automatically here.

## Versioning and concurrency

`PotentialProfile.version` is scoped per `user_id` (not per session) --
the Human Potential Profile is a per-person concept the ERD models as one
evolving thing across possibly-multiple assessment sessions over time
(`docs/architecture/02_ERD.md`'s `USER ||--|| POTENTIAL_PROFILE`), with
each version additionally tagged with which session produced it. Only one
profile-generation attempt may be `GENERATING` per user at a time
(`ProfileGenerationInProgressError` otherwise) -- this, plus the partial
unique index on `is_current`, is what "do not accidentally create
multiple uncontrolled profile versions" (brief §10/§12) means concretely.

Evidence is extracted once per (session, answer) and reused across
regenerations -- a retry or later regeneration only extracts evidence for
answers that don't have any yet, never re-spending AI Gateway calls on
already-processed answers.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_assessment import Answer, AssessmentStatus
from app.db.models_profile import (
    Evidence,
    EvidenceSourceType,
    PotentialProfile,
    ProfileClaim,
    ProfileClaimEvidence,
    ProfileGenerationStatus,
    TaxonomyTerm,
)
from app.services.assessment import state_machine
from app.services.assessment.question_bank import QUESTIONS_BY_ID
from app.services.assessment.sessions import get_owned_session, recover_stale_pending_answers
from app.services.events import emit_event
from app.services.exceptions import (
    AssessmentOwnershipError,
    InvalidStateTransitionError,
    NoCurrentProfileError,
    ProfileGenerationInProgressError,
)
from app.services.profile.claim_synthesis import PROMPT_VERSION as CLAIM_SYNTHESIS_PROMPT_VERSION
from app.services.profile.claim_synthesis import ClaimProposal, ClaimSynthesizer, compute_claim_confidence
from app.services.profile.evidence_extraction import EvidenceExtractor
from app.services.profile.summary import ProfileSummarizer
from app.services.profile.taxonomy import ensure_seed_taxonomy

_ELIGIBLE_STATUSES = {AssessmentStatus.COMPLETE, AssessmentStatus.PROCESSING, AssessmentStatus.READY}


async def generate_potential_profile(
    session: AsyncSession,
    *,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    evidence_extractor: EvidenceExtractor | None = None,
    claim_synthesizer: ClaimSynthesizer | None = None,
    summarizer: ProfileSummarizer | None = None,
    locale: str = "uk",
) -> PotentialProfile:
    interview_session = await get_owned_session(session, session_id=session_id, user_id=user_id)
    if interview_session.status not in _ELIGIBLE_STATUSES:
        raise InvalidStateTransitionError(
            f"InterviewSession {session_id} in status {interview_session.status.value} is not eligible for profile generation"
        )

    in_flight = await session.execute(
        select(PotentialProfile.id).where(
            PotentialProfile.user_id == user_id, PotentialProfile.status == ProfileGenerationStatus.GENERATING
        )
    )
    if in_flight.scalar_one_or_none() is not None:
        raise ProfileGenerationInProgressError(f"user {user_id} already has a profile generation in progress")

    if interview_session.status == AssessmentStatus.COMPLETE:
        state_machine.transition(interview_session, AssessmentStatus.PROCESSING)
        await session.commit()

    taxonomy_version = await ensure_seed_taxonomy(session)

    next_version = (
        await session.execute(select(func.coalesce(func.max(PotentialProfile.version), 0)).where(PotentialProfile.user_id == user_id))
    ).scalar_one() + 1

    profile = PotentialProfile(
        user_id=user_id,
        session_id=session_id,
        version=next_version,
        status=ProfileGenerationStatus.GENERATING,
        is_current=False,
        methodology_version=f"potential_dimensions:v{taxonomy_version.version}",
        prompt_version=CLAIM_SYNTHESIS_PROMPT_VERSION,
    )
    session.add(profile)
    await session.commit()
    await session.refresh(profile)
    emit_event(
        "profile_generation_started", user_id=str(user_id), session_id=str(session_id),
        profile_id=str(profile.id), version=profile.version,
    )

    try:
        await recover_stale_pending_answers(session, session_id)
        answers = (
            await session.execute(
                select(Answer)
                .where(Answer.session_id == session_id, Answer.extracted_value.isnot(None))
                .order_by(Answer.created_at)
            )
        ).scalars().all()

        new_evidence_count = await _extract_evidence_for_answers(
            session, user_id=user_id, session_id=session_id, answers=answers,
            extractor=evidence_extractor or EvidenceExtractor(), taxonomy_version_id=taxonomy_version.id,
        )
        emit_event(
            "evidence_extracted", user_id=str(user_id), session_id=str(session_id),
            profile_id=str(profile.id), new_evidence_count=new_evidence_count,
        )

        all_evidence = (
            await session.execute(select(Evidence).where(Evidence.session_id == session_id).order_by(Evidence.created_at))
        ).scalars().all()

        vocabulary = (
            await session.execute(
                select(TaxonomyTerm.term_key, TaxonomyTerm.dimension, TaxonomyTerm.label_uk).where(
                    TaxonomyTerm.taxonomy_version_id == taxonomy_version.id
                )
            )
        ).all()

        synthesis_result = await (claim_synthesizer or ClaimSynthesizer()).synthesize(
            evidence_items=list(all_evidence), taxonomy_terms=[tuple(row) for row in vocabulary]
        )
        claims = await _persist_claims(
            session, profile_id=profile.id, all_evidence=list(all_evidence),
            proposals=synthesis_result.proposals, trace_id=synthesis_result.trace_id,
        )

        summary_result = await (summarizer or ProfileSummarizer()).summarize(claims=claims, locale=locale)

        profile.status = ProfileGenerationStatus.READY
        profile.generated_at = datetime.now(timezone.utc)
        profile.summary_text = summary_result.summary_text
        profile.summary_locale = locale
        profile.trace_id = summary_result.trace_id
        await _mark_previous_not_current(session, user_id=user_id, keep_profile_id=profile.id)
        profile.is_current = True
        await session.commit()
        await session.refresh(profile)

        if interview_session.status == AssessmentStatus.PROCESSING:
            state_machine.transition(interview_session, AssessmentStatus.READY)
            await session.commit()

        emit_event(
            "profile_generated", user_id=str(user_id), session_id=str(session_id),
            profile_id=str(profile.id), version=profile.version, claim_count=len(claims),
        )
        return profile

    except Exception as exc:
        # Never store the raw exception text verbatim -- a provider
        # exception could in rare cases echo request content back; only
        # the exception's type is safe to persist/emit (Section 24).
        profile.status = ProfileGenerationStatus.FAILED
        profile.failure_reason = f"{type(exc).__name__} during profile generation"
        await session.commit()
        emit_event(
            "profile_generation_failed", user_id=str(user_id), session_id=str(session_id),
            profile_id=str(profile.id), error_type=type(exc).__name__,
        )
        raise


async def _extract_evidence_for_answers(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    answers: list[Answer],
    extractor: EvidenceExtractor,
    taxonomy_version_id: uuid.UUID,
) -> int:
    created = 0
    for answer in answers:
        question = QUESTIONS_BY_ID.get(answer.question_id)
        is_structured = question is not None and question.kind == "structured" and answer.source != "cv"
        source_type = (
            EvidenceSourceType.STRUCTURED_ANSWER
            if is_structured
            else (EvidenceSourceType.CV if answer.source == "cv" else EvidenceSourceType.OPEN_ANSWER)
        )

        already_processed = await session.execute(
            select(Evidence.id)
            .where(Evidence.session_id == session_id, Evidence.source_type == source_type, Evidence.source_id == answer.id)
            .limit(1)
        )
        if already_processed.scalar_one_or_none() is not None:
            continue  # evidence for this answer already exists -- reused across regenerations/retries

        if source_type == EvidenceSourceType.STRUCTURED_ANSWER:
            if await _try_add_evidence(
                session,
                Evidence(
                    user_id=user_id, session_id=session_id, source_type=source_type, source_id=answer.id,
                    evidence_type=f"answer:{answer.question_id}", taxonomy_version_id=None,
                    normalized_text=f"{answer.question_id}: {answer.extracted_value}",
                    confidence=answer.confidence if answer.confidence is not None else 1.0,
                    extraction_method="deterministic", trace_id=None,
                ),
            ):
                created += 1
            continue

        extraction = await extractor.extract(question_prompt=answer.question_id, raw_answer_text=answer.answer_text)
        for item in extraction.items:
            if await _try_add_evidence(
                session,
                Evidence(
                    user_id=user_id, session_id=session_id, source_type=source_type, source_id=answer.id,
                    evidence_type=item.evidence_type, taxonomy_version_id=taxonomy_version_id,
                    normalized_text=item.normalized_text, confidence=item.confidence,
                    extraction_method="llm_extraction", trace_id=extraction.trace_id,
                ),
            ):
                created += 1
    return created


async def _try_add_evidence(session: AsyncSession, evidence: Evidence) -> bool:
    """Commits one Evidence row; returns False (no-op) instead of raising
    if a duplicate (session_id, source_type, source_id, evidence_type)
    already exists -- the UNIQUE constraint is the authoritative
    idempotency guard, this is just the friendly recovery path."""
    session.add(evidence)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        return False
    return True


async def _persist_claims(
    session: AsyncSession,
    *,
    profile_id: uuid.UUID,
    all_evidence: list[Evidence],
    proposals: list[ClaimProposal],
    trace_id: str | None,
) -> list[ProfileClaim]:
    claims: list[ProfileClaim] = []
    for proposal in proposals:
        # Defense in depth: ClaimSynthesizer is a pluggable interface, so
        # this does not blindly trust that evidence_indices were already
        # bounds-checked upstream (claim_synthesis.py's own
        # _validate_proposals does this too, for the real AI-backed path).
        supporting = [all_evidence[i] for i in proposal.evidence_indices if 0 <= i < len(all_evidence)]
        result = compute_claim_confidence(supporting, is_contradictory=proposal.is_contradictory)
        if result is None:
            continue  # no valid evidence -- never persisted as a claim (brief §5/§7)
        confidence, status = result

        claim = ProfileClaim(
            profile_id=profile_id,
            dimension=proposal.dimension,
            taxonomy_version_id=next((e.taxonomy_version_id for e in supporting if e.taxonomy_version_id), None),
            term_key=proposal.term_key,
            label=proposal.label,
            normalized_value=proposal.normalized_value,
            confidence=confidence,
            status=status,
            generated_by="claim-synthesis-v1",
            trace_id=trace_id,
        )
        session.add(claim)
        await session.flush()
        for evidence_item in supporting:
            session.add(ProfileClaimEvidence(claim_id=claim.id, evidence_id=evidence_item.id))
        claims.append(claim)

    await session.commit()
    for claim in claims:
        await session.refresh(claim)
    return claims


async def _mark_previous_not_current(session: AsyncSession, *, user_id: uuid.UUID, keep_profile_id: uuid.UUID) -> None:
    current = (
        await session.execute(
            select(PotentialProfile).where(PotentialProfile.user_id == user_id, PotentialProfile.is_current.is_(True))
        )
    ).scalars().all()
    for row in current:
        if row.id != keep_profile_id:
            row.is_current = False
    await session.flush()


async def get_current_profile(session: AsyncSession, *, user_id: uuid.UUID) -> PotentialProfile | None:
    result = await session.execute(
        select(PotentialProfile).where(PotentialProfile.user_id == user_id, PotentialProfile.is_current.is_(True))
    )
    return result.scalar_one_or_none()


async def get_owned_profile(session: AsyncSession, *, profile_id: uuid.UUID, user_id: uuid.UUID) -> PotentialProfile:
    profile = await session.get(PotentialProfile, profile_id)
    if profile is None:
        raise NoCurrentProfileError(f"PotentialProfile {profile_id} does not exist")
    if profile.user_id != user_id:
        raise AssessmentOwnershipError(f"user {user_id} does not own PotentialProfile {profile_id}")
    return profile


async def explain_claim(session: AsyncSession, *, claim_id: uuid.UUID) -> list[Evidence]:
    """"Why do we think this is true?" (brief §6) -- the concrete evidence
    rows behind one claim, via the many-to-many join."""
    result = await session.execute(
        select(Evidence)
        .join(ProfileClaimEvidence, ProfileClaimEvidence.evidence_id == Evidence.id)
        .where(ProfileClaimEvidence.claim_id == claim_id)
        .order_by(Evidence.created_at)
    )
    return list(result.scalars().all())
