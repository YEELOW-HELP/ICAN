from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class MeResponse(BaseModel):
    id: int
    email: str
    full_name: str | None
    role: str


# ---- Client list / detail ----

class ClientListItem(BaseModel):
    id: int
    first_name: str | None
    last_name: str | None
    phone: str | None
    city: str | None
    primary_target: str | None
    status: str
    priority: str
    profile_completion: int
    manager_id: int | None
    manager_name: str | None
    consultant_id: int | None
    consultant_name: str | None
    last_activity_at: datetime | None
    created_at: datetime
    next_action_type: str | None
    next_action_due_at: datetime | None


class ClientListResponse(BaseModel):
    items: list[ClientListItem]
    total: int
    page: int
    page_size: int


class ClientCreateRequest(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    email: str | None = None
    country: str | None = None
    city: str | None = None
    source_channel: str = "manager"


class ClientUpdateRequest(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    telegram_username: str | None = None
    email: str | None = None
    birth_date: str | None = None
    country: str | None = None
    city: str | None = None
    priority: str | None = None


class ClientProfileOut(BaseModel):
    currently_employed: bool | None = None
    current_position: str | None = None
    current_fields: list[str] | None = None
    current_income: str | None = None
    current_income_currency: str | None = None
    search_reasons: list[str] | None = None
    readiness_to_start: str | None = None
    readiness_date: str | None = None
    urgency: str | None = None
    nonstandard_info: str | None = None
    consultation_consent: bool | None = None
    education_level: str | None = None
    specialty: str | None = None
    institution: str | None = None
    graduation_year: int | None = None
    courses: list[str] | None = None
    driver_licenses: list[str] | None = None
    other_qualification: str | None = None
    primary_target: str | None = None
    alternative_targets: list[str] | None = None
    interesting_fields: list[str] | None = None
    avoid_fields: list[str] | None = None
    open_to_career_change: str | None = None
    min_salary: str | None = None
    desired_salary: str | None = None
    salary_currency: str | None = None
    employment_types: list[str] | None = None
    work_formats: list[str] | None = None
    schedules: list[str] | None = None
    work_cities: list[str] | None = None
    commute_limit: str | None = None
    relocation_ready: str | None = None
    relocation_cities: list[str] | None = None
    business_trips_ok: str | None = None
    start_date: str | None = None
    constraints: list[str] | None = None
    critical_constraint: bool = False
    constraints_comment: str | None = None


class ClientProfileUpdateRequest(ClientProfileOut):
    critical_constraint: bool | None = None


class WorkExperienceOut(BaseModel):
    id: int
    company: str | None
    position: str | None
    fields: list[str] | None
    start_month_year: str | None
    end_month_year: str | None
    responsibilities: str | None
    achievements: str | None
    tools: list[str] | None


class WorkExperienceRequest(BaseModel):
    company: str | None = None
    position: str | None = None
    fields: list[str] | None = None
    start_month_year: str | None = None
    end_month_year: str | None = None
    responsibilities: str | None = None
    achievements: str | None = None
    tools: list[str] | None = None


class SkillOut(BaseModel):
    id: int
    skill_name: str
    level: str | None
    years_experience: int | None
    verified: bool


class SkillRequest(BaseModel):
    skill_name: str
    level: str | None = None
    years_experience: int | None = None
    verified: bool = False


class LanguageOut(BaseModel):
    id: int
    language: str
    level: str | None
    can_work_in_it: str | None


class LanguageRequest(BaseModel):
    language: str
    level: str | None = None
    can_work_in_it: str | None = None


class ClientDetail(BaseModel):
    id: int
    first_name: str | None
    last_name: str | None
    phone: str | None
    telegram_username: str | None
    email: str | None
    birth_date: str | None
    country: str | None
    city: str | None
    source_channel: str
    status: str
    priority: str
    manager_id: int | None
    manager_name: str | None
    consultant_id: int | None
    consultant_name: str | None
    profile_completion: int
    created_at: datetime
    last_activity_at: datetime | None
    profile: ClientProfileOut
    work_experiences: list[WorkExperienceOut]
    skills: list[SkillOut]
    languages: list[LanguageOut]


class AssignRequest(BaseModel):
    staff_id: int


class StatusUpdateRequest(BaseModel):
    status: str


class ReadinessResponse(BaseModel):
    ready: bool
    missing: list[str]
    status: str


class ConsultationOut(BaseModel):
    primary_target: str | None
    alternative_targets: list[str] | None
    strengths: list[str] | None
    skills_gaps: list[str] | None
    search_strategy: str | None
    expectations_realistic: str | None
    expectations_comment: str | None
    conclusion: str | None
    completed_at: datetime | None


class ConsultationDraftRequest(BaseModel):
    primary_target: str | None = None
    alternative_targets: list[str] | None = None
    strengths: list[str] | None = None
    skills_gaps: list[str] | None = None
    search_strategy: str | None = None
    expectations_realistic: str | None = None
    expectations_comment: str | None = None


class ConsultationCompleteRequest(BaseModel):
    conclusion: str


class CallOut(BaseModel):
    id: int
    direction: str
    status: str
    duration_seconds: int | None
    employee_id: int | None
    employee_name: str | None
    contact_type: str | None
    note: str | None
    recording_url: str | None
    started_at: datetime


class CallCreateRequest(BaseModel):
    direction: str
    status: str
    duration_seconds: int | None = None
    contact_type: str | None = None
    note: str | None = None


class TaskOut(BaseModel):
    id: int
    task_type: str
    other_description: str | None
    assignee_id: int | None
    assignee_name: str | None
    due_at: datetime | None
    status: str
    note: str | None
    created_at: datetime
    completed_at: datetime | None


class TaskCreateRequest(BaseModel):
    task_type: str
    other_description: str | None = None
    assignee_id: int | None = None
    due_at: datetime | None = None
    note: str | None = None


class TimelineEventOut(BaseModel):
    id: int
    event_type: str
    description: str
    actor_id: int | None
    actor_name: str | None
    before_value: str | None
    after_value: str | None
    created_at: datetime


class FileOut(BaseModel):
    id: int
    file_type: str
    other_description: str | None
    filename: str
    content_type: str | None
    size_bytes: int | None
    is_current_cv: bool
    uploaded_by_id: int | None
    uploaded_by_name: str | None
    uploaded_at: datetime


class DashboardSummaryOut(BaseModel):
    total_clients: int
    new_today: int
    in_screening: int
    waiting_consultant: int
    in_career_consultation: int
    ready_for_matching: int


class StaffOut(BaseModel):
    id: int
    full_name: str | None
    email: str
    role: str
    is_active: bool
    created_at: datetime


class StaffCreateRequest(BaseModel):
    full_name: str | None = None
    email: str
    password: str
    role: str


class StaffUpdateRequest(BaseModel):
    full_name: str | None = None
    role: str | None = None
    is_active: bool | None = None
    password: str | None = None
