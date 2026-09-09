from __future__ import annotations

import hashlib
from typing import Any

from fastapi import APIRouter, Body, Depends, File, HTTPException, UploadFile

from app.core.config import settings
from app.mongo_runtime.auth import staff_view
from app.mongo_runtime.core import (
    ADMIN, MANAGER, SUPER_ADMIN, Database, current_person_session, current_staff,
    new_id, new_web_session, now, privileged_staff,
)

router = APIRouter(prefix="/v1/mnp")

STATUS_UK = {"draft": "Чернетка", "active": "Активний", "archived": "В архіві"}
SOURCE_UK = {"self_service": "Самостійно", "consultant": "Консультант", "imported": "Імпорт"}
FACTS = {
    "educations": "mnp_person_educations",
    "credentials": "mnp_person_credentials",
    "experiences": "mnp_person_experiences",
    "activities": "mnp_person_activities",
    "skills": "mnp_person_skills_v1",
    "languages": "mnp_person_languages_v1",
}
CORE_FIELDS = {
    "first_name", "last_name", "phone", "email", "telegram_username", "city", "region",
    "country", "date_of_birth", "notes",
}
MOBILITY_FIELDS = {
    "has_driver_license", "driver_license_categories", "has_car", "willing_to_relocate",
    "work_geography", "work_format",
}


def _clean(data: dict[str, Any], allowed: set[str]) -> dict[str, Any]:
    return {key: value for key, value in data.items() if key in allowed}


def _view_fact(row: dict) -> dict:
    result = {key: value for key, value in row.items() if key not in {"_id", "person_id", "storage_ref"}}
    result["id"] = str(row["_id"])
    return result


async def _person_view(db, person: dict) -> dict:
    person_id = str(person["_id"])
    facts: dict[str, list] = {}
    for public_name, collection in FACTS.items():
        facts[public_name] = [_view_fact(row) async for row in db[collection].find({"person_id": person_id})]
    documents = [_view_fact(row) async for row in db.mnp_person_documents.find({"person_id": person_id})]
    status = person.get("status", "draft")
    source = person.get("source", "consultant")
    return {
        "id": person_id,
        "identity_user_id": person.get("identity_user_id"),
        "core": {
            **{key: person.get(key) for key in CORE_FIELDS},
            "first_name": person.get("first_name") or "",
            "status": status, "status_uk": STATUS_UK.get(status, status),
            "source": source, "source_uk": SOURCE_UK.get(source, source),
            "profile_version": person.get("profile_version", 1),
        },
        "mobility": {key: person.get(key) for key in MOBILITY_FIELDS},
        **facts,
        "documents": documents,
        "created_at": person.get("created_at"), "updated_at": person.get("updated_at"),
    }


def _scope(staff: dict) -> dict:
    if staff["role"] in (SUPER_ADMIN, ADMIN):
        return {}
    return {"access_admin_ids": staff["_id"]}


async def _staff_person(db, person_id: str, staff: dict) -> dict:
    query = {"_id": person_id, **_scope(staff)}
    person = await db.mnp_persons.find_one(query)
    if not person:
        raise HTTPException(404, "Клієнта не знайдено або немає доступу")
    return person


async def _self_person(db, session: dict) -> dict:
    person = await db.mnp_persons.find_one({"identity_user_id": session["user_id"]})
    if not person:
        raise HTTPException(404, "Профіль ще не створено")
    return person


@router.post("/session", status_code=201)
async def create_session(db: Database):
    token, row = new_web_session()
    await db.mnp_web_sessions.insert_one(row)
    return {"user_id": row["user_id"], "session_token": token}


@router.get("/me/person")
async def get_self(db: Database, session=Depends(current_person_session)):
    return await _person_view(db, await _self_person(db, session))


@router.post("/me/person")
async def save_self(payload: dict = Body(...), db: Database = None,
                    session=Depends(current_person_session)):
    changes = _clean(payload, CORE_FIELDS | MOBILITY_FIELDS)
    changes["updated_at"] = now()
    current = await db.mnp_persons.find_one({"identity_user_id": session["user_id"]})
    if current:
        await db.mnp_persons.update_one({"_id": current["_id"]}, {"$set": changes})
        person = await db.mnp_persons.find_one({"_id": current["_id"]})
    else:
        if not str(changes.get("first_name") or "").strip():
            raise HTTPException(422, "Вкажіть ім’я")
        person = {"_id": new_id(), "identity_user_id": session["user_id"], **changes,
                  "status": "draft", "source": "self_service", "profile_version": 1,
                  "created_at": now(), "access_admin_ids": []}
        await db.mnp_persons.insert_one(person)
    return await _person_view(db, person)


@router.post("/me/person/activate")
async def activate_self(db: Database, session=Depends(current_person_session)):
    person = await _self_person(db, session)
    await db.mnp_persons.update_one({"_id": person["_id"]}, {"$set": {"status": "active", "updated_at": now()}})
    return await _person_view(db, await db.mnp_persons.find_one({"_id": person["_id"]}))


