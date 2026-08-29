"""MNP V1 REST API (`MNP_API_CONTRACTS_V1`). Identity: V1 uses a
lightweight anonymous session bootstrap (`POST /v1/mnp/session` creates
an `IdentityUser`, the client stores the returned `user_id` and sends it
back as `X-Mnp-User-Id` on every call) rather than a full email/password
account system -- no login/registration flow exists yet anywhere in this
codebase to build on, and MNP_PRD_V1 lists "auth/profile" as a
requirement heading without mandating a specific mechanism. A real
persistent account system (so a Career Card survives across devices/
browsers) is a disclosed POST_V1_CANDIDATE, not built here.

Every endpoint that reads a `career_card_id`/`match_run_id`/
`career_match_id` a client supplies verifies it actually belongs to the
resolved `X-Mnp-User-Id` before touching it (MNP_SECURITY_PRIVACY_V1
"least privilege") -- see `_owned_match_run`/`_owned_career_match`
below."""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.db.models import AdminUser
from app.db.models_career_card import (
    CareerGoalType,
    EntryMode,
    MnpCareerCard,
    SourceMode,
    WorkFormat,
    WorkObject,
)
from app.db.models_career_kb_mnp import CareerLifecycleStatus, MnpCareer, MnpCareerFamily
from app.db.models_identity import IdentityUser
from app.db.models_matching_mnp import MnpCareerMatch, MnpMatchRun
from app.db.session import get_session
from app.schemas.mnp import (
    CareerCapitalAnswersIn,
    CareerCreateIn,
    CareerIntentAnswersIn,
    CareerStatusChangeIn,
    MatchRunRequestIn,
)
from app.services.career_card_mnp.card import (
    get_or_create_career_card,
    serialize_career_card,
    snapshot_career_card,
    start_assessment_session,
)
from app.services.career_kb_mnp.careers import create_career, get_or_create_career_family, transition_career_status
from app.services.exceptions import (
    CVFileTooLargeError,
    MnpDuplicateCareerCodeError,
    MnpInvalidLifecycleTransitionError,
)
from app.services.matching_mnp.engine import run_match
from app.services.matching_mnp.queries import get_career_compatibility, get_match_run_results
from app.services.questionnaire_mnp.missing import get_missing_fields
from app.services.questionnaire_mnp.schema import (
    CareerCapitalAnswers,
    CareerIntentAnswers,
    ConstraintAnswer,
    LanguageAnswer,
)
from app.services.questionnaire_mnp.submit import submit_career_capital, submit_career_intent
from app.services.resume_parser_mnp.parser import upload_and_parse_resume

router = APIRouter(prefix="/v1/mnp", tags=["mnp"])

# --- basic single-process upload rate limit (MNP_SECURITY_PRIVACY_V1
# "rate limiting and abuse protection"). Deliberately simple -- an
# in-memory sliding window per user, no new dependency. A multi-process
# deployment needs a shared store (Redis) instead; disclosed limitation.
_UPLOAD_WINDOW_SECONDS = 60.0
_UPLOAD_MAX_PER_WINDOW = 5
_upload_timestamps: dict[str, list[float]] = {}


def _check_upload_rate_limit(user_id: str) -> None:
    now = time.monotonic()
    timestamps = _upload_timestamps.setdefault(user_id, [])
    timestamps[:] = [t for t in timestamps if now - t < _UPLOAD_WINDOW_SECONDS]
    if len(timestamps) >= _UPLOAD_MAX_PER_WINDOW:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many uploads -- please wait a moment and try again")
    timestamps.append(now)


async def get_current_mnp_user(
    x_mnp_user_id: str = Header(...), session: AsyncSession = Depends(get_session),
) -> IdentityUser:
    try:
        user_uuid = uuid.UUID(x_mnp_user_id)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid X-Mnp-User-Id")
    user = await session.get(IdentityUser, user_uuid)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown session -- call POST /v1/mnp/session first")
    return user


async def _get_or_create_owned_card(session: AsyncSession, user: IdentityUser, entry_mode: EntryMode, source_mode: SourceMode) -> MnpCareerCard:
    assessment_session = await start_assessment_session(session, user_id=user.id, entry_mode=entry_mode)
    return await get_or_create_career_card(session, user_id=user.id, assessment_session_id=assessment_session.id, source_mode=source_mode)


async def _owned_card_or_404(session: AsyncSession, user: IdentityUser) -> MnpCareerCard:
    result = await session.execute(select(MnpCareerCard).where(MnpCareerCard.user_id == user.id))
    card = result.scalar_one_or_none()
    if card is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No Career Card yet -- upload a CV or submit the questionnaire first")
    return card


