"""Staff access to the canonical Person KB; no parallel client model."""
import uuid

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.db.models import AdminRole, AdminUser
from app.db.models_person_kb import MnpPerson, MnpPersonAccess
from app.db.session import get_session

PRIVILEGED = (AdminRole.SUPER_ADMIN, AdminRole.ADMIN)
STAFF = (*PRIVILEGED, AdminRole.MANAGER)


def visible_persons(admin: AdminUser):
    query = select(MnpPerson)
    if admin.role not in PRIVILEGED:
        query = query.where(MnpPerson.id.in_(
            select(MnpPersonAccess.person_id).where(MnpPersonAccess.admin_id == admin.id)))
    return query.order_by(MnpPerson.updated_at.desc())


async def person_staff(request: Request, admin: AdminUser = Depends(get_current_admin),
                       session: AsyncSession = Depends(get_session)):
    if admin.role not in STAFF:
        raise HTTPException(403, "Немає доступу до консолі")
    raw_id = request.path_params.get("person_id")
    if raw_id and admin.role not in PRIVILEGED:
        try:
            person_id = uuid.UUID(str(raw_id))
        except ValueError:
            raise HTTPException(422, "Невірний ID клієнта")
        access = await session.get(MnpPersonAccess, (person_id, admin.id))
        if access is None:
            raise HTTPException(404, "Клієнта не знайдено")
    return admin
