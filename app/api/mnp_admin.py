"""MNP Career KB Editor -- admin-only write API.

Every route here requires a valid admin bearer token (`get_current_admin`,
the existing dashboard JWT -- no second auth stack). There is NO public /
anonymous write path into the Career KB. All DB work goes through
`app.services.career_kb_mnp.editor` (service layer), never inline here.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.db.models import AdminUser
from app.db.models_career_kb_mnp import CareerLifecycleStatus, MnpCareer
from app.db.session import get_session
from app.services.career_kb_mnp import editor
from app.services.career_kb_mnp.editor import CareerKbValidationError
from app.services.exceptions import (
    MnpCareerNotFoundError,
    MnpDuplicateCareerCodeError,
    MnpInvalidLifecycleTransitionError,
)

router = APIRouter(prefix="/v1/mnp/admin", tags=["mnp-admin"])


# --- error mapping -----------------------------------------------------------
def _handle(exc: Exception):
    if isinstance(exc, MnpCareerNotFoundError):
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    if isinstance(exc, MnpDuplicateCareerCodeError):
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))
    if isinstance(exc, (CareerKbValidationError, MnpInvalidLifecycleTransitionError, ValueError)):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    raise exc


def _kw(payload: dict[str, Any], *allowed: str) -> dict[str, Any]:
    """Pass only the keys the caller actually sent -> service `_UNSET`
    defaults leave everything else untouched."""
    return {k: payload[k] for k in allowed if k in payload}


async def _career(session: AsyncSession, career_id: uuid.UUID) -> MnpCareer:
    try:
        return await editor.get_career_or_404(session, career_id)
    except MnpCareerNotFoundError as exc:
        _handle(exc)


# ===========================================================================
# whoami / catalog
# ===========================================================================
@router.get("/me")
async def whoami(admin: AdminUser = Depends(get_current_admin)):
    return {"id": admin.id, "email": admin.email, "role": admin.role.value}


@router.get("/careers")
async def admin_list_careers(
    admin: AdminUser = Depends(get_current_admin), session: AsyncSession = Depends(get_session),
):
    """Every career in every status (public catalog only shows ACTIVE)."""
    rows = (await session.execute(select(MnpCareer))).scalars().all()
    for c in rows:
        await session.refresh(c, ["career_family"])
    rows.sort(key=lambda c: (c.status.value != "active", c.canonical_name_uk))
    return [{
        "id": str(c.id), "code": c.code, "name_uk": c.canonical_name_uk,
        "category_uk": c.career_family.name_uk if c.career_family else None,
        "status": c.status.value, "profile_version": c.career_profile_version,
    } for c in rows]


@router.get("/careers/{career_id}")
async def admin_get_career(
    career_id: uuid.UUID, admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    career = await _career(session, career_id)
    return await editor.get_career_editor_view(session, career)


@router.get("/careers/{career_id}/history")
async def admin_career_history(
    career_id: uuid.UUID, admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    career = await _career(session, career_id)
    return {"history": await editor.get_career_history(session, career)}


# ===========================================================================
# Career core / lifecycle
# ===========================================================================
@router.post("/careers", status_code=status.HTTP_201_CREATED)
async def admin_create_career(
    payload: dict = Body(...), admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    try:
        career = await editor.create_career_draft(
            session, actor_admin_id=admin.id,
            code=payload["career_code"], name_uk=payload["name_uk"],
            category_uk=payload.get("category_uk", "Інше"),
            **_kw(payload, "name_en", "short_description_uk", "long_description_uk",
                  "difficulty_level", "entry_without_experience", "typical_entry_route_uk"),
        )
    except KeyError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"missing field: {exc}")
    except Exception as exc:
        _handle(exc)
    return await editor.get_career_editor_view(session, career)


@router.patch("/careers/{career_id}")
async def admin_update_career_core(
    career_id: uuid.UUID, payload: dict = Body(...), admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    career = await _career(session, career_id)
    try:
        await editor.update_career_core(
            session, career, actor_admin_id=admin.id,
            **_kw(payload, "name_uk", "name_en", "category_uk", "short_description_uk",
                  "long_description_uk", "difficulty_level", "entry_without_experience",
                  "typical_entry_route_uk"),
        )
    except Exception as exc:
        _handle(exc)
    return await editor.get_career_editor_view(session, career)


@router.get("/careers/{career_id}/publish-readiness")
async def admin_publish_readiness(
    career_id: uuid.UUID, admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    career = await _career(session, career_id)
    missing = await editor.check_publish_readiness(session, career)
    return {"ready": not missing, "missing": missing}


@router.post("/careers/{career_id}/publish")
async def admin_publish(
    career_id: uuid.UUID, admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    career = await _career(session, career_id)
    try:
        await editor.publish_career(session, career, actor_admin_id=admin.id)
    except Exception as exc:
        _handle(exc)
    return {"id": str(career.id), "status": career.status.value}


@router.post("/careers/{career_id}/archive")
async def admin_archive(
    career_id: uuid.UUID, admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    career = await _career(session, career_id)
    try:
        await editor.archive_career(session, career, actor_admin_id=admin.id)
    except Exception as exc:
        _handle(exc)
    return {"id": str(career.id), "status": career.status.value}


@router.post("/careers/{career_id}/unarchive")
async def admin_unarchive(
    career_id: uuid.UUID, admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    career = await _career(session, career_id)
    try:
        await editor.unarchive_career(session, career, actor_admin_id=admin.id)
    except Exception as exc:
        _handle(exc)
    return {"id": str(career.id), "status": career.status.value}


# ===========================================================================
# generic child-collection routes
# ===========================================================================
def _mount_collection(name: str, *, create_fn, update_fn, delete_fn, create_keys, update_keys,
                      reorder_fn=None):
    base = f"/careers/{{career_id}}/{name}"

    @router.post(base, name=f"admin_add_{name}")
    async def _add(career_id: uuid.UUID, payload: dict = Body(...),
                   admin: AdminUser = Depends(get_current_admin),
                   session: AsyncSession = Depends(get_session)):
        career = await _career(session, career_id)
        try:
            await create_fn(session, career, actor_admin_id=admin.id, **_kw(payload, *create_keys))
        except Exception as exc:
            _handle(exc)
        return await editor.get_career_editor_view(session, career)

    @router.patch(base + "/{row_id}", name=f"admin_update_{name}")
    async def _update(career_id: uuid.UUID, row_id: uuid.UUID, payload: dict = Body(...),
                      admin: AdminUser = Depends(get_current_admin),
                      session: AsyncSession = Depends(get_session)):
        career = await _career(session, career_id)
        try:
            await update_fn(session, career, row_id, actor_admin_id=admin.id, **_kw(payload, *update_keys))
        except Exception as exc:
            _handle(exc)
        return await editor.get_career_editor_view(session, career)

    @router.delete(base + "/{row_id}", name=f"admin_delete_{name}")
    async def _delete(career_id: uuid.UUID, row_id: uuid.UUID,
                      admin: AdminUser = Depends(get_current_admin),
                      session: AsyncSession = Depends(get_session)):
        career = await _career(session, career_id)
        try:
            await delete_fn(session, career, row_id, actor_admin_id=admin.id)
        except Exception as exc:
            _handle(exc)
        return await editor.get_career_editor_view(session, career)

    if reorder_fn is not None:
        @router.post(base + "/{row_id}/move", name=f"admin_move_{name}")
        async def _move(career_id: uuid.UUID, row_id: uuid.UUID, payload: dict = Body(...),
                        admin: AdminUser = Depends(get_current_admin),
                        session: AsyncSession = Depends(get_session)):
            career = await _career(session, career_id)
            try:
                await reorder_fn(session, career, row_id, actor_admin_id=admin.id,
                                 direction=payload.get("direction", "up"))
            except Exception as exc:
                _handle(exc)
            return await editor.get_career_editor_view(session, career)


_SRC = ("source_type", "source_reference", "review_status")

_mount_collection(
    "responsibilities",
    create_fn=editor.add_responsibility, update_fn=editor.update_responsibility,
    delete_fn=editor.delete_responsibility, reorder_fn=editor.reorder_responsibility,
    create_keys=("title_uk", "description_uk", "importance", "frequency", *_SRC),
    update_keys=("title_uk", "description_uk", "importance", "frequency", *_SRC),
)
_mount_collection(
    "skills",
    create_fn=editor.attach_skill, update_fn=editor.update_skill_requirement,
    delete_fn=editor.detach_skill,
    create_keys=("skill_id", "importance", "required_level", "requirement_type", *_SRC),
    update_keys=("importance", "required_level", "requirement_type", *_SRC),
)
_mount_collection(
    "knowledge",
    create_fn=editor.attach_knowledge, update_fn=editor.update_knowledge_requirement,
    delete_fn=editor.detach_knowledge,
    create_keys=("knowledge_id", "importance", "required_level", "requirement_type", *_SRC),
    update_keys=("importance", "required_level", "requirement_type", *_SRC),
)
_mount_collection(
    "requirements",
    create_fn=editor.add_requirement, update_fn=editor.update_requirement,
    delete_fn=editor.delete_requirement,
    create_keys=("category", "description_uk", "value", "hardness", "country", *_SRC),
    update_keys=("category", "description_uk", "value", "hardness", "country", *_SRC),
)
_mount_collection(
    "career-path",
    create_fn=editor.add_path_step, update_fn=editor.update_path_step,
    delete_fn=editor.delete_path_step, reorder_fn=editor.reorder_path_step,
    create_keys=("step_name_uk", "step_type", "description_uk", "typical_experience_text_uk",
                 "is_current_career_step", "path_code", *_SRC),
    update_keys=("step_name_uk", "step_type", "description_uk", "typical_experience_text_uk",
                 "is_current_career_step", *_SRC),
)
_mount_collection(
    "pros-cons",
    create_fn=editor.add_procon, update_fn=editor.update_procon,
    delete_fn=editor.delete_procon, reorder_fn=editor.reorder_procon,
    create_keys=("type", "text_uk", *_SRC),
    update_keys=("type", "text_uk", *_SRC),
)
_mount_collection(
    "relations",
    create_fn=editor.add_relation, update_fn=editor.update_relation,
    delete_fn=editor.delete_relation,
    create_keys=("to_career_id", "relation_type", "strength", *_SRC),
    update_keys=("relation_type", "strength", *_SRC),
)
_mount_collection(
    "external-references",
    create_fn=editor.add_external_ref, update_fn=editor.update_external_ref,
    delete_fn=editor.delete_external_ref,
    create_keys=("external_system", "external_id", "external_label", "mapping_type",
                 "confidence", "source_reference", "review_status", "note"),
    update_keys=("external_label", "mapping_type", "confidence", "source_reference",
                 "review_status", "note"),
)


# ===========================================================================
# skill / knowledge lookup + creation
# ===========================================================================
@router.get("/skills/search")
async def admin_search_skills(
    q: str = Query(""), admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    rows = await editor.search_skills(session, q)
    return [{"id": str(s.id), "name_uk": s.canonical_name_uk, "name_en": s.canonical_name_en,
             "skill_type": s.skill_type.value,
             "is_soft": s.skill_type.value in ("communication", "management")} for s in rows]


@router.post("/skills", status_code=status.HTTP_201_CREATED)
async def admin_create_skill(
    payload: dict = Body(...), admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    try:
        s = await editor.create_canonical_skill(
            session, actor_admin_id=admin.id, name_uk=payload["name_uk"], name_en=payload["name_en"],
            skill_type=payload["skill_type"], description=payload.get("description"),
        )
    except KeyError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"missing field: {exc}")
    except Exception as exc:
        _handle(exc)
    return {"id": str(s.id), "name_uk": s.canonical_name_uk, "name_en": s.canonical_name_en,
            "skill_type": s.skill_type.value}


@router.get("/knowledge/search")
async def admin_search_knowledge(
    q: str = Query(""), admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    rows = await editor.search_knowledge(session, q)
    return [{"id": str(k.id), "name_uk": k.canonical_name_uk, "name_en": k.canonical_name_en} for k in rows]


@router.post("/knowledge", status_code=status.HTTP_201_CREATED)
async def admin_create_knowledge(
    payload: dict = Body(...), admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    try:
        k = await editor.create_knowledge(
            session, actor_admin_id=admin.id, name_uk=payload["name_uk"], name_en=payload["name_en"])
    except KeyError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"missing field: {exc}")
    except Exception as exc:
        _handle(exc)
    return {"id": str(k.id), "name_uk": k.canonical_name_uk, "name_en": k.canonical_name_en}
