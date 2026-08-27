"""Stage 3B Slice 3 §4/§5/§6/§7: consultant review state machine, append-
only corrections, and the approval gate.

## State machine

    PENDING_REVIEW -> APPROVED | CHANGES_REQUESTED | REJECTED

Mirrors `app/services/assessment/state_machine.py`'s discipline: this
module is the only code allowed to change `DirectionReview.status`.
APPROVED/CHANGES_REQUESTED/REJECTED are all terminal for that review row
-- a regeneration (`app.services.direction.pipeline.generate_directions`)
creates a brand NEW `DirectionRun` and therefore a brand new
`DirectionReview` at PENDING_REVIEW; it never reopens an old one, and the
old run + its review stay immutable/auditable forever
(`get_approved_direction_run` only ever returns the run an APPROVED
review actually points at, by exact version).

## RBAC

`AdminRole.CAREER_CONSULTANT`, `AdminRole.ADMIN`, `AdminRole.SUPER_ADMIN`
may act on a review -- the same pairing CRM's own API layer already uses
for career-consultant actions (`app/api/crm.py`'s
`_require_roles(admin, AdminRole.ADMIN, AdminRole.CAREER_CONSULTANT)`),
plus the universal `SUPER_ADMIN` override already used the same way in
`app/services/product_access.py`. No new role is invented.

## Corrections are append-only

`ConsultantCorrection` rows are only ever INSERTed, never UPDATEd or
DELETEd (mirrors `AuditLog`). The underlying `DirectionRun`/`Direction`
rows are NEVER mutated by a correction -- `original_value`/
`corrected_value` are captured as data on the correction row itself. A
`wording_only` correction to the narrative must never touch the four
output scores or ranking (`correct_narrative_wording` only ever writes
`artifact_type="narrative"` corrections and never accepts a placement/
score field).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AdminRole, AdminUser
from app.db.models_direction import (
    ConsultantCorrection,
    CorrectionReasonCode,
    CriticSeverity,
    Direction,
    DirectionCriticFinding,
    DirectionReview,
    DirectionRun,
    DirectionRunStatus,
    ReviewStatus,
    ScoringConfig,
)
from app.services.events import emit_event
from app.services.exceptions import (
    DirectionReviewNotFoundError,
    DirectionRunHasUnresolvedBlockerError,
    InsufficientRoleError,
    InvalidStateTransitionError,
    NoApprovedDirectionRunError,
    NoCurrentDirectionRunError,
)

__all__ = [
    "REVIEW_ROLES",
    "start_review",
    "get_review",
    "unresolved_blocker_count",
    "approve_run",
    "reject_run",
    "request_changes",
    "record_correction",
    "correct_direction_placement",
    "correct_narrative_wording",
    "flag_problem",
    "get_approved_direction_run",
]

REVIEW_ROLES = frozenset({AdminRole.SUPER_ADMIN, AdminRole.ADMIN, AdminRole.CAREER_CONSULTANT})

_ALLOWED_TRANSITIONS: dict[ReviewStatus, frozenset[ReviewStatus]] = {
    ReviewStatus.PENDING_REVIEW: frozenset({ReviewStatus.APPROVED, ReviewStatus.CHANGES_REQUESTED, ReviewStatus.REJECTED}),
    ReviewStatus.APPROVED: frozenset(),
    ReviewStatus.CHANGES_REQUESTED: frozenset(),
    ReviewStatus.REJECTED: frozenset(),
}


def _require_review_role(reviewer: AdminUser) -> None:
    if reviewer.role not in REVIEW_ROLES:
        raise InsufficientRoleError(f"role {reviewer.role.value} may not act on a Direction review")


async def start_review(session: AsyncSession, *, run_id: uuid.UUID) -> DirectionReview:
    """Get-or-create the PENDING_REVIEW row for a run -- idempotent, safe
    to call right after the Critic finishes or lazily on first consultant
    action."""
    existing = (
        await session.execute(select(DirectionReview).where(DirectionReview.run_id == run_id))
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    review = DirectionReview(run_id=run_id, status=ReviewStatus.PENDING_REVIEW)
    session.add(review)
    await session.commit()
    await session.refresh(review)
    emit_event("direction_review_started", run_id=str(run_id), review_id=str(review.id))
    return review


async def get_review(session: AsyncSession, *, run_id: uuid.UUID) -> DirectionReview:
    review = (
        await session.execute(select(DirectionReview).where(DirectionReview.run_id == run_id))
    ).scalar_one_or_none()
    if review is None:
        raise DirectionReviewNotFoundError(f"no DirectionReview exists for run {run_id}")
    return review


async def unresolved_blocker_count(session: AsyncSession, *, run_id: uuid.UUID) -> int:
    result = await session.execute(
        select(DirectionCriticFinding.id).where(
            DirectionCriticFinding.run_id == run_id, DirectionCriticFinding.severity == CriticSeverity.BLOCKER
        )
    )
    return len(result.all())


def _transition(review: DirectionReview, to: ReviewStatus) -> None:
    if to not in _ALLOWED_TRANSITIONS[review.status]:
        raise InvalidStateTransitionError(f"cannot transition DirectionReview from {review.status.value} to {to.value}")
    review.status = to
    review.decided_at = datetime.now(timezone.utc)


async def approve_run(
    session: AsyncSession, *, run_id: uuid.UUID, reviewer: AdminUser, comment: str | None = None
) -> DirectionReview:
    """Approval requires: the run is READY, zero unresolved BLOCKER
    findings, and an authorized reviewer. Re-checks BLOCKER status itself
    (never trusts a caller's earlier check) -- this is the actual approval
    gate's enforcement point, `get_approved_direction_run` only reads its
    result afterward."""
    _require_review_role(reviewer)

    run = await session.get(DirectionRun, run_id)
    if run is None:
        raise NoCurrentDirectionRunError(f"DirectionRun {run_id} does not exist")
    if run.status is not DirectionRunStatus.READY:
        raise InvalidStateTransitionError(f"DirectionRun {run_id} is {run.status.value}, not READY -- cannot approve")

    blocker_count = await unresolved_blocker_count(session, run_id=run_id)
    if blocker_count > 0:
        raise DirectionRunHasUnresolvedBlockerError(
            f"DirectionRun {run_id} has {blocker_count} unresolved BLOCKER finding(s) -- cannot approve"
        )

    review = await start_review(session, run_id=run_id)
    _transition(review, ReviewStatus.APPROVED)
    review.reviewer_id = reviewer.id
    review.comment = comment
    await session.commit()
    await session.refresh(review)
    emit_event(
        "direction_review_approved", run_id=str(run_id), review_id=str(review.id), reviewer_id=str(reviewer.id)
    )
    return review


async def reject_run(session: AsyncSession, *, run_id: uuid.UUID, reviewer: AdminUser, comment: str) -> DirectionReview:
    _require_review_role(reviewer)
    review = await start_review(session, run_id=run_id)
    _transition(review, ReviewStatus.REJECTED)
    review.reviewer_id = reviewer.id
    review.comment = comment
    await session.commit()
    await session.refresh(review)
    emit_event("direction_review_rejected", run_id=str(run_id), review_id=str(review.id), reviewer_id=str(reviewer.id))
    return review


async def request_changes(session: AsyncSession, *, run_id: uuid.UUID, reviewer: AdminUser, comment: str) -> DirectionReview:
    """Never mutates the underlying `DirectionRun` -- regeneration (a new
    `pipeline.generate_directions()` call) is a separate, explicit action
    the caller takes afterward; this function only records the decision."""
    _require_review_role(reviewer)
    review = await start_review(session, run_id=run_id)
    _transition(review, ReviewStatus.CHANGES_REQUESTED)
    review.reviewer_id = reviewer.id
    review.comment = comment
    await session.commit()
    await session.refresh(review)
    emit_event(
        "direction_review_changes_requested", run_id=str(run_id), review_id=str(review.id), reviewer_id=str(reviewer.id)
    )
    return review


async def record_correction(
    session: AsyncSession,
    *,
    run_id: uuid.UUID,
    reviewer: AdminUser,
    artifact_type: str,
    reason_code: CorrectionReasonCode,
    original_value: dict | None,
    corrected_value: dict | None,
    comment: str | None = None,
    direction_id: uuid.UUID | None = None,
    related_claim_ids: list[str] | None = None,
    related_evidence_ids: list[str] | None = None,
    model: str | None = None,
    prompt_version: str | None = None,
) -> ConsultantCorrection:
    """The one append-only write path for every correction/flag kind
    (`correct_direction_placement`/`correct_narrative_wording`/
    `flag_problem` below are thin, ergonomic wrappers over this). Every
    provenance/version field is denormalized from the run at correction
    time (Founder Slice 3 §5) -- never looked up freshly later, since the
    run itself never changes anyway."""
    _require_review_role(reviewer)
    run = await session.get(DirectionRun, run_id)
    if run is None:
        raise NoCurrentDirectionRunError(f"DirectionRun {run_id} does not exist")
    review = await start_review(session, run_id=run_id)

    correction = ConsultantCorrection(
        review_id=review.id, direction_id=direction_id, artifact_type=artifact_type,
        original_value=original_value, corrected_value=corrected_value, reason_code=reason_code, comment=comment,
        reviewer_id=reviewer.id, related_claim_ids=related_claim_ids, related_evidence_ids=related_evidence_ids,
        methodology_version=run.methodology_version, knowledge_base_version_id=run.knowledge_base_version_id,
        scoring_config_version=(await session.get(ScoringConfig, run.scoring_config_id)).version,
        ranking_policy_version=await _ranking_policy_version(session, run),
        direction_engine_version=run.direction_engine_version, model=model, prompt_version=prompt_version,
    )
    session.add(correction)
    await session.commit()
    await session.refresh(correction)
    return correction


async def _ranking_policy_version(session: AsyncSession, run: DirectionRun) -> int:
    from app.db.models_direction import RankingPolicy

    policy = await session.get(RankingPolicy, run.ranking_policy_id)
    return policy.version


async def correct_direction_placement(
    session: AsyncSession,
    *,
    run_id: uuid.UUID,
    direction_id: uuid.UUID,
    reviewer: AdminUser,
    corrected_placement: str,
    reason_code: CorrectionReasonCode,
    comment: str | None = None,
) -> ConsultantCorrection:
    """Records a corrected placement/metadata WITHOUT overwriting the
    original `Direction.placement` column (Founder: "Never overwrite the
    original Direction") -- a later rendering layer applies the
    correction as an overlay on top of the immutable system output."""
    direction = await session.get(Direction, direction_id)
    if direction is None or direction.run_id != run_id:
        raise NoCurrentDirectionRunError(f"Direction {direction_id} does not belong to run {run_id}")
    return await record_correction(
        session, run_id=run_id, reviewer=reviewer, artifact_type="direction_placement", reason_code=reason_code,
        original_value={"placement": direction.placement.value}, corrected_value={"placement": corrected_placement},
        comment=comment, direction_id=direction_id,
    )


async def correct_narrative_wording(
    session: AsyncSession,
    *,
    run_id: uuid.UUID,
    direction_id: uuid.UUID,
    reviewer: AdminUser,
    corrected_text: str,
    field: str = "summary",
    comment: str | None = None,
) -> ConsultantCorrection:
    """A wording-only correction -- MUST NOT and structurally CANNOT
    change any of the four output scores or ranking, since it only ever
    reads/writes narrative text fields via `original_value`/
    `corrected_value`, never a score/placement field."""
    direction = await session.get(Direction, direction_id)
    if direction is None or direction.run_id != run_id:
        raise NoCurrentDirectionRunError(f"Direction {direction_id} does not belong to run {run_id}")
    original_text = (direction.narrative_structured or {}).get(field) if direction.narrative_structured else direction.narrative_text
    return await record_correction(
        session, run_id=run_id, reviewer=reviewer, artifact_type="narrative", reason_code=CorrectionReasonCode.WORDING_ONLY,
        original_value={field: original_text}, corrected_value={field: corrected_text}, comment=comment,
        direction_id=direction_id,
    )


async def flag_problem(
    session: AsyncSession,
    *,
    run_id: uuid.UUID,
    reviewer: AdminUser,
    reason_code: CorrectionReasonCode,
    comment: str,
    artifact_type: str = "profile_flag",
    direction_id: uuid.UUID | None = None,
    related_claim_ids: list[str] | None = None,
) -> ConsultantCorrection:
    """Flags a Profile or Knowledge Base problem the consultant noticed --
    `artifact_type="profile_flag"` or `"knowledge_flag"`. Recorded, not
    auto-applied: engineering/methodology decides what (if anything)
    changes as a result (Founder: never auto-change methodology/prompts/
    scoring config from a consultant correction)."""
    return await record_correction(
        session, run_id=run_id, reviewer=reviewer, artifact_type=artifact_type, reason_code=reason_code,
        original_value=None, corrected_value=None, comment=comment, direction_id=direction_id,
        related_claim_ids=related_claim_ids,
    )


async def get_approved_direction_run(session: AsyncSession, *, user_id: uuid.UUID) -> DirectionRun:
    """The ONLY function a later client-report layer should call to
    decide "is there a publishable Direction Intelligence result for this
    user". Requires, all at once: a current `DirectionRun` that is READY,
    zero unresolved BLOCKER findings, and a `DirectionReview` that is
    APPROVED and bound to that exact run id (never a stale/older run)."""
    run = (
        await session.execute(
            select(DirectionRun).where(DirectionRun.user_id == user_id, DirectionRun.is_current.is_(True))
        )
    ).scalar_one_or_none()
    if run is None or run.status is not DirectionRunStatus.READY:
        raise NoApprovedDirectionRunError(f"user {user_id} has no READY current DirectionRun")

    review = (
        await session.execute(select(DirectionReview).where(DirectionReview.run_id == run.id))
    ).scalar_one_or_none()
    if review is None or review.status is not ReviewStatus.APPROVED:
        raise NoApprovedDirectionRunError(f"DirectionRun {run.id} has no APPROVED review")

    if await unresolved_blocker_count(session, run_id=run.id) > 0:
        raise NoApprovedDirectionRunError(f"DirectionRun {run.id} has unresolved BLOCKER findings despite an APPROVED review")

    return run