@router.post("/me/person/cv", status_code=201)
async def upload_cv(file: UploadFile = File(...), db: Database = None,
                    session=Depends(current_person_session)):
    person = await _self_person(db, session)
    content = await file.read(settings.max_upload_size_mb * 1024 * 1024 + 1)
    if len(content) > settings.max_upload_size_mb * 1024 * 1024:
        raise HTTPException(413, "Файл завеликий")
    extension = (file.filename or "").lower().rsplit(".", 1)[-1]
    if extension not in {"pdf", "doc", "docx"}:
        raise HTTPException(422, "Підтримуються PDF, DOC і DOCX")
    document_id = new_id()
    await db.mnp_person_documents.insert_one({
        "_id": document_id, "person_id": str(person["_id"]), "document_type": "cv",
        "filename": file.filename, "mime_type": file.content_type, "file_size": len(content),
        "sha256": hashlib.sha256(content).hexdigest(), "created_at": now(),
    })
    await db.mnp_file_blobs.insert_one({"_id": document_id, "content": content})
    return {"id": document_id, "filename": file.filename}


@router.get("/admin/persons")
async def list_persons(db: Database, staff=Depends(current_staff)):
    rows = []
    async for person in db.mnp_persons.find(_scope(staff)).sort("updated_at", -1):
        status = person.get("status", "draft")
        rows.append({
            "id": str(person["_id"]),
            "name": " ".join(x for x in (person.get("first_name"), person.get("last_name")) if x),
            "phone": person.get("phone"), "email": person.get("email"),
            "telegram_username": person.get("telegram_username"), "city": person.get("city"),
            "status": status, "status_uk": STATUS_UK.get(status, status),
            "source": person.get("source"), "updated_at": person.get("updated_at"),
        })
    return rows


@router.post("/admin/persons", status_code=201)
async def create_person(payload: dict = Body(...), db: Database = None,
                        staff=Depends(current_staff)):
    values = _clean(payload, CORE_FIELDS | MOBILITY_FIELDS)
    if not str(values.get("first_name") or "").strip():
        raise HTTPException(422, "Вкажіть ім’я")
    person_id = new_id()
    person = {"_id": person_id, **values, "status": "draft", "source": "consultant",
              "profile_version": 1, "created_at": now(), "updated_at": now(),
              "access_admin_ids": [staff["_id"]]}
    await db.mnp_persons.insert_one(person)
    await db.mnp_person_access.insert_one({"_id": f"{person_id}:{staff['_id']}",
                                           "person_id": person_id, "admin_id": staff["_id"],
                                           "is_creator": True, "granted_by": staff["_id"],
                                           "created_at": now()})
    return await _person_view(db, person)


@router.get("/admin/persons/{person_id}")
async def get_person(person_id: str, db: Database, staff=Depends(current_staff)):
    return await _person_view(db, await _staff_person(db, person_id, staff))


@router.patch("/admin/persons/{person_id}")
async def update_person(person_id: str, payload: dict = Body(...), db: Database = None,
                        staff=Depends(current_staff)):
    await _staff_person(db, person_id, staff)
    changes = _clean(payload, CORE_FIELDS | MOBILITY_FIELDS | {"status"})
    changes["updated_at"] = now()
    await db.mnp_persons.update_one({"_id": person_id}, {"$set": changes})
    return await _person_view(db, await db.mnp_persons.find_one({"_id": person_id}))


async def _fact_owner(db, person_id: str, staff: dict | None, session: dict | None) -> dict:
    return await _staff_person(db, person_id, staff) if staff else await _self_person(db, session)


