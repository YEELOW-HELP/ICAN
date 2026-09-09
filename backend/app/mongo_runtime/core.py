from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pymongo import ReturnDocument

from app.core.config import settings
from app.core.security import decode_access_token

SUPER_ADMIN = "super_admin"
ADMIN = "admin"
MANAGER = "manager"
STAFF_ROLES = (SUPER_ADMIN, ADMIN, MANAGER)
PRIVILEGED_ROLES = (SUPER_ADMIN, ADMIN)
bearer = HTTPBearer(auto_error=False)


def now() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid.uuid4())


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def public_document(document: dict | None) -> dict | None:
    if document is None:
        return None
    result = dict(document)
    if "_id" in result:
        result["id"] = str(result.pop("_id"))
    return result


async def database(request: Request):
    return request.app.state.database


Database = Annotated[object, Depends(database)]


async def next_integer_id(db, name: str) -> int:
    row = await db.counters.find_one_and_update(
        {"_id": name}, {"$inc": {"value": 1}}, upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return int(row["value"])


async def current_staff(
    db: Database,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
):
    if credentials is None:
        raise HTTPException(401, "Not authenticated")
    try:
        payload = decode_access_token(credentials.credentials)
        staff_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, TypeError, ValueError):
        raise HTTPException(401, "Invalid or expired token")
    staff = await db.admin_users.find_one({"_id": staff_id, "is_active": {"$ne": False}})
    if not staff or staff.get("role") not in STAFF_ROLES:
        raise HTTPException(401, "Staff account no longer exists")
    return staff


async def privileged_staff(staff=Depends(current_staff)):
    if staff["role"] not in PRIVILEGED_ROLES:
        raise HTTPException(403, "Потрібна роль адміністратора")
    return staff


async def current_person_session(
    db: Database,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
):
    if credentials is None:
        raise HTTPException(401, "Потрібна сесія")
    digest = token_digest(credentials.credentials.strip())
    row = await db.mnp_web_sessions.find_one({"$or": [
        {"_id": digest, "expires_at": {"$gt": now()}},
        {"token_hash": digest, "revoked_at": None},
    ]})
    if not row:
        raise HTTPException(401, "Недійсна або завершена сесія")
    await db.mnp_web_sessions.update_one({"_id": row["_id"]}, {"$set": {"last_seen_at": now()}})
    return row


def new_web_session() -> tuple[str, dict]:
    token = secrets.token_urlsafe(32)
    user_id = new_id()
    return token, {
        "_id": token_digest(token), "token_hash": token_digest(token), "user_id": user_id,
        "created_at": now(), "last_seen_at": now(), "revoked_at": None,
        "expires_at": now() + timedelta(days=30),
    }
