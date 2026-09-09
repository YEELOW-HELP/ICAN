from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from pymongo.errors import DuplicateKeyError

from app.core.security import create_access_token, hash_password, verify_password
from app.mongo_runtime.core import (
    ADMIN, MANAGER, PRIVILEGED_ROLES, STAFF_ROLES, SUPER_ADMIN, Database,
    current_staff, next_integer_id, now, privileged_staff, public_document,
)

router = APIRouter()


class Login(BaseModel):
    email: str
    password: str


class StaffCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(max_length=255)
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=72)
    role: str = MANAGER


class StaffUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    role: str | None = None
    is_active: bool | None = None


def staff_view(staff: dict):
    return {"id": staff["_id"], "email": staff["email"],
            "full_name": staff.get("full_name"), "role": staff["role"],
            "is_active": bool(staff.get("is_active", True))}


def valid_email(value: str) -> str:
    value = value.strip().lower()
    if "@" not in value or len(value) > 255:
        raise HTTPException(422, "Перевірте email")
    return value


def check_role(actor: dict, target: dict | None, role: str):
    if role not in STAFF_ROLES:
        raise HTTPException(422, "Невідома роль")
    if actor["role"] != SUPER_ADMIN and (role != MANAGER or (target and target["role"] != MANAGER)):
        raise HTTPException(403, "Адміністратор може керувати лише менеджерами")


@router.get("/admin/auth/bootstrap/status")
async def bootstrap_status(db: Database):
    return {"registration_open": await db.admin_users.count_documents({"role": SUPER_ADMIN}) == 0}


@router.post("/admin/auth/bootstrap", status_code=201)
async def bootstrap_owner(payload: StaffCreate, db: Database):
    if payload.role != SUPER_ADMIN:
        raise HTTPException(422, "Перший обліковий запис має бути суперадміністратором")
    email = valid_email(payload.email)
    staff = {
        "_id": await next_integer_id(db, "admin_users"), "email": email,
        "full_name": payload.full_name.strip(), "role": SUPER_ADMIN,
        "password_hash": hash_password(payload.password), "is_active": True,
        "bootstrap_owner": True, "created_at": now(),
    }
    try:
        await db.admin_users.insert_one(staff)
    except DuplicateKeyError:
        raise HTTPException(409, "Суперадміністратора вже створено або email зайнятий")
    return staff_view(staff)


@router.post("/admin/auth/login")
async def login(payload: Login, db: Database):
    staff = await db.admin_users.find_one({"email": payload.email.strip().lower(), "is_active": {"$ne": False}})
    if not staff or not verify_password(payload.password, staff["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    return {"access_token": create_access_token(staff["_id"], staff["role"]),
            "token_type": "bearer", "email": staff["email"], "role": staff["role"]}


@router.get("/v1/mnp/admin/me")
async def me(staff=Depends(current_staff)):
    return staff_view(staff)


@router.get("/v1/mnp/admin/staff")
async def list_staff(db: Database, _staff=Depends(privileged_staff)):
    return [staff_view(row) async for row in db.admin_users.find().sort("email", 1)]


@router.post("/v1/mnp/admin/staff", status_code=201)
async def create_staff(payload: StaffCreate, db: Database, actor=Depends(privileged_staff)):
    check_role(actor, None, payload.role)
    email = valid_email(payload.email)
    staff = {
        "_id": await next_integer_id(db, "admin_users"), "email": email,
        "full_name": payload.full_name.strip(), "role": payload.role,
        "password_hash": hash_password(payload.password), "is_active": True,
        "created_at": now(),
    }
    try:
        await db.admin_users.insert_one(staff)
    except DuplicateKeyError:
        raise HTTPException(409, "Такий email уже зареєстрований")
    await db.audit_logs.insert_one({"entity_type": "staff", "entity_id": str(staff["_id"]),
                                    "action": "staff_created", "actor_admin_id": actor["_id"],
                                    "created_at": now()})
    return staff_view(staff)


@router.patch("/v1/mnp/admin/staff/{staff_id}")
async def update_staff(staff_id: int, payload: StaffUpdate, db: Database,
                       actor=Depends(privileged_staff)):
    target = await db.admin_users.find_one({"_id": staff_id})
    if not target:
        raise HTTPException(404, "Працівника не знайдено")
    role = payload.role or target["role"]
    check_role(actor, target, role)
    if target["_id"] == actor["_id"] and (payload.is_active is False or role != target["role"]):
        raise HTTPException(409, "Не можна вимкнути себе або змінити власну роль")
    if target["role"] == SUPER_ADMIN and (payload.is_active is False or role != SUPER_ADMIN):
        raise HTTPException(409, "Суперадміністратора не можна вимкнути або понизити")
    changes = payload.model_dump(exclude_none=True)
    if "full_name" in changes:
        changes["full_name"] = changes["full_name"].strip()
    await db.admin_users.update_one({"_id": staff_id}, {"$set": changes})
    await db.audit_logs.insert_one({"entity_type": "staff", "entity_id": str(staff_id),
                                    "action": "staff_updated", "actor_admin_id": actor["_id"],
                                    "changes": list(changes), "created_at": now()})
    return staff_view(await db.admin_users.find_one({"_id": staff_id}))