def _fact_routes(prefix: str, staff_mode: bool) -> None:
    dependency = current_staff if staff_mode else current_person_session

    async def add(person_id: str, fact_type: str, payload: dict, db, actor):
        if fact_type not in FACTS:
            raise HTTPException(404, "Невідомий розділ")
        person = await _fact_owner(db, person_id, actor if staff_mode else None, None if staff_mode else actor)
        row = {"_id": new_id(), "person_id": str(person["_id"]), **payload,
               "created_at": now(), "updated_at": now()}
        await db[FACTS[fact_type]].insert_one(row)
        await db.mnp_persons.update_one({"_id": person["_id"]}, {"$set": {"updated_at": now()}})
        return await _person_view(db, await db.mnp_persons.find_one({"_id": person["_id"]}))

    async def edit(person_id: str, fact_type: str, fact_id: str, payload: dict, db, actor):
        if fact_type not in FACTS:
            raise HTTPException(404, "Невідомий розділ")
        person = await _fact_owner(db, person_id, actor if staff_mode else None, None if staff_mode else actor)
        result = await db[FACTS[fact_type]].update_one(
            {"_id": fact_id, "person_id": str(person["_id"])},
            {"$set": {**payload, "updated_at": now()}},
        )
        if not result.matched_count:
            raise HTTPException(404, "Запис не знайдено")
        return await _person_view(db, person)

    async def remove(person_id: str, fact_type: str, fact_id: str, db, actor):
        if fact_type not in FACTS:
            raise HTTPException(404, "Невідомий розділ")
        person = await _fact_owner(db, person_id, actor if staff_mode else None, None if staff_mode else actor)
        result = await db[FACTS[fact_type]].delete_one({"_id": fact_id, "person_id": str(person["_id"])})
        if not result.deleted_count:
            raise HTTPException(404, "Запис не знайдено")
        return await _person_view(db, person)

    router.add_api_route(prefix + "/{person_id}/{fact_type}", add, methods=["POST"], dependencies=[],
                         name=("admin" if staff_mode else "self") + "_add_fact")
    router.add_api_route(prefix + "/{person_id}/{fact_type}/{fact_id}", edit, methods=["PATCH"],
                         name=("admin" if staff_mode else "self") + "_edit_fact")
    router.add_api_route(prefix + "/{person_id}/{fact_type}/{fact_id}", remove, methods=["DELETE"],
                         name=("admin" if staff_mode else "self") + "_delete_fact")


# Admin fact routes match the React consultant workspace contract.
@router.post("/admin/persons/{person_id}/{fact_type}")
async def admin_add_fact(person_id: str, fact_type: str, payload: dict = Body(...), db: Database = None,
                         staff=Depends(current_staff)):
    if fact_type not in FACTS: raise HTTPException(404, "Невідомий розділ")
    person = await _staff_person(db, person_id, staff)
    await db[FACTS[fact_type]].insert_one({"_id": new_id(), "person_id": person_id, **payload,
                                           "created_at": now(), "updated_at": now()})
    return await _person_view(db, person)


@router.patch("/admin/persons/{person_id}/{fact_type}/{fact_id}")
async def admin_edit_fact(person_id: str, fact_type: str, fact_id: str, payload: dict = Body(...),
                          db: Database = None, staff=Depends(current_staff)):
    if fact_type not in FACTS: raise HTTPException(404, "Невідомий розділ")
    person = await _staff_person(db, person_id, staff)
    result = await db[FACTS[fact_type]].update_one({"_id": fact_id, "person_id": person_id},
                                                   {"$set": {**payload, "updated_at": now()}})
    if not result.matched_count: raise HTTPException(404, "Запис не знайдено")
    return await _person_view(db, person)


@router.delete("/admin/persons/{person_id}/{fact_type}/{fact_id}")
async def admin_delete_fact(person_id: str, fact_type: str, fact_id: str, db: Database,
                            staff=Depends(current_staff)):
    person = await _staff_person(db, person_id, staff)
    if fact_type not in FACTS: raise HTTPException(404, "Невідомий розділ")
    await db[FACTS[fact_type]].delete_one({"_id": fact_id, "person_id": person_id})
    return await _person_view(db, person)


@router.get("/admin/persons/{person_id}/access")
async def list_access(person_id: str, db: Database, actor=Depends(privileged_staff)):
    await _staff_person(db, person_id, actor)
    result = []
    async for grant in db.mnp_person_access.find({"person_id": person_id}):
        staff = await db.admin_users.find_one({"_id": grant["admin_id"]})
        if staff:
            result.append({**staff_view(staff), "is_creator": grant.get("is_creator", False)})
    return result


@router.put("/admin/persons/{person_id}/access/{staff_id}", status_code=204)
async def grant_access(person_id: str, staff_id: int, db: Database, actor=Depends(privileged_staff)):
    await _staff_person(db, person_id, actor)
    target = await db.admin_users.find_one({"_id": staff_id, "role": MANAGER, "is_active": True})
    if not target: raise HTTPException(404, "Менеджера не знайдено")
    await db.mnp_person_access.update_one({"_id": f"{person_id}:{staff_id}"}, {"$setOnInsert": {
        "person_id": person_id, "admin_id": staff_id, "is_creator": False,
        "granted_by": actor["_id"], "created_at": now()}}, upsert=True)
    await db.mnp_persons.update_one({"_id": person_id}, {"$addToSet": {"access_admin_ids": staff_id}})


@router.delete("/admin/persons/{person_id}/access/{staff_id}", status_code=204)
async def revoke_access(person_id: str, staff_id: int, db: Database, actor=Depends(privileged_staff)):
    grant = await db.mnp_person_access.find_one({"_id": f"{person_id}:{staff_id}"})
    if grant and grant.get("is_creator"): raise HTTPException(409, "Не можна забрати доступ у автора")
    await db.mnp_person_access.delete_one({"_id": f"{person_id}:{staff_id}"})
    await db.mnp_persons.update_one({"_id": person_id}, {"$pull": {"access_admin_ids": staff_id}})