async def _owned_match_run(session: AsyncSession, match_run_id: uuid.UUID, user: IdentityUser) -> MnpMatchRun:
    match_run = await session.get(MnpMatchRun, match_run_id)
    if match_run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Match run not found")
    card = await session.get(MnpCareerCard, match_run.career_card_id)
    if card is None or card.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your match run")
    return match_run


async def _owned_career_match(session: AsyncSession, career_match_id: uuid.UUID, user: IdentityUser) -> MnpCareerMatch:
    match = await session.get(MnpCareerMatch, career_match_id)
    if match is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Career match not found")
    await _owned_match_run(session, match.match_run_id, user)
    return match


@router.post("/session")
async def create_session(session: AsyncSession = Depends(get_session)):
    user = IdentityUser(locale="uk")
    session.add(user)
    await session.commit()
    return {"user_id": str(user.id)}


@router.post("/documents")
async def upload_document(
    file: UploadFile = File(...), user: IdentityUser = Depends(get_current_mnp_user), session: AsyncSession = Depends(get_session),
):
    _check_upload_rate_limit(str(user.id))
    content = await file.read()
    try:
        card, document = await upload_and_parse_resume(session, user_id=user.id, filename=file.filename or "resume", content_bytes=content)
    except CVFileTooLargeError as exc:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, str(exc))
    return {
        "document_id": str(document.id), "career_card_id": str(card.id),
        "extraction_status": document.text_extraction_status.value,
    }


@router.get("/career-card")
async def get_career_card(user: IdentityUser = Depends(get_current_mnp_user), session: AsyncSession = Depends(get_session)):
    card = await _owned_card_or_404(session, user)
    return await serialize_career_card(session, card)


@router.get("/questionnaire/missing")
async def questionnaire_missing(user: IdentityUser = Depends(get_current_mnp_user), session: AsyncSession = Depends(get_session)):
    card = await _owned_card_or_404(session, user)
    missing = await get_missing_fields(session, card.id)
    return asdict(missing)


@router.post("/questionnaire/career-capital")
async def submit_capital(payload: CareerCapitalAnswersIn, user: IdentityUser = Depends(get_current_mnp_user), session: AsyncSession = Depends(get_session)):
    card = await _get_or_create_owned_card(session, user, EntryMode.MANUAL, SourceMode.MANUAL)
    answers = CareerCapitalAnswers(
        current_role=payload.current_role, years_of_experience=payload.years_of_experience,
        responsibilities=payload.responsibilities, skill_phrases=payload.skill_phrases,
        education_level=payload.education_level, education_field=payload.education_field,
        education_institution=payload.education_institution, graduation_year=payload.graduation_year,
        credential_names=payload.credential_names,
        languages=[LanguageAnswer(l.language_code, l.overall_level) for l in payload.languages],
    )
    await submit_career_capital(session, card, answers)
    await session.commit()
    return {"career_card_id": str(card.id)}


@router.post("/questionnaire/career-intent")
async def submit_intent(payload: CareerIntentAnswersIn, user: IdentityUser = Depends(get_current_mnp_user), session: AsyncSession = Depends(get_session)):
    card = await _get_or_create_owned_card(session, user, EntryMode.MANUAL, SourceMode.MANUAL)
    answers = CareerIntentAnswers(
        goal_type=CareerGoalType(payload.goal_type) if payload.goal_type else None,
        location_region=payload.location_region,
        work_format=WorkFormat(payload.work_format) if payload.work_format else None,
        current_income=payload.current_income, target_income=payload.target_income, income_currency=payload.income_currency,
        time_horizon=payload.time_horizon, willingness_change_career=payload.willingness_change_career,
        preferred_work_object=WorkObject(payload.preferred_work_object) if payload.preferred_work_object else None,
        autonomy_preference=payload.autonomy_preference, teamwork_preference=payload.teamwork_preference,
        customer_interaction_preference=payload.customer_interaction_preference,
        routine_vs_novelty_preference=payload.routine_vs_novelty_preference,
        leadership_preference=payload.leadership_preference, physical_activity_preference=payload.physical_activity_preference,
        top_work_value_keys=payload.top_work_value_keys, learning_hours_per_week=payload.learning_hours_per_week,
        learning_budget=payload.learning_budget, willing_new_credential=payload.willing_new_credential,
        willing_lower_entry_role=payload.willing_lower_entry_role, excluded_career_codes=payload.excluded_career_codes,
        constraints=[ConstraintAnswer(c.constraint_type, c.value, c.severity) for c in payload.constraints],
    )
    await submit_career_intent(session, card, answers)
    await session.commit()
    return {"career_card_id": str(card.id)}


