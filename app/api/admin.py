from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.core.security import create_access_token
from app.db.models import AdminUser
from app.db.session import get_session
from app.schemas.admin import (
    DashboardSummary,
    EditLogEntry,
    LoginRequest,
    LoginResponse,
    MessageOut,
    ProfileUpdateRequest,
    StatusUpdateRequest,
    UserDetail,
    UserListItem,
    UserListResponse,
)
from app.schemas.profile import ProfileDraft
from app.services import admin_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/auth/login", response_model=LoginResponse)
async def login(payload: LoginRequest, session: AsyncSession = Depends(get_session)):
    admin = await admin_service.authenticate_admin(session, payload.email, payload.password)
    if admin is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    token = create_access_token(admin.id, admin.role.value)
    return LoginResponse(access_token=token, role=admin.role.value, email=admin.email)


@router.get("/dashboard/summary", response_model=DashboardSummary)
async def dashboard_summary(
    session: AsyncSession = Depends(get_session), _admin: AdminUser = Depends(get_current_admin)
):
    return await admin_service.get_dashboard_summary(session)


@router.get("/users", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=50),
    search: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
    city: str | None = None,
    desired_role: str | None = None,
    registered_after: datetime | None = None,
    registered_before: datetime | None = None,
    active_after: datetime | None = None,
    sort_by: str = Query("created_at", pattern="^(created_at|last_active_at)$"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    session: AsyncSession = Depends(get_session),
    _admin: AdminUser = Depends(get_current_admin),
):
    rows, total = await admin_service.list_users(
        session,
        page=page,
        page_size=page_size,
        search=search,
        status_filter=status_filter,
        city=city,
        desired_role=desired_role,
        registered_after=registered_after,
        registered_before=registered_before,
        active_after=active_after,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    items = [
        UserListItem(
            id=user.id,
            telegram_id=user.telegram_id,
            telegram_username=user.telegram_username,
            name=profile.name if profile else None,
            phone=user.phone,
            city=profile.city if profile else None,
            desired_role=profile.desired_role if profile else None,
            screening_state=user.screening_state.value,
            is_blocked=user.is_blocked,
            profile_completion=admin_service.profile_completion(profile),
            created_at=user.created_at,
            last_active_at=user.last_active_at,
        )
        for user, profile in rows
    ]
    return UserListResponse(items=items, total=total, page=page, page_size=page_size)


async def _load_user_and_profile(session: AsyncSession, user_id: int):
    result = await admin_service.get_user_with_profile(session, user_id)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return result


@router.get("/users/{user_id}", response_model=UserDetail)
async def get_user(
    user_id: int, session: AsyncSession = Depends(get_session), _admin: AdminUser = Depends(get_current_admin)
):
    user, profile = await _load_user_and_profile(session, user_id)
    draft = ProfileDraft(**{f: getattr(profile, f) for f in ProfileDraft.model_fields})
    return UserDetail(
        id=user.id,
        telegram_id=user.telegram_id,
        telegram_username=user.telegram_username,
        phone=user.phone,
        email=user.email,
        screening_state=user.screening_state.value,
        is_blocked=user.is_blocked,
        profile_completion=admin_service.profile_completion(profile),
        created_at=user.created_at,
        last_active_at=user.last_active_at,
        profile=draft,
        profile_confirmed=profile.confirmed,
        profile_updated_at=profile.updated_at,
    )


@router.get("/users/{user_id}/messages", response_model=list[MessageOut])
async def get_user_messages(
    user_id: int, session: AsyncSession = Depends(get_session), _admin: AdminUser = Depends(get_current_admin)
):
    await _load_user_and_profile(session, user_id)
    messages = await admin_service.get_messages(session, user_id)
    return [MessageOut(role=m.role.value, content=m.content, created_at=m.created_at) for m in messages]


@router.get("/users/{user_id}/edit-logs", response_model=list[EditLogEntry])
async def get_user_edit_logs(
    user_id: int, session: AsyncSession = Depends(get_session), _admin: AdminUser = Depends(get_current_admin)
):
    await _load_user_and_profile(session, user_id)
    logs = await admin_service.get_edit_logs(session, user_id)
    return [
        EditLogEntry(
            field_name=log.field_name,
            old_value=log.old_value,
            new_value=log.new_value,
            edited_by=log.edited_by,
            edited_at=log.edited_at,
        )
        for log in logs
    ]


@router.patch("/users/{user_id}/profile", response_model=UserDetail)
async def patch_user_profile(
    user_id: int,
    payload: ProfileUpdateRequest,
    session: AsyncSession = Depends(get_session),
    admin: AdminUser = Depends(get_current_admin),
):
    user, profile = await _load_user_and_profile(session, user_id)
    changes = payload.model_dump(exclude_unset=True)
    await admin_service.update_profile(session, profile, changes, edited_by=admin.email)
    await session.refresh(profile)
    draft = ProfileDraft(**{f: getattr(profile, f) for f in ProfileDraft.model_fields})
    return UserDetail(
        id=user.id,
        telegram_id=user.telegram_id,
        telegram_username=user.telegram_username,
        phone=user.phone,
        email=user.email,
        screening_state=user.screening_state.value,
        is_blocked=user.is_blocked,
        profile_completion=admin_service.profile_completion(profile),
        created_at=user.created_at,
        last_active_at=user.last_active_at,
        profile=draft,
        profile_confirmed=profile.confirmed,
        profile_updated_at=profile.updated_at,
    )


@router.patch("/users/{user_id}/status")
async def patch_user_status(
    user_id: int,
    payload: StatusUpdateRequest,
    session: AsyncSession = Depends(get_session),
    admin: AdminUser = Depends(get_current_admin),
):
    user, _profile = await _load_user_and_profile(session, user_id)

    if payload.is_blocked is not None and admin.role.value != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only ADMIN can block/unblock a user")

    user = await admin_service.update_status(session, user, payload.screening_state, payload.is_blocked)
    return {"id": user.id, "screening_state": user.screening_state.value, "is_blocked": user.is_blocked}
