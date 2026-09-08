"""Console staff provisioning and explicit Person KB sharing."""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_privileged_admin
from app.core.security import hash_password
from app.db.models import AdminRole, AdminUser
from app.db.models_person_kb import MnpPerson, MnpPersonAccess
from app.db.models_platform import AuditLog
from app.db.session import get_session

router = APIRouter(prefix="/v1/mnp/admin", tags=["workspace"])


def staff_view(staff):
    return {"id": staff.id, "email": staff.email, "full_name": staff.full_name,
            "role": staff.role.value, "is_active": staff.is_active}


class StaffCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(max_length=255)
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=72)
    role: AdminRole = AdminRole.MANAGER


class StaffUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    role: AdminRole | None = None
    is_active: bool | None = None


def check_role_change(actor, target, new_role):
    if new_role not in (AdminRole.SUPER_ADMIN, AdminRole.ADMIN, AdminRole.MANAGER):
        raise HTTPException(422, "Оберіть роль: суперадмін, адмін або менеджер")
    if actor.role != AdminRole.SUPER_ADMIN:
        if new_role != AdminRole.MANAGER or (target and target.role != AdminRole.MANAGER):
            raise HTTPException(403, "Адміністратор може керувати лише менеджерами")


@router.get("/staff")
async def list_staff(admin: AdminUser = Depends(get_privileged_admin), session: AsyncSession = Depends(get_session)):
    return [staff_view(s) for s in (await session.scalars(select(AdminUser).order_by(AdminUser.email))).all()]


@router.post("/staff", status_code=201)
async def create_staff(payload: StaffCreate, admin: AdminUser = Depends(get_privileged_admin), session: AsyncSession = Depends(get_session)):
    check_role_change(admin, None, payload.role)
    email = payload.email.strip().lower()
    if "@" not in email or len(payload.password.encode("utf-8")) > 72:
        raise HTTPException(422, "Перевірте email та довжину пароля (до 72 байтів)")
    if await session.scalar(select(AdminUser.id).where(func.lower(AdminUser.email) == email)):
        raise HTTPException(409, "Такий email уже зареєстрований")
    staff = AdminUser(email=email, full_name=payload.full_name.strip(), role=payload.role,
                      password_hash=hash_password(payload.password), is_active=True)
    session.add(staff)
    try:
        await session.flush()
        session.add(AuditLog(actor_admin_id=admin.id, entity_type="staff", entity_id=str(staff.id),
                             action="staff_created", after_snapshot={"role": staff.role.value}))
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(409, "Такий email уже зареєстрований")
    return staff_view(staff)


@router.patch("/staff/{staff_id}")
async def update_staff(staff_id: int, payload: StaffUpdate, admin: AdminUser = Depends(get_privileged_admin), session: AsyncSession = Depends(get_session)):
    staff = await session.get(AdminUser, staff_id)
    if not staff:
        raise HTTPException(404, "Працівника не знайдено")
    check_role_change(admin, staff, payload.role or staff.role)
    if staff.id == admin.id and ((payload.role and payload.role != staff.role) or payload.is_active is False):
        raise HTTPException(409, "Не можна вимкнути власний обліковий запис або змінити власну роль")
    # Keep every existing superadmin protected from demotion/deactivation here.
    if staff.role == AdminRole.SUPER_ADMIN and (payload.is_active is False or payload.role not in (None, AdminRole.SUPER_ADMIN)):
        raise HTTPException(409, "Зміна доступу суперадміна виконується через локальне налаштування")
    before = staff_view(staff)
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(staff, field, value)
    session.add(AuditLog(actor_admin_id=admin.id, entity_type="staff", entity_id=str(staff.id),
                         action="staff_updated", before_snapshot=before, after_snapshot=staff_view(staff)))
    await session.commit()
    return staff_view(staff)


@router.get("/persons/{person_id}/access")
async def person_access(person_id: uuid.UUID, admin: AdminUser = Depends(get_privileged_admin), session: AsyncSession = Depends(get_session)):
    if not await session.get(MnpPerson, person_id):
        raise HTTPException(404, "Клієнта не знайдено")
    rows = (await session.execute(select(MnpPersonAccess, AdminUser).join(AdminUser, AdminUser.id == MnpPersonAccess.admin_id)
                                 .where(MnpPersonAccess.person_id == person_id))).all()
    return [{**staff_view(staff), "is_creator": grant.is_creator} for grant, staff in rows]


@router.put("/persons/{person_id}/access/{staff_id}", status_code=204)
async def grant_access(person_id: uuid.UUID, staff_id: int, admin: AdminUser = Depends(get_privileged_admin), session: AsyncSession = Depends(get_session)):
    if not await session.get(MnpPerson, person_id):
        raise HTTPException(404, "Клієнта не знайдено")
    target = await session.get(AdminUser, staff_id)
    if not target or not target.is_active or target.role != AdminRole.MANAGER:
        raise HTTPException(422, "Оберіть активного менеджера")
    if await session.get(MnpPersonAccess, (person_id, staff_id)):
        return
    session.add(MnpPersonAccess(person_id=person_id, admin_id=staff_id, granted_by=admin.id, is_creator=False))
    session.add(AuditLog(actor_admin_id=admin.id, entity_type="mnp_person", entity_id=str(person_id),
                         action="person_access_granted", after_snapshot={"admin_id": staff_id}))
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(409, "Доступ уже змінився. Оновіть сторінку")


@router.delete("/persons/{person_id}/access/{staff_id}", status_code=204)
async def revoke_access(person_id: uuid.UUID, staff_id: int, admin: AdminUser = Depends(get_privileged_admin), session: AsyncSession = Depends(get_session)):
    grant = await session.get(MnpPersonAccess, (person_id, staff_id))
    if grant:
        if grant.is_creator:
            raise HTTPException(409, "Автор зберігає доступ до створеного ним клієнта")
        await session.delete(grant)
        session.add(AuditLog(actor_admin_id=admin.id, entity_type="mnp_person", entity_id=str(person_id),
                             action="person_access_revoked", after_snapshot={"admin_id": staff_id}))
        await session.commit()