@router.post("/match-runs")
async def create_match_run(payload: MatchRunRequestIn, user: IdentityUser = Depends(get_current_mnp_user), session: AsyncSession = Depends(get_session)):
    card = await _owned_card_or_404(session, user)
    await snapshot_career_card(session, card)  # pin the exact state this run is reproducible against
    match_run = await run_match(session, career_card_id=card.id, ranking_mode=payload.ranking_mode)
    await session.commit()
    return {"match_run_id": str(match_run.id)}


@router.get("/match-runs/{match_run_id}/careers")
async def get_match_run_careers(match_run_id: uuid.UUID, user: IdentityUser = Depends(get_current_mnp_user), session: AsyncSession = Depends(get_session)):
    await _owned_match_run(session, match_run_id, user)
    results = await get_match_run_results(session, match_run_id)
    return {
        "featured": [asdict(c) for c in results.featured],
        "ranked_top10": [asdict(c) for c in results.ranked_top10],
        "blocked": [asdict(c) for c in results.blocked],
    }


@router.get("/career-matches/{career_match_id}")
async def get_career_match_detail(career_match_id: uuid.UUID, user: IdentityUser = Depends(get_current_mnp_user), session: AsyncSession = Depends(get_session)):
    await _owned_career_match(session, career_match_id, user)
    view = await get_career_compatibility(session, career_match_id)
    return asdict(view)


@router.get("/career-matches/{career_match_id}/route")
async def get_career_match_route(career_match_id: uuid.UUID, user: IdentityUser = Depends(get_current_mnp_user), session: AsyncSession = Depends(get_session)):
    await _owned_career_match(session, career_match_id, user)
    view = await get_career_compatibility(session, career_match_id)
    return {"route_type": view.route_type, "steps": [asdict(s) for s in view.route_steps]}


@router.get("/careers")
async def list_careers(session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(select(MnpCareer).where(MnpCareer.status == CareerLifecycleStatus.ACTIVE))).scalars().all()
    return [
        {"id": str(c.id), "code": c.code, "name_uk": c.canonical_name_uk, "description_short_uk": c.description_short_uk}
        for c in rows
    ]


@router.get("/careers/{career_id}")
async def get_career_detail(career_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    career = await session.get(MnpCareer, career_id)
    if career is None or career.status == CareerLifecycleStatus.ARCHIVED:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Career not found")
    return {
        "id": str(career.id), "code": career.code, "name_uk": career.canonical_name_uk,
        "name_en": career.canonical_name_en, "description_short_uk": career.description_short_uk,
        "status": career.status.value, "market_data_limited": career.market_data_limited,
    }


# ---------------------------------------------------------------------------
# Admin Career KB (reuses Stage 1's admin JWT auth)

@router.post("/admin/careers", status_code=status.HTTP_201_CREATED)
async def admin_create_career(
    payload: CareerCreateIn, admin: AdminUser = Depends(get_current_admin), session: AsyncSession = Depends(get_session),
):
    family = await get_or_create_career_family(
        session, code=payload.career_family_code, name_uk=payload.career_family_name_uk, name_en=payload.career_family_name_en,
    )
    try:
        career = await create_career(
            session, code=payload.code, canonical_name_uk=payload.canonical_name_uk, canonical_name_en=payload.canonical_name_en,
            description_short_uk=payload.description_short_uk, career_family=family, actor_admin_id=admin.id,
        )
    except MnpDuplicateCareerCodeError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))
    await session.commit()
    return {"id": str(career.id), "code": career.code, "status": career.status.value}


@router.patch("/admin/careers/{career_id}/status")
async def admin_change_career_status(
    career_id: uuid.UUID, payload: CareerStatusChangeIn, admin: AdminUser = Depends(get_current_admin), session: AsyncSession = Depends(get_session),
):
    career = await session.get(MnpCareer, career_id)
    if career is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Career not found")
    try:
        updated = await transition_career_status(
            session, career, to_status=CareerLifecycleStatus(payload.to_status), actor_admin_id=admin.id, reason=payload.reason,
        )
    except MnpInvalidLifecycleTransitionError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    await session.commit()
    return {"id": str(updated.id), "status": updated.status.value}
