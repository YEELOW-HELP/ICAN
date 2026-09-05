"""PERSON KB BASE V1 -- API.

Admin routes (`/v1/mnp/admin/persons/...`, admin bearer) + user routes
(`/v1/mnp/me/person/...`, `Authorization: Bearer <session-token>` from
`POST /v1/mnp/session`) + CV intake. All write through
`app.services.person_kb`. A user can only ever touch their OWN Person KB
-- the identity is resolved server-side from the session token, never
from a client-supplied UUID or path id.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Body, Depends, File, Header, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.api.mnp import _check_upload_rate_limit
from app.db.models import AdminUser
from app.db.models_identity import IdentityUser
from app.db.models_person_kb import PersonSource
from app.db.session import get_session
from app.services.person_kb import cv_intake, service
from app.services.person_kb.service import PersonKbError, PersonNotFoundError
from app.services.person_kb.sessions import bearer_from_header, resolve_web_session
from app.services.person_kb.views import person_list_row, serialize_person

router = APIRouter(prefix="/v1/mnp", tags=["person-kb"])


async def get_mnp_session_user(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> IdentityUser:
    """Person KB private-route auth. `Authorization: Bearer <session-token>`
    ONLY -- a client-supplied `X-Mnp-User-Id` is never trusted here. The
    token is minted by `POST /v1/mnp/session`, is not derivable from the
    user id, and resolves the `IdentityUser` server-side."""
    token = bearer_from_header(authorization)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                            "Потрібна сесія -- викличте POST /v1/mnp/session")
    user = await resolve_web_session(session, token)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Недійсна або завершена сесія")
    return user


_COLLECTIONS = ("educations", "credentials", "experiences", "activities", "languages")


def _err(exc: Exception):
    if isinstance(exc, PersonNotFoundError):
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    if isinstance(exc, (PersonKbError, ValueError)):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    raise exc


# ===========================================================================
# ADMIN
# ===========================================================================
@router.get("/admin/persons")
async def admin_list(admin: AdminUser = Depends(get_current_admin),
                     session: AsyncSession = Depends(get_session)):
    rows = await service.list_persons(session)
    return [person_list_row(p) for p in rows]


@router.post("/admin/persons", status_code=status.HTTP_201_CREATED)
async def admin_create(payload: dict = Body(...), admin: AdminUser = Depends(get_current_admin),
                       session: AsyncSession = Depends(get_session)):
    try:
        person = await service.create_person(
            session, first_name=payload.get("first_name", ""), source=PersonSource.ADMIN_MANUAL,
            actor_admin_id=admin.id, **{k: payload[k] for k in (
                "last_name", "phone", "email", "telegram_username", "city", "region", "country",
                "date_of_birth", "notes") if k in payload})
    except Exception as exc:  # noqa: BLE001
        _err(exc)
    return serialize_person(person)


@router.get("/admin/persons/skills/search")
async def admin_skill_search(q: str = "", admin: AdminUser = Depends(get_current_admin),
                             session: AsyncSession = Depends(get_session)):
    rows = await service.search_canonical_skills(session, q)
    return [{"id": str(s.id), "name_uk": s.canonical_name_uk, "name_en": s.canonical_name_en,
             "skill_type": s.skill_type.value} for s in rows]


@router.get("/admin/persons/{person_id}")
async def admin_get(person_id: uuid.UUID, admin: AdminUser = Depends(get_current_admin),
                    session: AsyncSession = Depends(get_session)):
    try:
        return serialize_person(await service.get_person(session, person_id))
    except Exception as exc:  # noqa: BLE001
        _err(exc)


@router.patch("/admin/persons/{person_id}")
async def admin_update_core(person_id: uuid.UUID, payload: dict = Body(...),
                            admin: AdminUser = Depends(get_current_admin),
                            session: AsyncSession = Depends(get_session)):
    try:
        return serialize_person(await service.update_person_core(
            session, person_id, actor_admin_id=admin.id, **payload))
    except Exception as exc:  # noqa: BLE001
        _err(exc)


@router.post("/admin/persons/{person_id}/activate")
async def admin_activate(person_id: uuid.UUID, admin: AdminUser = Depends(get_current_admin),
                         session: AsyncSession = Depends(get_session)):
    try:
        return serialize_person(await service.activate_person(session, person_id, actor_admin_id=admin.id))
    except Exception as exc:  # noqa: BLE001
        _err(exc)


@router.post("/admin/persons/{person_id}/archive")
async def admin_archive(person_id: uuid.UUID, admin: AdminUser = Depends(get_current_admin),
                        session: AsyncSession = Depends(get_session)):
    try:
        return serialize_person(await service.set_status(
            session, person_id, status="archived", actor_admin_id=admin.id))
    except Exception as exc:  # noqa: BLE001
        _err(exc)


@router.post("/admin/persons/{person_id}/unarchive")
async def admin_unarchive(person_id: uuid.UUID, admin: AdminUser = Depends(get_current_admin),
                          session: AsyncSession = Depends(get_session)):
    try:
        return serialize_person(await service.set_status(
            session, person_id, status="draft", actor_admin_id=admin.id))
    except Exception as exc:  # noqa: BLE001
        _err(exc)


def _mount_admin_collection(name: str) -> None:
    @router.post(f"/admin/persons/{{person_id}}/{name}", name=f"admin_add_{name}")
    async def _add(person_id: uuid.UUID, payload: dict = Body(...),
                   admin: AdminUser = Depends(get_current_admin),
                   session: AsyncSession = Depends(get_session)):
        try:
            return serialize_person(await service.add_row(
                session, person_id, name, payload, actor_admin_id=admin.id,
                source=PersonSource.ADMIN_MANUAL))
        except Exception as exc:  # noqa: BLE001
            _err(exc)

    @router.patch(f"/admin/persons/{{person_id}}/{name}/{{row_id}}", name=f"admin_update_{name}")
    async def _upd(person_id: uuid.UUID, row_id: uuid.UUID, payload: dict = Body(...),
                   admin: AdminUser = Depends(get_current_admin),
                   session: AsyncSession = Depends(get_session)):
        try:
            return serialize_person(await service.update_row(
                session, person_id, name, row_id, payload, actor_admin_id=admin.id,
                source=PersonSource.ADMIN_EDIT))
        except Exception as exc:  # noqa: BLE001
            _err(exc)

    @router.delete(f"/admin/persons/{{person_id}}/{name}/{{row_id}}", name=f"admin_delete_{name}")
    async def _del(person_id: uuid.UUID, row_id: uuid.UUID,
                   admin: AdminUser = Depends(get_current_admin),
                   session: AsyncSession = Depends(get_session)):
        try:
            return serialize_person(await service.delete_row(
                session, person_id, name, row_id, actor_admin_id=admin.id))
        except Exception as exc:  # noqa: BLE001
            _err(exc)


for _c in _COLLECTIONS:
    _mount_admin_collection(_c)


@router.post("/admin/persons/{person_id}/skills")
async def admin_add_skill(person_id: uuid.UUID, payload: dict = Body(...),
                          admin: AdminUser = Depends(get_current_admin),
                          session: AsyncSession = Depends(get_session)):
    try:
        return serialize_person(await service.add_skill(
            session, person_id, actor_admin_id=admin.id, source=PersonSource.ADMIN_MANUAL,
            **{k: payload.get(k) for k in ("canonical_skill_id", "raw_input", "proficiency",
                                           "years_used", "last_used_year", "notes", "evidence_state")}))
    except Exception as exc:  # noqa: BLE001
        _err(exc)


@router.patch("/admin/persons/{person_id}/skills/{row_id}")
async def admin_update_skill(person_id: uuid.UUID, row_id: uuid.UUID, payload: dict = Body(...),
                             admin: AdminUser = Depends(get_current_admin),
                             session: AsyncSession = Depends(get_session)):
    try:
        return serialize_person(await service.update_skill(
            session, person_id, row_id, payload, actor_admin_id=admin.id, source=PersonSource.ADMIN_EDIT))
    except Exception as exc:  # noqa: BLE001
        _err(exc)


@router.delete("/admin/persons/{person_id}/skills/{row_id}")
async def admin_delete_skill(person_id: uuid.UUID, row_id: uuid.UUID,
                             admin: AdminUser = Depends(get_current_admin),
                             session: AsyncSession = Depends(get_session)):
    try:
        return serialize_person(await service.delete_skill(
            session, person_id, row_id, actor_admin_id=admin.id))
    except Exception as exc:  # noqa: BLE001
        _err(exc)


# ===========================================================================
# USER (own profile only)
# ===========================================================================
async def _my_person(session: AsyncSession, user: IdentityUser, *, create: bool = False):
    person = await service.get_person_by_identity(session, user.id)
    if person is None and create:
        person = await service.create_person(
            session, first_name="—", source=PersonSource.USER_MANUAL, identity_user_id=user.id)
    if person is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Профіль ще не створено")
    return person


@router.get("/me/person")
async def me_get(user: IdentityUser = Depends(get_mnp_session_user),
                 session: AsyncSession = Depends(get_session)):
    person = await service.get_person_by_identity(session, user.id)
    return serialize_person(person) if person else {"person": None}


@router.post("/me/person")
async def me_upsert_core(payload: dict = Body(...), user: IdentityUser = Depends(get_mnp_session_user),
                         session: AsyncSession = Depends(get_session)):
    try:
        person = await service.get_person_by_identity(session, user.id)
        if person is None:
            person = await service.create_person(
                session, first_name=payload.get("first_name") or "—", source=PersonSource.USER_MANUAL,
                identity_user_id=user.id)
        return serialize_person(await service.update_person_core(session, person.id, **payload))
    except Exception as exc:  # noqa: BLE001
        _err(exc)


@router.get("/me/person/skills/search")
async def me_skill_search(q: str = "", user: IdentityUser = Depends(get_mnp_session_user),
                          session: AsyncSession = Depends(get_session)):
    rows = await service.search_canonical_skills(session, q)
    return [{"id": str(s.id), "name_uk": s.canonical_name_uk, "name_en": s.canonical_name_en} for s in rows]


def _mount_user_collection(name: str) -> None:
    @router.post(f"/me/person/{name}", name=f"me_add_{name}")
    async def _add(payload: dict = Body(...), user: IdentityUser = Depends(get_mnp_session_user),
                   session: AsyncSession = Depends(get_session)):
        try:
            person = await _my_person(session, user, create=True)
            return serialize_person(await service.add_row(
                session, person.id, name, payload, source=PersonSource.USER_MANUAL))
        except Exception as exc:  # noqa: BLE001
            _err(exc)

    @router.patch(f"/me/person/{name}/{{row_id}}", name=f"me_update_{name}")
    async def _upd(row_id: uuid.UUID, payload: dict = Body(...),
                   user: IdentityUser = Depends(get_mnp_session_user),
                   session: AsyncSession = Depends(get_session)):
        try:
            person = await _my_person(session, user)
            return serialize_person(await service.update_row(
                session, person.id, name, row_id, payload, source=PersonSource.USER_MANUAL))
        except Exception as exc:  # noqa: BLE001
            _err(exc)

    @router.delete(f"/me/person/{name}/{{row_id}}", name=f"me_delete_{name}")
    async def _del(row_id: uuid.UUID, user: IdentityUser = Depends(get_mnp_session_user),
                   session: AsyncSession = Depends(get_session)):
        try:
            person = await _my_person(session, user)
            return serialize_person(await service.delete_row(session, person.id, name, row_id))
        except Exception as exc:  # noqa: BLE001
            _err(exc)


for _c in _COLLECTIONS:
    _mount_user_collection(_c)


@router.post("/me/person/skills")
async def me_add_skill(payload: dict = Body(...), user: IdentityUser = Depends(get_mnp_session_user),
                       session: AsyncSession = Depends(get_session)):
    try:
        person = await _my_person(session, user, create=True)
        return serialize_person(await service.add_skill(
            session, person.id, source=PersonSource.USER_MANUAL,
            **{k: payload.get(k) for k in ("canonical_skill_id", "raw_input", "proficiency",
                                           "years_used", "last_used_year", "notes")}))
    except Exception as exc:  # noqa: BLE001
        _err(exc)


@router.delete("/me/person/skills/{row_id}")
async def me_delete_skill(row_id: uuid.UUID, user: IdentityUser = Depends(get_mnp_session_user),
                          session: AsyncSession = Depends(get_session)):
    try:
        person = await _my_person(session, user)
        return serialize_person(await service.delete_skill(session, person.id, row_id))
    except Exception as exc:  # noqa: BLE001
        _err(exc)


@router.post("/me/person/activate")
async def me_activate(user: IdentityUser = Depends(get_mnp_session_user),
                      session: AsyncSession = Depends(get_session)):
    try:
        person = await _my_person(session, user)
        return serialize_person(await service.activate_person(session, person.id))
    except Exception as exc:  # noqa: BLE001
        _err(exc)


# ===========================================================================
# CV INTAKE (own profile)
# ===========================================================================
@router.post("/me/person/cv")
async def me_cv_upload(file: UploadFile = File(...), user: IdentityUser = Depends(get_mnp_session_user),
                       session: AsyncSession = Depends(get_session)):
    _check_upload_rate_limit(str(user.id))
    content = await file.read()
    if len(content) > 15 * 1024 * 1024:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Файл завеликий (максимум 15 МБ)")
    person = await _my_person(session, user, create=True)
    try:
        candidates = await cv_intake.extract_candidates(
            session, person.id, filename=file.filename or "resume", content=content,
            mime_type=file.content_type)
    except cv_intake.CvParseError as exc:
        return {"parsed": False, "message": str(exc),
                "document_id": str(exc.document_id) if exc.document_id else None,
                "fallback": "Не вдалося повністю розпізнати резюме. Ви можете заповнити профіль вручну."}
    return {"parsed": True, "candidates": candidates}


@router.post("/me/person/cv/confirm")
async def me_cv_confirm(payload: dict = Body(...), user: IdentityUser = Depends(get_mnp_session_user),
                        session: AsyncSession = Depends(get_session)):
    person = await _my_person(session, user, create=True)
    try:
        await cv_intake.apply_confirmed(session, person.id, payload.get("confirmed", {}),
                                        document_id=payload.get("document_id"))
    except Exception as exc:  # noqa: BLE001
        _err(exc)
    return serialize_person(await service.get_person(session, person.id))
