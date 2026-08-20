from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.core.config import settings
from app.core.security import hash_password
from app.db.models import AdminRole, AdminUser
from app.db.models_crm import (
    Client,
    ClientLanguage,
    ClientProfile,
    ClientSkill,
    ClientStatus,
    SourceChannel,
    Task,
    TaskStatus,
    WorkExperience,
)
from app.db.session import get_session
from app.schemas.crm import (
    AssignRequest,
    CallCreateRequest,
    CallOut,
    ClientCreateRequest,
    ClientDetail,
    ClientListItem,
    ClientListResponse,
    ClientProfileOut,
    ClientProfileUpdateRequest,
    ClientUpdateRequest,
    ConsultationCompleteRequest,
    ConsultationDraftRequest,
    ConsultationOut,
    DashboardSummaryOut,
    FileOut,
    LanguageOut,
    LanguageRequest,
    MeResponse,
    ReadinessResponse,
    SkillOut,
    SkillRequest,
    StaffCreateRequest,
    StaffOut,
    StaffUpdateRequest,
    StatusUpdateRequest,
    TaskCreateRequest,
    TaskOut,
    TimelineEventOut,
    WorkExperienceOut,
    WorkExperienceRequest,
)
from app.services.crm import calls as call_service
from app.services.crm import clients as client_service
from app.services.crm import consultation as consultation_service
from app.services.crm import files as file_service
from app.services.crm import profile_blocks
from app.services.crm import tasks as task_service
from app.services.crm import timeline as timeline_service
from app.services.crm.completeness import profile_completion
from app.services.crm.storage import get_storage

router = APIRouter(prefix="/crm", tags=["crm"])


# ---------------- RBAC helpers ----------------

def _require_roles(admin: AdminUser, *roles: AdminRole) -> None:
    if admin.role not in roles:
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"This action requires one of: {[r.value for r in roles]}")


def _ensure_visible(client: Client, viewer: AdminUser) -> None:
    """Mirrors the list-level RBAC scoping for single-client endpoints —
    ТЗ §20 requires this enforced by the backend, not just hidden in the UI."""
    if viewer.role == AdminRole.CAREER_CONSULTANT and client.consultant_id != viewer.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Client not found")


async def _get_client_or_404(session: AsyncSession, client_id: int, viewer: AdminUser) -> Client:
    client = await client_service.get_client(session, client_id)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Client not found")
    _ensure_visible(client, viewer)
    return client


async def _staff_names(session: AsyncSession, ids: set[int | None]) -> dict[int, str]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    result = await session.execute(select(AdminUser).where(AdminUser.id.in_(ids)))
    return {a.id: (a.full_name or a.email) for a in result.scalars().all()}


def _profile_out(profile: ClientProfile | None) -> ClientProfileOut:
    if profile is None:
        return ClientProfileOut()
    return ClientProfileOut(**{f: getattr(profile, f) for f in ClientProfileOut.model_fields})


# ---------------- Me ----------------

@router.get("/me", response_model=MeResponse)
async def me(admin: AdminUser = Depends(get_current_admin)):
    return MeResponse(id=admin.id, email=admin.email, full_name=admin.full_name, role=admin.role.value)


# ---------------- Dashboard ----------------

@router.get("/dashboard", response_model=DashboardSummaryOut)
async def dashboard(session: AsyncSession = Depends(get_session), admin: AdminUser = Depends(get_current_admin)):
    return await client_service.dashboard_summary(session, admin)


# ---------------- Clients: list / create ----------------

