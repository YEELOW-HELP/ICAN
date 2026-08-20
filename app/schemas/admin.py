from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.schemas.profile import ProfileDraft


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    email: str


class UserListItem(BaseModel):
    id: int
    telegram_id: int
    telegram_username: str | None
    name: str | None
    phone: str | None
    city: str | None
    desired_role: str | None
    screening_state: str
    is_blocked: bool
    profile_completion: int
    created_at: datetime
    last_active_at: datetime | None


class UserListResponse(BaseModel):
    items: list[UserListItem]
    total: int
    page: int
    page_size: int


class UserDetail(BaseModel):
    id: int
    telegram_id: int
    telegram_username: str | None
    phone: str | None
    email: str | None
    screening_state: str
    is_blocked: bool
    profile_completion: int
    created_at: datetime
    last_active_at: datetime | None
    profile: ProfileDraft
    profile_confirmed: bool
    profile_updated_at: datetime


class MessageOut(BaseModel):
    role: str
    content: str
    created_at: datetime


class ProfileUpdateRequest(BaseModel):
    """All fields optional — only the ones present in the request body are
    changed. Comes from ProfileDraft's field set so it can never drift from
    the columns the screening agent itself is allowed to fill."""

    name: str | None = None
    country: str | None = None
    city: str | None = None
    status: str | None = None
    education: str | None = None
    total_experience: str | None = None
    previous_positions: list[str] | None = None
    skills: list[str] | None = None
    languages: list[str] | None = None
    desired_role: str | None = None
    desired_min_income: str | None = None
    desired_currency: str | None = None
    employment_format: str | None = None
    work_format: str | None = None
    schedule: str | None = None
    constraints: str | None = None
    other_notes: str | None = None


class StatusUpdateRequest(BaseModel):
    screening_state: str | None = None
    is_blocked: bool | None = None


class DashboardSummary(BaseModel):
    total_users: int
    new_today: int
    completed: int
    in_progress: int
    not_completed: int
    active_last_7_days: int


class EditLogEntry(BaseModel):
    field_name: str
    old_value: str | None
    new_value: str | None
    edited_by: str
    edited_at: datetime
