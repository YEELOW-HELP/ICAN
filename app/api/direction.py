"""Stage 4A: the MNP consultant workspace API (Issue #3).

Thin handlers only -- every endpoint here calls an existing Stage 3B/3.5
service function and returns its result (or a small derived summary).
No Direction Intelligence business logic is duplicated here, and no route
queries the Career Knowledge Base or scoring/ranking tables directly --
`app/services/direction/*` remains the single source of truth.

RBAC: every route requires an authenticated admin
(`app.api.deps.get_current_admin`, the same dependency `crm.py` uses).
Consultant actions (corrections/approve/reject/request-changes) rely on
`review.py`'s own `REVIEW_ROLES` check
(`{SUPER_ADMIN, ADMIN, CAREER_CONSULTANT}`) -- this module never
re-implements or second-guesses that RBAC decision, it only translates
the `InsufficientRoleError` the service layer already raises into a 403.

Known limitation: the client list has no per-consultant visibility
scoping (unlike CRM's `Client.consultant_id`) -- there is no "assigned
consultant" field anywhere in the `IdentityUser`/`DirectionRun` domain
model yet (Founder Stage 4A brief explicitly allows this: "assigned
consultant if already available in current domain model"). Every
authenticated admin role sees every client for now.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.db.models import AdminUser
from app.db.models_direction import CorrectionReasonCode
from app.db.session import get_session
from app.schemas.direction import CreateCorrectionRequest, GenerateDirectionsRequest, ReviewDecisionRequest, ReviewDecisionWithReasonRequest
from app.services.direction import critic as critic_service
from app.services.direction import readmodel
from app.services.direction import review as review_service
from app.services.direction.narrative import DirectionNarrator, generate_narratives_for_run
from app.services.direction.pipeline import generate_directions
from app.services.exceptions import (
    DirectionGenerationInProgressError,
    DirectionReviewNotFoundError,
    DirectionRunHasUnresolvedBlockerError,
    DomainError,
    InsufficientRoleError,
    InvalidStateTransitionError,
    NoActiveRankingPolicyError,
    NoActiveScoringConfigError,
    NoApprovedDirectionRunError,
    NoCurrentDirectionRunError,
    NoCurrentProfileError,
    NoEligibleAssessmentSessionError,
    ProfileAlreadyExistsError,
    ProfileGenerationInProgressError,
)
from app.services.profile.generation import generate_profile_for_user, get_profile_status_summary

router = APIRouter(prefix="/direction", tags=["direction"])

_NOT_FOUND_ERRORS = (
    NoCurrentDirectionRunError, NoCurrentProfileError, DirectionReviewNotFoundError, NoEligibleAssessmentSessionError,
)
_CONFLICT_ERRORS = (
    DirectionRunHasUnresolvedBlockerError, InvalidStateTransitionError, DirectionGenerationInProgressError,
    NoActiveScoringConfigError, NoActiveRankingPolicyError, ProfileAlreadyExistsError, ProfileGenerationInProgressError,
)


def _raise_mapped(exc: DomainError) -> None:
    if isinstance(exc, InsufficientRoleError):
        raise HTTPException(status.HTTP_403_FORBIDDEN, exc.message) from exc
    if isinstance(exc, _NOT_FOUND_ERRORS):
        raise HTTPException(status.HTTP_404_NOT_FOUND, exc.message) from exc
    if isinstance(exc, _CONFLICT_ERRORS):
        raise HTTPException(status.HTTP_409_CONFLICT, exc.message) from exc
    raise HTTPException(status.HTTP_400_BAD_REQUEST, exc.message) from exc


def _uuid(value: str, field: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Invalid {field}: {value!r}")


@router.get("/clients")
async def list_clients(
    filter: str | None = Query(default=None),
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    return await readmodel.list_client_summaries(session, filter_name=filter)


@router.get("/clients/{user_id}/card")
async def get_client_card(
    user_id: str, admin: AdminUser = Depends(get_current_admin), session: AsyncSession = Depends(get_session)
):
    try:
        return await readmodel.build_client_card(session, user_id=_uuid(user_id, "user_id"))
    except DomainError as exc:
        _raise_mapped(exc)


@router.get("/clients/{user_id}/profile-status")
async def get_profile_status(
    user_id: str, admin: AdminUser = Depends(get_current_admin), session: AsyncSession = Depends(get_session)
):
    """Dashboard NO_PROFILE / PROCESSING / READY / FAILED state (Founder
    Stage 4A.5 §3) -- unlike `get_client_card`, never requires a
    DirectionRun to exist yet."""
    summary = await get_profile_status_summary(session, user_id=_uuid(user_id, "user_id"))
    return {
        "status": summary.status, "profile_id": str(summary.profile_id) if summary.profile_id else None,
        "version": summary.version, "failure_reason": summary.failure_reason,
    }


@router.post("/clients/{user_id}/profile", status_code=status.HTTP_201_CREATED)
async def generate_client_profile(
    user_id: str, admin: AdminUser = Depends(get_current_admin), session: AsyncSession = Depends(get_session)
):
    """Admin fallback (Founder Stage 4A.5 §3): "Generate / Regenerate
    Potential Profile -- only if it does not already exist." Calls the
    existing Stage 2 service unchanged
    (app/services/profile/generation.py::generate_profile_for_user) --
    no profile-generation logic is duplicated here."""
    try:
        profile = await generate_profile_for_user(session, user_id=_uuid(user_id, "user_id"))
    except DomainError as exc:
        _raise_mapped(exc)
    return {"profile_id": str(profile.id), "status": profile.status.value, "version": profile.version}


@router.post("/clients/{user_id}/full-pipeline")
async def run_full_pipeline(
    user_id: str, admin: AdminUser = Depends(get_current_admin), session: AsyncSession = Depends(get_session)
):
    """Founder Stage 4A.5 §4: "Generate full MNP result" -- ensure READY
    profile -> generate_directions -> run_critic -> optionally generate
    narrative. Every step calls its own existing, unchanged service
    function; this only sequences them and reports each step's outcome
    without hiding any individual lifecycle state. If profile generation
    fails, stops there. If Direction generation fails, the profile is
    never touched (generate_directions has no write path to
    PotentialProfile at all). If narrative fails, the deterministic
    Direction result (already returned in `steps`) remains valid --
    narrative failure is isolated and never re-raised."""
    uid = _uuid(user_id, "user_id")
    steps: dict = {}

    profile_status = await get_profile_status_summary(session, user_id=uid)
    if profile_status.status == "ready":
        steps["profile"] = {"status": "ready", "profile_id": str(profile_status.profile_id)}
    else:
        try:
            profile = await generate_profile_for_user(session, user_id=uid)
            steps["profile"] = {"status": profile.status.value, "profile_id": str(profile.id)}
        except ProfileAlreadyExistsError:
            steps["profile"] = {"status": "ready"}  # became ready concurrently -- proceed
        except DomainError as exc:
            steps["profile"] = {"status": "failed", "error": exc.code}
            return {"steps": steps}
        if steps["profile"]["status"] != "ready":
            return {"steps": steps}

    try:
        run = await generate_directions(session, user_id=uid)
        steps["direction_run"] = {"status": run.status.value, "run_id": str(run.id), "version": run.version}
    except DomainError as exc:
        steps["direction_run"] = {"status": "failed", "error": exc.code}
        return {"steps": steps}

    if run.status.value != "ready":
        return {"steps": steps}

    try:
        findings = await critic_service.run_critic(session, run_id=run.id)
        steps["critic"] = {
            "blocker_count": sum(1 for f in findings if f.severity.value == "blocker"),
            "warning_count": sum(1 for f in findings if f.severity.value == "warning"),
        }
    except DomainError as exc:
        steps["critic"] = {"status": "failed", "error": exc.code}
        return {"steps": steps}

    try:
        narrated = await generate_narratives_for_run(session, run_id=run.id, narrator=DirectionNarrator())
        steps["narrative"] = {"narrated_count": narrated}
    except Exception as exc:
        steps["narrative"] = {"status": "failed", "error": type(exc).__name__}

    return {"steps": steps}


@router.post("/clients/{user_id}/generate", status_code=status.HTTP_201_CREATED)
async def generate_client_directions(
    user_id: str,
    payload: GenerateDirectionsRequest = GenerateDirectionsRequest(),
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    kb_version_id = _uuid(payload.knowledge_base_version_id, "knowledge_base_version_id") if payload.knowledge_base_version_id else None
    try:
        run = await generate_directions(session, user_id=_uuid(user_id, "user_id"), knowledge_base_version_id=kb_version_id)
    except DomainError as exc:
        _raise_mapped(exc)
    return {"run_id": str(run.id), "status": run.status.value, "version": run.version}


@router.post("/runs/{run_id}/critic")
async def run_critic_endpoint(
    run_id: str, admin: AdminUser = Depends(get_current_admin), session: AsyncSession = Depends(get_session)
):
    try:
        findings = await critic_service.run_critic(session, run_id=_uuid(run_id, "run_id"))
    except DomainError as exc:
        _raise_mapped(exc)
    blocker_count = sum(1 for f in findings if f.severity.value == "blocker")
    warning_count = sum(1 for f in findings if f.severity.value == "warning")
    return {"total_findings": len(findings), "blocker_count": blocker_count, "warning_count": warning_count}


@router.post("/runs/{run_id}/narrative")
async def generate_narrative_endpoint(
    run_id: str, admin: AdminUser = Depends(get_current_admin), session: AsyncSession = Depends(get_session)
):
    try:
        narrated = await generate_narratives_for_run(session, run_id=_uuid(run_id, "run_id"), narrator=DirectionNarrator())
    except DomainError as exc:
        _raise_mapped(exc)
    return {"narrated_count": narrated}


@router.post("/runs/{run_id}/corrections", status_code=status.HTTP_201_CREATED)
async def create_correction(
    run_id: str,
    payload: CreateCorrectionRequest,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    run_uuid = _uuid(run_id, "run_id")
    try:
        reason_code = CorrectionReasonCode(payload.reason_code)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown reason_code: {payload.reason_code!r}")

    direction_uuid = _uuid(payload.direction_id, "direction_id") if payload.direction_id else None

    try:
        if payload.artifact_type == "direction_placement":
            if not direction_uuid or not payload.corrected_placement:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "direction_id and corrected_placement are required")
            correction = await review_service.correct_direction_placement(
                session, run_id=run_uuid, direction_id=direction_uuid, reviewer=admin,
                corrected_placement=payload.corrected_placement, reason_code=reason_code, comment=payload.comment,
            )
        elif payload.artifact_type == "narrative":
            if not direction_uuid or not payload.corrected_text:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "direction_id and corrected_text are required")
            correction = await review_service.correct_narrative_wording(
                session, run_id=run_uuid, direction_id=direction_uuid, reviewer=admin,
                corrected_text=payload.corrected_text, field=payload.narrative_field, comment=payload.comment,
            )
        elif payload.artifact_type in ("profile_flag", "knowledge_flag"):
            if not payload.comment:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "comment is required for a flag")
            correction = await review_service.flag_problem(
                session, run_id=run_uuid, reviewer=admin, reason_code=reason_code, comment=payload.comment,
                artifact_type=payload.artifact_type, direction_id=direction_uuid,
            )
        else:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Unsupported artifact_type: {payload.artifact_type!r} (frontend-only correction types are not allowed)",
            )
    except DomainError as exc:
        _raise_mapped(exc)

    return {
        "correction_id": str(correction.id), "artifact_type": correction.artifact_type,
        "reason_code": correction.reason_code.value,
    }


@router.post("/runs/{run_id}/approve")
async def approve_run_endpoint(
    run_id: str,
    payload: ReviewDecisionRequest = ReviewDecisionRequest(),
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    try:
        review = await review_service.approve_run(session, run_id=_uuid(run_id, "run_id"), reviewer=admin, comment=payload.comment)
    except DomainError as exc:
        _raise_mapped(exc)
    return {"review_id": str(review.id), "status": review.status.value}


@router.post("/runs/{run_id}/request-changes")
async def request_changes_endpoint(
    run_id: str,
    payload: ReviewDecisionWithReasonRequest,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    try:
        review = await review_service.request_changes(session, run_id=_uuid(run_id, "run_id"), reviewer=admin, comment=payload.comment)
    except DomainError as exc:
        _raise_mapped(exc)
    return {"review_id": str(review.id), "status": review.status.value}


@router.post("/runs/{run_id}/reject")
async def reject_run_endpoint(
    run_id: str,
    payload: ReviewDecisionWithReasonRequest,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    try:
        review = await review_service.reject_run(session, run_id=_uuid(run_id, "run_id"), reviewer=admin, comment=payload.comment)
    except DomainError as exc:
        _raise_mapped(exc)
    return {"review_id": str(review.id), "status": review.status.value}


@router.get("/clients/{user_id}/publishable")
async def get_publishable_preview(
    user_id: str, admin: AdminUser = Depends(get_current_admin), session: AsyncSession = Depends(get_session)
):
    """Never a 404/500 for "not approved yet" -- that is an expected,
    routine state for this screen, not an error. Returns
    `{"publishable": false, "reason": "..."}` instead, per Founder Stage
    4A §12 ("show NOT PUBLISHABLE YET with reason")."""
    try:
        result = await readmodel.get_publishable_direction_result(session, user_id=_uuid(user_id, "user_id"))
    except NoApprovedDirectionRunError as exc:
        return {"publishable": False, "reason": exc.message, "result": None}
    return {"publishable": True, "reason": None, "result": result}
