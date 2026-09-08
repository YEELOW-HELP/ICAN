from __future__ import annotations

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.models import AdminRole, AdminUser
from app.db.session import get_session

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> AdminUser:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")

    try:
        payload = decode_access_token(credentials.credentials)
        admin_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")

    admin = await session.get(AdminUser, admin_id)
    if admin is None or not admin.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Admin account no longer exists")
    return admin


async def get_privileged_admin(admin: AdminUser = Depends(get_current_admin)) -> AdminUser:
    if admin.role not in (AdminRole.SUPER_ADMIN, AdminRole.ADMIN):
        raise HTTPException(403, "Потрібна роль адміністратора")
    return admin