@router.get("/clients", response_model=ClientListResponse)
async def list_clients(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    search: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
    city: str | None = None,
    manager_id: int | None = None,
    consultant_id: int | None = None,
    sort_by: str = Query("created_at", pattern="^(created_at|last_activity_at)$"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    session: AsyncSession = Depends(get_session),
    admin: AdminUser = Depends(get_current_admin),
):
    rows, total = await client_service.list_clients(
        session,
        viewer=admin,
        page=page,
        page_size=page_size,
        search=search,
        status_filter=status_filter,
        city=city,
        manager_id=manager_id,
        consultant_id=consultant_id,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    names = await _staff_names(session, {c.manager_id for c in rows} | {c.consultant_id for c in rows})

    next_actions: dict[int, Task] = {}
    if rows:
        result = await session.execute(
            select(Task)
            .where(Task.client_id.in_([c.id for c in rows]), Task.status == TaskStatus.PENDING)
            .order_by(Task.due_at)
        )
        for t in result.scalars().all():
            next_actions.setdefault(t.client_id, t)

    items = [
        ClientListItem(
            id=c.id,
            first_name=c.first_name,
            last_name=c.last_name,
            phone=c.phone,
            city=c.city,
            primary_target=c.profile.primary_target if c.profile else None,
            status=c.status.value,
            priority=c.priority.value,
            profile_completion=profile_completion(c, c.profile, c.work_experiences, c.skills, c.languages),
            manager_id=c.manager_id,
            manager_name=names.get(c.manager_id),
            consultant_id=c.consultant_id,
            consultant_name=names.get(c.consultant_id),
            last_activity_at=c.last_activity_at,
            created_at=c.created_at,
            next_action_type=next_actions[c.id].task_type if c.id in next_actions else None,
            next_action_due_at=next_actions[c.id].due_at if c.id in next_actions else None,
        )
        for c in rows
    ]
    return ClientListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/clients", response_model=ClientDetail, status_code=status.HTTP_201_CREATED)
async def create_client(
    payload: ClientCreateRequest,
    session: AsyncSession = Depends(get_session),
    admin: AdminUser = Depends(get_current_admin),
):
    _require_roles(admin, AdminRole.ADMIN, AdminRole.MANAGER)
    client = await client_service.create_client(
        session,
        source_channel=SourceChannel(payload.source_channel),
        actor=admin,
        **payload.model_dump(exclude={"source_channel"}),
    )
    client = await client_service.get_client(session, client.id)
    return await _to_client_detail(session, client)


# ---------------- Client detail helpers ----------------

async def _to_client_detail(session: AsyncSession, client: Client) -> ClientDetail:
    names = await _staff_names(session, {client.manager_id, client.consultant_id})
    return ClientDetail(
        id=client.id,
        first_name=client.first_name,
        last_name=client.last_name,
        phone=client.phone,
        telegram_username=client.telegram_username,
        email=client.email,
        birth_date=client.birth_date,
        country=client.country,
        city=client.city,
        source_channel=client.source_channel.value,
        status=client.status.value,
        priority=client.priority.value,
        manager_id=client.manager_id,
        manager_name=names.get(client.manager_id),
        consultant_id=client.consultant_id,
        consultant_name=names.get(client.consultant_id),
        profile_completion=profile_completion(client, client.profile, client.work_experiences, client.skills, client.languages),
        created_at=client.created_at,
        last_activity_at=client.last_activity_at,
        profile=_profile_out(client.profile),
        work_experiences=[WorkExperienceOut(**{f: getattr(w, f) for f in WorkExperienceOut.model_fields}) for w in client.work_experiences],
        skills=[SkillOut(id=s.id, skill_name=s.skill_name, level=s.level.value if s.level else None, years_experience=s.years_experience, verified=s.verified) for s in client.skills],
        languages=[LanguageOut(id=l.id, language=l.language, level=l.level, can_work_in_it=l.can_work_in_it) for l in client.languages],
    )


@router.get("/clients/{client_id}", response_model=ClientDetail)
async def get_client(client_id: int, session: AsyncSession = Depends(get_session), admin: AdminUser = Depends(get_current_admin)):
    client = await _get_client_or_404(session, client_id, admin)
    return await _to_client_detail(session, client)


@router.patch("/clients/{client_id}", response_model=ClientDetail)
async def update_client(
    client_id: int,
    payload: ClientUpdateRequest,
    session: AsyncSession = Depends(get_session),
    admin: AdminUser = Depends(get_current_admin),
):
    client = await _get_client_or_404(session, client_id, admin)
    await client_service.update_client_fields(session, client, payload.model_dump(exclude_unset=True), admin)
    client = await client_service.get_client(session, client_id)
    return await _to_client_detail(session, client)


@router.patch("/clients/{client_id}/profile", response_model=ClientDetail)
async def update_client_profile(
    client_id: int,
    payload: ClientProfileUpdateRequest,
    session: AsyncSession = Depends(get_session),
    admin: AdminUser = Depends(get_current_admin),
):
    client = await _get_client_or_404(session, client_id, admin)
    await profile_blocks.update_profile(session, client.profile, payload.model_dump(exclude_unset=True), admin)
    client = await client_service.get_client(session, client_id)
    return await _to_client_detail(session, client)


# ---------------- Repeatable blocks ----------------

@router.post("/clients/{client_id}/work-experience", response_model=WorkExperienceOut)
async def add_work_experience(client_id: int, payload: WorkExperienceRequest, session: AsyncSession = Depends(get_session), admin: AdminUser = Depends(get_current_admin)):
    client = await _get_client_or_404(session, client_id, admin)
    row = await profile_blocks.add_work_experience(session, client.id, payload.model_dump(exclude_unset=True), admin)
    return WorkExperienceOut(**{f: getattr(row, f) for f in WorkExperienceOut.model_fields})


@router.patch("/clients/{client_id}/work-experience/{we_id}", response_model=WorkExperienceOut)
async def update_work_experience(client_id: int, we_id: int, payload: WorkExperienceRequest, session: AsyncSession = Depends(get_session), admin: AdminUser = Depends(get_current_admin)):
    client = await _get_client_or_404(session, client_id, admin)
    row = await session.get(WorkExperience, we_id)
    if row is None or row.client_id != client.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Work experience not found")
    row = await profile_blocks.update_work_experience(session, row, payload.model_dump(exclude_unset=True), admin)
    return WorkExperienceOut(**{f: getattr(row, f) for f in WorkExperienceOut.model_fields})


@router.delete("/clients/{client_id}/work-experience/{we_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_work_experience(client_id: int, we_id: int, session: AsyncSession = Depends(get_session), admin: AdminUser = Depends(get_current_admin)):
    client = await _get_client_or_404(session, client_id, admin)
    row = await session.get(WorkExperience, we_id)
    if row is None or row.client_id != client.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Work experience not found")
    await profile_blocks.delete_work_experience(session, row, admin)


@router.post("/clients/{client_id}/skills", response_model=SkillOut)
async def add_skill(client_id: int, payload: SkillRequest, session: AsyncSession = Depends(get_session), admin: AdminUser = Depends(get_current_admin)):
    client = await _get_client_or_404(session, client_id, admin)
    row = await profile_blocks.add_skill(session, client.id, payload.model_dump(exclude_unset=True), admin)
    return SkillOut(id=row.id, skill_name=row.skill_name, level=row.level.value if row.level else None, years_experience=row.years_experience, verified=row.verified)


@router.delete("/clients/{client_id}/skills/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_skill(client_id: int, skill_id: int, session: AsyncSession = Depends(get_session), admin: AdminUser = Depends(get_current_admin)):
    client = await _get_client_or_404(session, client_id, admin)
    row = await session.get(ClientSkill, skill_id)
    if row is None or row.client_id != client.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Skill not found")
    await profile_blocks.delete_skill(session, row, admin)


@router.post("/clients/{client_id}/languages", response_model=LanguageOut)
async def add_language(client_id: int, payload: LanguageRequest, session: AsyncSession = Depends(get_session), admin: AdminUser = Depends(get_current_admin)):
    client = await _get_client_or_404(session, client_id, admin)
    row = await profile_blocks.add_language(session, client.id, payload.model_dump(exclude_unset=True), admin)
    return LanguageOut(id=row.id, language=row.language, level=row.level, can_work_in_it=row.can_work_in_it)


@router.delete("/clients/{client_id}/languages/{lang_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_language(client_id: int, lang_id: int, session: AsyncSession = Depends(get_session), admin: AdminUser = Depends(get_current_admin)):
    client = await _get_client_or_404(session, client_id, admin)
    row = await session.get(ClientLanguage, lang_id)
    if row is None or row.client_id != client.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Language not found")
    await profile_blocks.delete_language(session, row, admin)


# ---------------- Workflow actions ----------------

@router.post("/clients/{client_id}/assign-consultant", response_model=ClientDetail)
async def assign_consultant(client_id: int, payload: AssignRequest, session: AsyncSession = Depends(get_session), admin: AdminUser = Depends(get_current_admin)):
    _require_roles(admin, AdminRole.ADMIN)
    client = await _get_client_or_404(session, client_id, admin)
    consultant = await session.get(AdminUser, payload.staff_id)
    if consultant is None or consultant.role != AdminRole.CAREER_CONSULTANT:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "staff_id must be an active CAREER_CONSULTANT")
    await client_service.assign_consultant(session, client, consultant, admin)
    client = await client_service.get_client(session, client_id)
    return await _to_client_detail(session, client)


@router.post("/clients/{client_id}/assign-manager", response_model=ClientDetail)
async def assign_manager(client_id: int, payload: AssignRequest, session: AsyncSession = Depends(get_session), admin: AdminUser = Depends(get_current_admin)):
    _require_roles(admin, AdminRole.ADMIN)
    client = await _get_client_or_404(session, client_id, admin)
    manager = await session.get(AdminUser, payload.staff_id)
    if manager is None or manager.role not in (AdminRole.ADMIN, AdminRole.MANAGER):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "staff_id must be an active ADMIN or MANAGER")
    await client_service.assign_manager(session, client, manager, admin)
    client = await client_service.get_client(session, client_id)
    return await _to_client_detail(session, client)


@router.post("/clients/{client_id}/status", response_model=ClientDetail)
async def set_status_manual(client_id: int, payload: StatusUpdateRequest, session: AsyncSession = Depends(get_session), admin: AdminUser = Depends(get_current_admin)):
    """Manual status override for edge cases (e.g. PAUSED, CLOSED)."""
    _require_roles(admin, AdminRole.ADMIN)
    client = await _get_client_or_404(session, client_id, admin)
    try:
        new_status = ClientStatus(payload.status)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Invalid status: {payload.status}")
    await client_service.set_status(session, client, new_status, admin)
    client = await client_service.get_client(session, client_id)
    return await _to_client_detail(session, client)


@router.post("/clients/{client_id}/screening/complete", response_model=ReadinessResponse)
async def complete_screening(client_id: int, session: AsyncSession = Depends(get_session), admin: AdminUser = Depends(get_current_admin)):
    client = await _get_client_or_404(session, client_id, admin)
    check = await client_service.try_complete_screening(session, client, admin)
    client = await client_service.get_client(session, client_id)
    return ReadinessResponse(ready=check.ready, missing=check.missing, status=client.status.value)


@router.post("/clients/{client_id}/ready-for-matching", response_model=ReadinessResponse)
async def ready_for_matching(client_id: int, session: AsyncSession = Depends(get_session), admin: AdminUser = Depends(get_current_admin)):
    _require_roles(admin, AdminRole.ADMIN, AdminRole.CAREER_CONSULTANT)
    client = await _get_client_or_404(session, client_id, admin)
    check = await client_service.try_mark_ready_for_matching(session, client, admin)
    client = await client_service.get_client(session, client_id)
    return ReadinessResponse(ready=check.ready, missing=check.missing, status=client.status.value)


# ---------------- Career consultation ----------------

@router.get("/clients/{client_id}/career-consultation", response_model=ConsultationOut)
async def get_consultation(client_id: int, session: AsyncSession = Depends(get_session), admin: AdminUser = Depends(get_current_admin)):
    client = await _get_client_or_404(session, client_id, admin)
    consultation = await consultation_service.get_or_create_consultation(session, client.id)
    return ConsultationOut(**{f: getattr(consultation, f) for f in ConsultationOut.model_fields})


@router.patch("/clients/{client_id}/career-consultation", response_model=ConsultationOut)
async def save_consultation_draft(client_id: int, payload: ConsultationDraftRequest, session: AsyncSession = Depends(get_session), admin: AdminUser = Depends(get_current_admin)):
    client = await _get_client_or_404(session, client_id, admin)
    consultation = await consultation_service.get_or_create_consultation(session, client.id)
    consultation = await consultation_service.save_draft(session, consultation, payload.model_dump(exclude_unset=True), admin)
    return ConsultationOut(**{f: getattr(consultation, f) for f in ConsultationOut.model_fields})


@router.post("/clients/{client_id}/career-consultation/complete", response_model=ConsultationOut)
async def complete_consultation(client_id: int, payload: ConsultationCompleteRequest, session: AsyncSession = Depends(get_session), admin: AdminUser = Depends(get_current_admin)):
    _require_roles(admin, AdminRole.ADMIN, AdminRole.CAREER_CONSULTANT)
    client = await _get_client_or_404(session, client_id, admin)
    consultation = await consultation_service.get_or_create_consultation(session, client.id)
    consultation = await consultation_service.complete_consultation(session, client, consultation, payload.conclusion, admin)
    return ConsultationOut(**{f: getattr(consultation, f) for f in ConsultationOut.model_fields})


# ---------------- Calls ----------------

@router.get("/clients/{client_id}/calls", response_model=list[CallOut])
async def list_calls(client_id: int, session: AsyncSession = Depends(get_session), admin: AdminUser = Depends(get_current_admin)):
    client = await _get_client_or_404(session, client_id, admin)
    calls = await call_service.list_calls(session, client.id)
    names = await _staff_names(session, {c.employee_id for c in calls})
    return [
        CallOut(id=c.id, direction=c.direction.value, status=c.status.value, duration_seconds=c.duration_seconds,
                employee_id=c.employee_id, employee_name=names.get(c.employee_id), contact_type=c.contact_type,
                note=c.note, recording_url=c.recording_url, started_at=c.started_at)
        for c in calls
    ]


@router.post("/clients/{client_id}/calls", response_model=CallOut)
async def log_call(client_id: int, payload: CallCreateRequest, session: AsyncSession = Depends(get_session), admin: AdminUser = Depends(get_current_admin)):
    client = await _get_client_or_404(session, client_id, admin)
    call = await call_service.log_call(session, client, payload.model_dump(), admin)
    return CallOut(id=call.id, direction=call.direction.value, status=call.status.value, duration_seconds=call.duration_seconds,
                    employee_id=call.employee_id, employee_name=admin.full_name or admin.email, contact_type=call.contact_type,
                    note=call.note, recording_url=call.recording_url, started_at=call.started_at)


# ---------------- Tasks ----------------

@router.get("/clients/{client_id}/tasks", response_model=list[TaskOut])
async def list_tasks(client_id: int, session: AsyncSession = Depends(get_session), admin: AdminUser = Depends(get_current_admin)):
    client = await _get_client_or_404(session, client_id, admin)
    tasks = await task_service.list_tasks_for_client(session, client.id)
    names = await _staff_names(session, {t.assignee_id for t in tasks})
    return [
        TaskOut(id=t.id, task_type=t.task_type, other_description=t.other_description, assignee_id=t.assignee_id,
                assignee_name=names.get(t.assignee_id), due_at=t.due_at, status=t.status.value, note=t.note,
                created_at=t.created_at, completed_at=t.completed_at)
        for t in tasks
    ]


@router.post("/clients/{client_id}/tasks", response_model=TaskOut)
async def create_task(client_id: int, payload: TaskCreateRequest, session: AsyncSession = Depends(get_session), admin: AdminUser = Depends(get_current_admin)):
    client = await _get_client_or_404(session, client_id, admin)
    task = await task_service.create_task(session, client, payload.model_dump())
    names = await _staff_names(session, {task.assignee_id})
    return TaskOut(id=task.id, task_type=task.task_type, other_description=task.other_description, assignee_id=task.assignee_id,
                    assignee_name=names.get(task.assignee_id), due_at=task.due_at, status=task.status.value, note=task.note,
                    created_at=task.created_at, completed_at=task.completed_at)


async def _get_task_or_404(session: AsyncSession, task_id: int, admin: AdminUser) -> Task:
    task = await session.get(Task, task_id)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    client = await _get_client_or_404(session, task.client_id, admin)  # RBAC via client scope
    return task


@router.post("/tasks/{task_id}/complete", response_model=TaskOut)
async def complete_task(task_id: int, session: AsyncSession = Depends(get_session), admin: AdminUser = Depends(get_current_admin)):
    task = await _get_task_or_404(session, task_id, admin)
    task = await task_service.complete_task(session, task)
    names = await _staff_names(session, {task.assignee_id})
    return TaskOut(id=task.id, task_type=task.task_type, other_description=task.other_description, assignee_id=task.assignee_id,
                    assignee_name=names.get(task.assignee_id), due_at=task.due_at, status=task.status.value, note=task.note,
                    created_at=task.created_at, completed_at=task.completed_at)


@router.post("/tasks/{task_id}/cancel", response_model=TaskOut)
async def cancel_task(task_id: int, session: AsyncSession = Depends(get_session), admin: AdminUser = Depends(get_current_admin)):
    task = await _get_task_or_404(session, task_id, admin)
    task = await task_service.cancel_task(session, task)
    names = await _staff_names(session, {task.assignee_id})
    return TaskOut(id=task.id, task_type=task.task_type, other_description=task.other_description, assignee_id=task.assignee_id,
                    assignee_name=names.get(task.assignee_id), due_at=task.due_at, status=task.status.value, note=task.note,
                    created_at=task.created_at, completed_at=task.completed_at)


# ---------------- Timeline ----------------

@router.get("/clients/{client_id}/timeline", response_model=list[TimelineEventOut])
async def get_timeline(client_id: int, session: AsyncSession = Depends(get_session), admin: AdminUser = Depends(get_current_admin)):
    client = await _get_client_or_404(session, client_id, admin)
    events = await timeline_service.list_events(session, client.id)
    names = await _staff_names(session, {e.actor_id for e in events})
    return [
        TimelineEventOut(id=e.id, event_type=e.event_type.value, description=e.description, actor_id=e.actor_id,
                          actor_name=names.get(e.actor_id) or "Система", before_value=e.before_value,
                          after_value=e.after_value, created_at=e.created_at)
        for e in events
    ]


# ---------------- Files ----------------

@router.get("/clients/{client_id}/files", response_model=list[FileOut])
async def list_files(client_id: int, session: AsyncSession = Depends(get_session), admin: AdminUser = Depends(get_current_admin)):
    client = await _get_client_or_404(session, client_id, admin)
    files = await file_service.list_files(session, client.id)
    names = await _staff_names(session, {f.uploaded_by_id for f in files})
    return [
        FileOut(id=f.id, file_type=f.file_type.value, other_description=f.other_description, filename=f.filename,
                content_type=f.content_type, size_bytes=f.size_bytes, is_current_cv=f.is_current_cv,
                uploaded_by_id=f.uploaded_by_id, uploaded_by_name=names.get(f.uploaded_by_id), uploaded_at=f.uploaded_at)
        for f in files
    ]


@router.post("/clients/{client_id}/files", response_model=FileOut)
async def upload_file(
    client_id: int,
    file_type: str = Form(...),
    other_description: str | None = Form(None),
    upload: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    admin: AdminUser = Depends(get_current_admin),
):
    client = await _get_client_or_404(session, client_id, admin)
    data = await upload.read()
    if len(data) > settings.max_upload_size_mb * 1024 * 1024:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"File exceeds {settings.max_upload_size_mb}MB limit")

    row = await file_service.upload_file(
        session, client, file_type=file_type, other_description=other_description,
        filename=upload.filename or "file", content_type=upload.content_type, data=data, actor=admin,
    )
    return FileOut(id=row.id, file_type=row.file_type.value, other_description=row.other_description, filename=row.filename,
                    content_type=row.content_type, size_bytes=row.size_bytes, is_current_cv=row.is_current_cv,
                    uploaded_by_id=row.uploaded_by_id, uploaded_by_name=admin.full_name or admin.email, uploaded_at=row.uploaded_at)


@router.get("/clients/{client_id}/files/{file_id}/download")
async def download_file(client_id: int, file_id: int, session: AsyncSession = Depends(get_session), admin: AdminUser = Depends(get_current_admin)):
    client = await _get_client_or_404(session, client_id, admin)
    file = await file_service.get_file(session, file_id)
    if file is None or file.client_id != client.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")
    data = get_storage().read(file.storage_key)
    return Response(
        content=data,
        media_type=file.content_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{file.filename}"'},
    )


@router.patch("/clients/{client_id}/files/{file_id}/current-cv", response_model=FileOut)
async def mark_current_cv(client_id: int, file_id: int, session: AsyncSession = Depends(get_session), admin: AdminUser = Depends(get_current_admin)):
    client = await _get_client_or_404(session, client_id, admin)
    file = await file_service.get_file(session, file_id)
    if file is None or file.client_id != client.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")
    file = await file_service.mark_current_cv(session, file, admin)
    return FileOut(id=file.id, file_type=file.file_type.value, other_description=file.other_description, filename=file.filename,
                    content_type=file.content_type, size_bytes=file.size_bytes, is_current_cv=file.is_current_cv,
                    uploaded_by_id=file.uploaded_by_id, uploaded_by_name=None, uploaded_at=file.uploaded_at)


@router.delete("/clients/{client_id}/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(client_id: int, file_id: int, session: AsyncSession = Depends(get_session), admin: AdminUser = Depends(get_current_admin)):
    client = await _get_client_or_404(session, client_id, admin)
    file = await file_service.get_file(session, file_id)
    if file is None or file.client_id != client.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")
    await file_service.delete_file(session, file, admin)


# ---------------- Staff (users) ----------------

@router.get("/users/assignable", response_model=list[StaffOut])
async def assignable_staff(
    role: str = Query(..., pattern="^(manager|career_consultant|admin)$"),
    session: AsyncSession = Depends(get_session),
    admin: AdminUser = Depends(get_current_admin),
):
    """Lightweight, available to any authenticated staff member — used to
    populate Manager/Consultant dropdowns without exposing full staff mgmt
    (that's ADMIN-only, see GET /crm/users)."""
    result = await session.execute(
        select(AdminUser).where(AdminUser.role == AdminRole(role), AdminUser.is_active.is_(True))
    )
    return [
        StaffOut(id=a.id, full_name=a.full_name, email=a.email, role=a.role.value, is_active=a.is_active, created_at=a.created_at)
        for a in result.scalars().all()
    ]


@router.get("/users", response_model=list[StaffOut])
async def list_staff(session: AsyncSession = Depends(get_session), admin: AdminUser = Depends(get_current_admin)):
    _require_roles(admin, AdminRole.ADMIN)
    result = await session.execute(select(AdminUser).order_by(AdminUser.created_at))
    return [
        StaffOut(id=a.id, full_name=a.full_name, email=a.email, role=a.role.value, is_active=a.is_active, created_at=a.created_at)
        for a in result.scalars().all()
    ]


@router.post("/users", response_model=StaffOut, status_code=status.HTTP_201_CREATED)
async def create_staff(payload: StaffCreateRequest, session: AsyncSession = Depends(get_session), admin: AdminUser = Depends(get_current_admin)):
    _require_roles(admin, AdminRole.ADMIN)
    existing = await session.execute(select(AdminUser).where(AdminUser.email == payload.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Email already in use")

    staff = AdminUser(
        full_name=payload.full_name, email=payload.email,
        password_hash=hash_password(payload.password), role=AdminRole(payload.role),
    )
    session.add(staff)
    await session.commit()
    await session.refresh(staff)
    return StaffOut(id=staff.id, full_name=staff.full_name, email=staff.email, role=staff.role.value, is_active=staff.is_active, created_at=staff.created_at)


@router.patch("/users/{staff_id}", response_model=StaffOut)
async def update_staff(staff_id: int, payload: StaffUpdateRequest, session: AsyncSession = Depends(get_session), admin: AdminUser = Depends(get_current_admin)):
    _require_roles(admin, AdminRole.ADMIN)
    staff = await session.get(AdminUser, staff_id)
    if staff is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Staff not found")

    if payload.full_name is not None:
        staff.full_name = payload.full_name
    if payload.role is not None:
        staff.role = AdminRole(payload.role)
    if payload.is_active is not None:
        staff.is_active = payload.is_active
    if payload.password:
        staff.password_hash = hash_password(payload.password)

    await session.commit()
    await session.refresh(staff)
    return StaffOut(id=staff.id, full_name=staff.full_name, email=staff.email, role=staff.role.value, is_active=staff.is_active, created_at=staff.created_at)
