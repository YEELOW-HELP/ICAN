from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timedelta, timezone
from io import BytesIO
from typing import Any
from urllib.parse import quote
from zipfile import BadZipFile, ZipFile

from fastapi import APIRouter, Body, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pymongo.errors import DuplicateKeyError

from app.core.config import settings
from app.mongo_runtime.auth import staff_view
from app.mongo_runtime import ai_recommendations, cv_analysis, dropbox_storage
from app.mongo_runtime.core import (
    ADMIN, MANAGER, SUPER_ADMIN, Database, current_person_session, current_staff,
    new_id, new_web_session, now, privileged_staff,
)

router = APIRouter(prefix="/v1/mnp")
logger = logging.getLogger(__name__)

STATUS_UK = {"case": "КЕЙС", "draft": "Чернетка", "active": "Активний", "archived": "В архіві"}
WORKFLOW_STAGE_UK = {
    "new_request": "Нова заявка",
    "needs_contact": "Потрібно зв’язатися",
    "in_contact": "В контакті",
    "consultation_scheduled": "Консультація запланована",
    "consultation_completed": "Консультація проведена",
    "in_progress": "У роботі",
    "employed": "Працевлаштований",
    "closed": "Закритий",
}
CLOSURE_REASON_UK = {
    "no_response": "Не відповідає",
    "refused": "Відмовився",
    "not_relevant": "Неактуально",
    "other": "Інше",
}


def _validate_person_status(value: Any) -> str:
    if not isinstance(value, str) or value not in STATUS_UK:
        raise HTTPException(422, "Оберіть статус: КЕЙС, Чернетка, Активний або В архіві")
    return value


def _validate_workflow_stage(value: Any) -> str:
    if not isinstance(value, str) or value not in WORKFLOW_STAGE_UK:
        raise HTTPException(422, "Оберіть коректний етап роботи з клієнтом")
    return value


def _workflow_stage(person: dict) -> str:
    """Give older records a useful stage until they are explicitly updated."""
    current = person.get("workflow_stage")
    if current in WORKFLOW_STAGE_UK:
        return current
    if person.get("status") == "archived":
        return "closed"
    if person.get("needs_contact"):
        return "needs_contact"
    if person.get("status") == "active":
        return "in_progress"
    return "new_request"


SOURCE_UK = {"self_service": "Самостійно", "consultant": "Консультант", "imported": "Імпорт"}
REFERRAL_SOURCES = {"instagram", "telegram", "workshop", "phone", "work_ua", "recommendation", "other"}
DEFAULT_CLIENT_REQUEST_TYPES = (
    "Пошук роботи", "Зміна професії", "Дистанційна робота",
    "Підробіток / швидкий заробіток", "Допомога з резюме",
    "Підготовка до співбесіди", "Професійна орієнтація", "Навчання",
    "Працевлаштування за кордоном",
)
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
    "country", "date_of_birth", "notes", "referral_source", "referral_details",
}
MOBILITY_FIELDS = {
    "has_driver_license", "driver_license_categories", "has_car", "willing_to_relocate",
    "work_geography", "work_format",
}
MIN_SEARCH_TAGS = 5
EMPLOYMENT_OFFER_MAX_LENGTH = 5000
NEXT_ACTION_MAX_LENGTH = 500
CLOSURE_NOTE_MAX_LENGTH = 500


def _require_super_admin(staff: dict) -> None:
    if staff.get("role") != SUPER_ADMIN:
        raise HTTPException(403, "AI-рекомендації доступні лише суперадміністратору")


def _norm_label(value: Any) -> str:
    return " ".join(str(value or "").casefold().split())


def _clean(data: dict[str, Any], allowed: set[str]) -> dict[str, Any]:
    return {key: value for key, value in data.items() if key in allowed}


def _normalize_phone(value: Any) -> tuple[str | None, str | None]:
    """Return a readable international number and digits used for matching."""
    if value is None or value == "":
        return None, None
    if not isinstance(value, str):
        raise HTTPException(422, "Телефон має бути текстом")
    raw = value.strip()
    if not raw:
        return None, None
    if re.search(r"[A-Za-zА-Яа-яІіЇїЄє]", raw):
        raise HTTPException(422, "Перевірте номер телефону")
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("00"):
        digits = digits[2:]
    if len(digits) == 9:
        digits = "380" + digits
    elif len(digits) == 10 and digits.startswith("0"):
        digits = "38" + digits
    elif len(digits) == 11 and digits.startswith("80"):
        digits = "3" + digits
    if not 8 <= len(digits) <= 15:
        raise HTTPException(422, "Перевірте номер телефону")
    return "+" + digits, digits


def _normalize_email(value: Any) -> tuple[str | None, str | None]:
    if value is None or value == "":
        return None, None
    if not isinstance(value, str):
        raise HTTPException(422, "Email має бути текстом")
    email = value.strip().lower()
    if not email:
        return None, None
    if "@" not in email or len(email) > 255:
        raise HTTPException(422, "Перевірте email")
    return email, email


def _prepare_contacts(changes: dict) -> None:
    if "phone" in changes:
        changes["phone"], changes["phone_normalized"] = _normalize_phone(changes["phone"])
    if "email" in changes:
        changes["email"], changes["email_normalized"] = _normalize_email(changes["email"])


def _validate_referral(changes: dict, current: dict | None = None) -> None:
    if not {"referral_source", "referral_details"}.intersection(changes):
        return
    current = current or {}
    source = changes.get("referral_source", current.get("referral_source"))
    if source == "":
        source = None
    if source is not None and (not isinstance(source, str) or source not in REFERRAL_SOURCES):
        raise HTTPException(422, "Оберіть джерело знайомства зі списку")
    details = changes.get("referral_details", current.get("referral_details"))
    if details is not None and (not isinstance(details, str) or len(details) > 300):
        raise HTTPException(422, "Уточнення джерела має бути текстом до 300 символів")
    details = (details or "").strip()
    if source == "other" and not details:
        raise HTTPException(422, "Уточніть, звідки клієнт дізнався про нас")
    changes["referral_source"] = source
    changes["referral_details"] = details if source == "other" else None


def _stage_name(payload: dict) -> tuple[str, str]:
    if set(payload) != {"name"} or not isinstance(payload.get("name"), str):
        raise HTTPException(422, "Вкажіть назву етапу")
    name = " ".join(payload["name"].split())
    if not name or len(name) > 80:
        raise HTTPException(422, "Назва етапу має містити від 1 до 80 символів")
    return name, name.casefold()


def _request_type_name(payload: dict) -> tuple[str, str]:
    if set(payload) != {"name"} or not isinstance(payload.get("name"), str):
        raise HTTPException(422, "Вкажіть назву запиту")
    name = " ".join(payload["name"].split())
    if not name or len(name) > 100:
        raise HTTPException(422, "Назва запиту має містити від 1 до 100 символів")
    return name, name.casefold()


def _employment_stage_view(row: dict) -> dict:
    return {"id": str(row["_id"]), "name": row["name"],
            "is_active": bool(row.get("is_active", True))}


def _request_type_view(row: dict) -> dict:
    return {"id": str(row["_id"]), "name": row["name"],
            "is_active": bool(row.get("is_active", True))}


def _next_action_at(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise HTTPException(422, "Дата наступної дії має бути датою і часом")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(422, "Перевірте дату наступної дії") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _view_fact(row: dict) -> dict:
    result = {key: value for key, value in row.items() if key not in {"_id", "person_id", "storage_ref"}}
    result["id"] = str(row["_id"])
    return result


async def _person_view(db, person: dict) -> dict:
    fresh = await db.mnp_persons.find_one({"_id": person["_id"]})
    if fresh:
        person = fresh
    person_id = str(person["_id"])
    facts: dict[str, list] = {}
    for public_name, collection in FACTS.items():
        facts[public_name] = [_view_fact(row) async for row in db[collection].find({"person_id": person_id})]
    documents = [_view_fact(row) async for row in db.mnp_person_documents.find({"person_id": person_id})]
    status = person.get("status", "draft")
    source = person.get("source", "consultant")
    employment_stage = None
    if person.get("employment_stage_id"):
        employment_stage = await db.mnp_employment_stages.find_one(
            {"_id": person["employment_stage_id"]}
        )
    responsible = None
    if person.get("responsible_staff_id") is not None:
        responsible_row = await db.admin_users.find_one({"_id": person["responsible_staff_id"]})
        if responsible_row:
            responsible = staff_view(responsible_row)
    request_labels = person.get("client_request_labels") or {}
    client_requests = []
    for request_id in person.get("client_request_ids") or []:
        row = await db.mnp_client_request_types.find_one({"_id": request_id})
        name = row.get("name") if row else request_labels.get(request_id)
        if name:
            client_requests.append({
                "id": request_id, "name": name,
                "is_active": bool(row.get("is_active", True)) if row else False,
            })
    workflow_stage = _workflow_stage(person)
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
        "employment": {
            "stage_id": person.get("employment_stage_id"),
            "stage_name": employment_stage.get("name") if employment_stage else person.get("employment_stage_name"),
            "stage_active": bool(employment_stage.get("is_active", True)) if employment_stage else None,
            "offer_text": person.get("employment_offer_text"),
        },
        "workflow": {
            "stage": workflow_stage,
            "stage_uk": WORKFLOW_STAGE_UK[workflow_stage],
            "closure_reason": person.get("closure_reason"),
            "closure_reason_uk": CLOSURE_REASON_UK.get(person.get("closure_reason")),
            "closure_note": person.get("closure_note"),
            "client_requests": client_requests,
            "responsible": responsible,
            "needs_contact": bool(person.get("needs_contact", False)),
            "next_action_text": person.get("next_action_text"),
            "next_action_at": person.get("next_action_at"),
        },
        **facts,
        "tags": person.get("tags", []),
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
    _prepare_contacts(changes)
    changes["updated_at"] = now()
    current = await db.mnp_persons.find_one({"identity_user_id": session["user_id"]})
    _validate_referral(changes, current)
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


def _validated_cv(file: UploadFile, content: bytes) -> tuple[str, str]:
    filename = (file.filename or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not filename or len(filename) > 255 or "." not in filename:
        raise HTTPException(422, "Некоректна назва CV")
    extension = filename.rsplit(".", 1)[-1].lower()
    if extension not in {"pdf", "doc", "docx"}:
        raise HTTPException(422, "Підтримуються PDF, DOC і DOCX")
    if not content:
        raise HTTPException(422, "Файл порожній")
    if extension == "pdf" and not content.startswith(b"%PDF-"):
        raise HTTPException(422, "Файл не схожий на PDF")
    if extension == "doc" and not content.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        raise HTTPException(422, "Файл не схожий на DOC")
    if extension == "docx":
        try:
            with ZipFile(BytesIO(content)) as archive:
                if "word/document.xml" not in archive.namelist():
                    raise HTTPException(422, "Файл не схожий на DOCX")
        except BadZipFile as exc:
            raise HTTPException(422, "Файл не схожий на DOCX") from exc
    return filename, extension


@router.post("/admin/persons/{person_id}/documents/cv", status_code=201)
async def admin_upload_cv(person_id: str, file: UploadFile = File(...), db: Database = None,
                          staff=Depends(current_staff)):
    # Check object-level access before reading the file or contacting Dropbox.
    person = await _staff_person(db, person_id, staff)
    content = await file.read(settings.max_upload_size_mb * 1024 * 1024 + 1)
    if len(content) > settings.max_upload_size_mb * 1024 * 1024:
        raise HTTPException(413, f"Файл завеликий (максимум {settings.max_upload_size_mb} МБ)")
    filename, extension = _validated_cv(file, content)
    document_id = new_id()
    try:
        file_id = await dropbox_storage.upload_cv(
            document_id=document_id, person_id=str(person["_id"]),
            extension=extension, content=content,
        )
    except dropbox_storage.DropboxStorageError as exc:
        raise HTTPException(503, str(exc)) from exc
    try:
        await db.mnp_person_documents.insert_one({
            "_id": document_id, "person_id": str(person["_id"]), "document_type": "cv",
            "filename": filename, "mime_type": file.content_type, "file_size": len(content),
            "sha256": hashlib.sha256(content).hexdigest(), "storage_provider": "dropbox",
            "storage_ref": file_id, "uploaded_by_staff_id": staff["_id"], "created_at": now(),
        })
    except Exception:
        try:
            await dropbox_storage.delete_cv(file_id)
        except dropbox_storage.DropboxStorageError:
            logger.error("Dropbox CV rollback failed for document %s", document_id)
        raise
    await db.mnp_persons.update_one({"_id": person["_id"]}, {"$set": {"updated_at": now()}})
    return await _person_view(db, await db.mnp_persons.find_one({"_id": person["_id"]}))


@router.get("/admin/persons/{person_id}/documents/{document_id}/download")
async def admin_download_document(person_id: str, document_id: str, db: Database,
                                  staff=Depends(current_staff)):
    person = await _staff_person(db, person_id, staff)
    document = await db.mnp_person_documents.find_one({
        "_id": document_id, "person_id": str(person["_id"]),
    })
    if not document:
        raise HTTPException(404, "Документ не знайдено")
    content = await _document_bytes(db, document)
    filename = str(document.get("filename") or "cv.pdf").replace("\\", "/").rsplit("/", 1)[-1]
    extension = filename.rsplit(".", 1)[-1].lower()
    media_type = {"pdf": "application/pdf", "doc": "application/msword",
                  "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}.get(
                      extension, "application/octet-stream")
    return Response(content=content, media_type=media_type, headers={
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
    })


async def _document_bytes(db, document: dict) -> bytes:
    if document.get("storage_provider") == "dropbox":
        try:
            return await dropbox_storage.download_cv(document["storage_ref"])
        except dropbox_storage.DropboxStorageError as exc:
            raise HTTPException(503, str(exc)) from exc
    blob = await db.mnp_file_blobs.find_one({"_id": document["_id"]})
    if not blob:
        raise HTTPException(404, "Файл документа не знайдено")
    return blob["content"]


def _require_ai_permission(payload: dict) -> None:
    if not settings.cv_analysis_enabled:
        raise HTTPException(503, "AI-аналіз вимкнено на сервері")
    if payload.get("permission_confirmed") is not True:
        raise HTTPException(422, "Підтвердіть дозвіл на AI-обробку даних клієнта")


async def _check_analysis_quota(db, person_id: str) -> None:
    query = {"person_id": person_id, "analyzed_at": {"$gte": now() - timedelta(days=1)}}
    recent = await db.mnp_ai_analysis_events.count_documents(query)
    if recent >= settings.cv_analysis_daily_limit:
        raise HTTPException(429, "Денний ліміт AI-аналізу для цього клієнта вичерпано")


async def _sync_person_tags(db, person_id: str) -> list[dict]:
    """Materialize canonical search tags directly on the person document."""
    skill_ids = []
    seen = set()
    async for row in db[FACTS["skills"]].find({"person_id": person_id}):
        skill_id = str(row.get("canonical_skill_id") or "")
        if skill_id and skill_id not in seen:
            seen.add(skill_id)
            skill_ids.append(skill_id)
    tags = []
    for skill_id in skill_ids:
        skill = await db.mnp_skills.find_one({"_id": skill_id})
        if not skill or skill.get("status") == "archived":
            continue
        tags.append({
            "skill_id": skill_id,
            "name": skill.get("canonical_name_uk") or skill.get("canonical_name_en") or skill_id,
            "skill_type": skill.get("skill_type"),
        })
    tags.sort(key=lambda item: str(item["name"]).casefold())
    await db.mnp_persons.update_one(
        {"_id": person_id}, {"$set": {"tags": tags, "updated_at": now()}},
    )
    return tags


async def _career_requirement_tags(db, *, proposal: dict,
                                   known_skill_ids: set[str]) -> tuple[dict | None, list[dict]]:
    """Choose the closest catalog career and return its strongest canonical skills.

    Role names/aliases are the primary signal. Existing evidence-backed skills are
    only a deterministic tie-breaker. Nothing outside the canonical taxonomy is
    ever returned.
    """
    careers = [row async for row in db.mnp_careers.find()
               if row.get("status") != "archived"]
    if not careers:
        return None, []
    names: dict[str, set[str]] = {str(row["_id"]): set() for row in careers}
    for row in careers:
        career_id = str(row["_id"])
        for value in (row.get("canonical_name_uk"), row.get("canonical_name_en")):
            if _norm_label(value):
                names[career_id].add(_norm_label(value))
    async for row in db.mnp_career_aliases.find():
        career_id = str(row.get("career_id") or "")
        if career_id in names and row.get("status") != "archived" and _norm_label(row.get("alias")):
            names[career_id].add(_norm_label(row["alias"]))

    relations: dict[str, list[dict]] = {str(row["_id"]): [] for row in careers}
    async for row in db.mnp_career_skill_requirements.find():
        career_id = str(row.get("career_id") or "")
        if (career_id in relations and row.get("status") != "archived"
                and row.get("review_status") != "rejected"):
            relations[career_id].append(row)

    roles = [_norm_label(proposal.get("primary_role"))]
    roles.extend(_norm_label(value) for value in proposal.get("alternative_roles") or [])
    roles = [value for value in roles if value]
    importance = {"critical": 4, "high": 3, "medium": 2, "low": 1}

    def role_score(career_id: str) -> float:
        best = 0.0
        for role_index, role in enumerate(roles):
            role_tokens = set(role.split())
            for label in names[career_id]:
                if role == label:
                    best = max(best, 1000 - role_index * 20)
                    continue
                if len(role) >= 5 and len(label) >= 5 and (role in label or label in role):
                    best = max(best, 700 - role_index * 20)
                    continue
                label_tokens = set(label.split())
                overlap = len(role_tokens & label_tokens) / max(len(role_tokens | label_tokens), 1)
                if overlap >= .5:
                    best = max(best, 400 * overlap - role_index * 10)
        return best

    ranked = []
    for career in careers:
        career_id = str(career["_id"])
        overlap_score = sum(
            importance.get(str(row.get("importance") or "medium"), 2)
            for row in relations[career_id]
            if str(row.get("skill_id") or "") in known_skill_ids
        )
        title_score = role_score(career_id)
        if title_score or overlap_score:
            ranked.append((title_score, overlap_score,
                           _norm_label(career.get("canonical_name_uk")), career))
    if not ranked:
        return None, []
    ranked.sort(key=lambda item: (-item[0], -item[1], item[2]))
    career = ranked[0][3]
    career_id = str(career["_id"])
    requirement_rank = {"must_have": 0, "high_value": 1, "differentiator": 2, "optional": 3}
    ordered = sorted(relations[career_id], key=lambda row: (
        -importance.get(str(row.get("importance") or "medium"), 2),
        requirement_rank.get(str(row.get("requirement_type") or "high_value"), 4),
        -float(row.get("confidence") or 0), str(row.get("skill_id") or ""),
    ))
    candidates = []
    for relation in ordered:
        skill_id = str(relation.get("skill_id") or "")
        if not skill_id or skill_id in known_skill_ids:
            continue
        skill = await db.mnp_skills.find_one({"_id": skill_id})
        if skill and skill.get("status") != "archived":
            candidates.append({"skill": skill, "relation": relation})
    return career, candidates


async def _assign_analysis_tags(db, *, person_id: str, proposal: dict,
                                source: str, source_id: str) -> dict:
    """Save only existing taxonomy skills as unconfirmed, evidence-linked facts."""
    current = [row async for row in db[FACTS["skills"]].find({"person_id": person_id})]
    existing = {str(row["canonical_skill_id"]) for row in current
                if row.get("canonical_skill_id")}
    existing_names = {" ".join(str(row.get("raw_input") or "").casefold().split())
                      for row in current}
    matched = []
    seen = set()
    added = 0
    for suggestion in proposal.get("skills") or []:
        skill_id = suggestion.get("canonical_skill_id")
        evidence = str(suggestion.get("evidence") or "").strip()
        if not skill_id or not evidence:
            continue
        skill = await db.mnp_skills.find_one({"_id": skill_id})
        if not skill or skill.get("status") == "archived":
            continue
        if str(skill_id) in seen:
            continue
        seen.add(str(skill_id))
        name = skill.get("canonical_name_uk") or skill.get("canonical_name_en") or suggestion["name"]
        matched.append({"id": str(skill_id), "name": name})
        if (str(skill_id) in existing
                or " ".join(str(name).casefold().split()) in existing_names
                or " ".join(str(suggestion["name"]).casefold().split()) in existing_names):
            continue
        await db[FACTS["skills"]].insert_one({
            "_id": new_id(), "person_id": person_id,
            "canonical_skill_id": skill_id, "raw_input": suggestion["name"],
            "custom_status": "canonical", "proficiency": None,
            "evidence_state": "system_detected", "source": f"ai_{source}_analysis",
            "analysis_source_id": source_id, "evidence_excerpt": evidence,
            "supporting_document_id": source_id if source == "cv" else None,
            "created_at": now(), "updated_at": now(),
        })
        existing.add(str(skill_id))
        added += 1
    inferred = []
    person_tags = await _sync_person_tags(db, person_id)
    career = None
    if len(person_tags) < MIN_SEARCH_TAGS:
        career, candidates = await _career_requirement_tags(
            db, proposal=proposal,
            known_skill_ids={str(tag["skill_id"]) for tag in person_tags},
        )
        for candidate in candidates:
            if len(person_tags) + len(inferred) >= MIN_SEARCH_TAGS:
                break
            skill = candidate["skill"]
            skill_id = str(skill["_id"])
            name = skill.get("canonical_name_uk") or skill.get("canonical_name_en") or skill_id
            career_name = (career.get("canonical_name_uk") or career.get("canonical_name_en")
                           or proposal.get("primary_role") or "")
            await db[FACTS["skills"]].insert_one({
                "_id": new_id(), "person_id": person_id,
                "canonical_skill_id": skill_id, "raw_input": name,
                "custom_status": "canonical", "proficiency": None,
                "evidence_state": "system_inferred", "source": f"ai_{source}_analysis",
                "analysis_source_id": source_id,
                "evidence_excerpt": f"Вимога професії «{career_name}»",
                "inferred_from_career_id": str(career["_id"]),
                "supporting_document_id": source_id if source == "cv" else None,
                "created_at": now(), "updated_at": now(),
            })
            inferred.append({"id": skill_id, "name": name})
            added += 1
        if inferred:
            person_tags = await _sync_person_tags(db, person_id)
    return {
        "detected_tags": matched,
        "inferred_tags": inferred,
        "new_tags_count": added,
        "person_tags": person_tags,
        "tagging": {
            "minimum": MIN_SEARCH_TAGS,
            "total": len(person_tags),
            "complete": len(person_tags) >= MIN_SEARCH_TAGS,
            "career": ({"id": str(career["_id"]),
                        "name": career.get("canonical_name_uk") or career.get("canonical_name_en")}
                       if career else None),
        },
    }


@router.post("/admin/persons/{person_id}/documents/{document_id}/analyze")
async def admin_analyze_cv(person_id: str, document_id: str, payload: dict = Body(...), db: Database = None,
                           staff=Depends(current_staff)):
    person = await _staff_person(db, person_id, staff)
    _require_ai_permission(payload)
    document = await db.mnp_person_documents.find_one({
        "_id": document_id, "person_id": str(person["_id"]), "document_type": "cv",
    })
    if not document:
        raise HTTPException(404, "CV не знайдено")
    cached = await db.mnp_cv_analyses.find_one({"_id": document_id})
    if (cached and cached.get("sha256") == document.get("sha256")
            and cached.get("prompt_version") == cv_analysis.PROMPT_VERSION
            and cached.get("model") == settings.openai_model):
        tags = await _assign_analysis_tags(db, person_id=person_id, proposal=cached["proposal"],
                                           source="cv", source_id=document_id)
        return {"cached": True, **tags, **{key: cached[key] for key in (
            "document_id", "proposal", "model", "prompt_version", "input_tokens", "output_tokens")}}
    await _check_analysis_quota(db, str(person["_id"]))
    content = await _document_bytes(db, document)
    try:
        proposal, trace = await cv_analysis.analyze_cv(
            db, content=content, filename=document["filename"])
    except cv_analysis.CvAnalysisError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
    record = {"_id": document_id, "document_id": document_id,
              "person_id": str(person["_id"]), "sha256": document.get("sha256"),
              "proposal": proposal.model_dump(), "model": settings.openai_model,
              "prompt_version": cv_analysis.PROMPT_VERSION,
              "input_tokens": trace.input_tokens, "output_tokens": trace.output_tokens,
              "trace_id": trace.trace_id, "analyzed_at": now(),
              "permission_confirmed_by_staff_id": staff["_id"]}
    await db.mnp_ai_analysis_events.insert_one({
        "_id": new_id(), "person_id": str(person["_id"]), "source": "cv",
        "source_id": document_id, "analyzed_at": record["analyzed_at"],
        "staff_id": staff["_id"], "input_tokens": trace.input_tokens,
        "output_tokens": trace.output_tokens,
    })
    await db.mnp_cv_analyses.replace_one({"_id": document_id}, record, upsert=True)
    tags = await _assign_analysis_tags(db, person_id=person_id, proposal=record["proposal"],
                                       source="cv", source_id=document_id)
    return {"cached": False, **tags, **{key: record[key] for key in (
        "document_id", "proposal", "model", "prompt_version", "input_tokens", "output_tokens")}}


@router.post("/admin/persons/{person_id}/analysis/questionnaire")
async def admin_analyze_questionnaire(person_id: str, payload: dict = Body(...),
                                      db: Database = None, staff=Depends(current_staff)):
    person = await _staff_person(db, person_id, staff)
    _require_ai_permission(payload)
    profile = await _person_view(db, person)
    try:
        excerpt = await cv_analysis.questionnaire_excerpt(db, profile)
    except cv_analysis.CvAnalysisError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
    profile_hash = hashlib.sha256(excerpt.encode("utf-8")).hexdigest()
    cached = await db.mnp_questionnaire_analyses.find_one({"_id": person_id})
    if (cached and cached.get("profile_hash") == profile_hash
            and cached.get("prompt_version") == cv_analysis.QUESTIONNAIRE_PROMPT_VERSION
            and cached.get("model") == settings.openai_model):
        tags = await _assign_analysis_tags(db, person_id=person_id, proposal=cached["proposal"],
                                           source="questionnaire", source_id=person_id)
        return {"cached": True, **tags, **{key: cached[key] for key in (
            "proposal", "model", "prompt_version", "input_tokens", "output_tokens")}}
    await _check_analysis_quota(db, person_id)
    try:
        proposal, trace = await cv_analysis.analyze_questionnaire(db, excerpt=excerpt)
    except cv_analysis.CvAnalysisError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
    record = {"_id": person_id, "person_id": person_id, "profile_hash": profile_hash,
              "proposal": proposal.model_dump(), "model": settings.openai_model,
              "prompt_version": cv_analysis.QUESTIONNAIRE_PROMPT_VERSION,
              "input_tokens": trace.input_tokens, "output_tokens": trace.output_tokens,
              "trace_id": trace.trace_id, "analyzed_at": now(),
              "permission_confirmed_by_staff_id": staff["_id"]}
    await db.mnp_ai_analysis_events.insert_one({
        "_id": new_id(), "person_id": person_id, "source": "questionnaire",
        "source_id": person_id, "analyzed_at": record["analyzed_at"],
        "staff_id": staff["_id"], "input_tokens": trace.input_tokens,
        "output_tokens": trace.output_tokens,
    })
    await db.mnp_questionnaire_analyses.replace_one({"_id": person_id}, record, upsert=True)
    tags = await _assign_analysis_tags(db, person_id=person_id, proposal=record["proposal"],
                                       source="questionnaire", source_id=person_id)
    return {"cached": False, **tags, **{key: record[key] for key in (
        "proposal", "model", "prompt_version", "input_tokens", "output_tokens")}}


def _ai_recommendation_view(record: dict, person: dict) -> dict:
    generated_for = record.get("profile_updated_at")
    current_updated_at = person.get("updated_at")
    return {
        "recommendation": record["recommendation"],
        "generated_at": record.get("generated_at"),
        "profile_updated_at": generated_for,
        "is_outdated": bool(
            record.get("prompt_version") != ai_recommendations.PROMPT_VERSION
            or (generated_for and current_updated_at and current_updated_at > generated_for)
        ),
        "vacancy_search": record.get("vacancy_search"),
        "model": record.get("model"),
        "input_tokens": record.get("input_tokens", 0),
        "output_tokens": record.get("output_tokens", 0),
    }


@router.get("/admin/persons/{person_id}/ai-recommendations")
async def get_ai_recommendations(person_id: str, db: Database,
                                 staff=Depends(current_staff)):
    _require_super_admin(staff)
    person = await _staff_person(db, person_id, staff)
    record = await db.mnp_superadmin_recommendations.find_one({"_id": person_id})
    if not record:
        return {"recommendation": None}
    return _ai_recommendation_view(record, person)


@router.post("/admin/persons/{person_id}/ai-recommendations")
async def generate_ai_recommendations(person_id: str, db: Database,
                                      staff=Depends(current_staff)):
    _require_super_admin(staff)
    if not settings.cv_analysis_enabled:
        raise HTTPException(503, "AI-аналіз вимкнено на сервері")
    person = await _staff_person(db, person_id, staff)
    await _check_analysis_quota(db, person_id)
    profile = await _person_view(db, person)
    career_matches = await ai_recommendations.catalog_career_matches(db, profile)
    profile["catalog_career_matches"] = career_matches
    try:
        plan, trace = await ai_recommendations.generate(profile)
    except ai_recommendations.RecommendationError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
    generated_at = now()
    record = {
        "_id": person_id,
        "person_id": person_id,
        "recommendation": plan.model_dump(),
        "vacancy_search": ai_recommendations.vacancy_search(profile, career_matches),
        "model": settings.openai_model,
        "prompt_version": ai_recommendations.PROMPT_VERSION,
        "input_tokens": trace.input_tokens,
        "output_tokens": trace.output_tokens,
        "trace_id": trace.trace_id,
        "generated_at": generated_at,
        "profile_updated_at": person.get("updated_at") or generated_at,
        "generated_by_staff_id": staff["_id"],
    }
    await db.mnp_ai_analysis_events.insert_one({
        "_id": new_id(), "person_id": person_id,
        "source": "superadmin_recommendations", "source_id": person_id,
        "analyzed_at": generated_at, "staff_id": staff["_id"],
        "input_tokens": trace.input_tokens, "output_tokens": trace.output_tokens,
    })
    await db.mnp_superadmin_recommendations.replace_one(
        {"_id": person_id}, record, upsert=True,
    )
    return _ai_recommendation_view(record, person)


@router.get("/admin/persons")
async def list_persons(db: Database, staff=Depends(current_staff)):
    rows = []
    async for person in db.mnp_persons.find(_scope(staff)).sort("updated_at", -1):
        status = person.get("status", "draft")
        responsible = None
        if person.get("responsible_staff_id") is not None:
            row = await db.admin_users.find_one({"_id": person["responsible_staff_id"]})
            if row:
                responsible = staff_view(row)
        rows.append({
            "id": str(person["_id"]),
            "name": " ".join(x for x in (person.get("first_name"), person.get("last_name")) if x),
            "phone": person.get("phone"), "email": person.get("email"),
            "telegram_username": person.get("telegram_username"), "city": person.get("city"),
            "status": status, "status_uk": STATUS_UK.get(status, status),
            "source": person.get("source"),
            "created_at": person.get("created_at"), "updated_at": person.get("updated_at"),
            "responsible": responsible,
            "workflow_stage": _workflow_stage(person),
            "workflow_stage_uk": WORKFLOW_STAGE_UK[_workflow_stage(person)],
            "workflow_closure_reason_uk": CLOSURE_REASON_UK.get(person.get("closure_reason")),
            "needs_contact": bool(person.get("needs_contact", False)),
            "has_next_action": bool(person.get("next_action_text") and person.get("next_action_at")),
            "next_action_text": person.get("next_action_text"),
            "next_action_at": person.get("next_action_at"),
        })
    return rows


@router.post("/admin/persons", status_code=201)
async def create_person(payload: dict = Body(...), db: Database = None,
                        staff=Depends(current_staff)):
    values = _clean(payload, CORE_FIELDS | MOBILITY_FIELDS)
    _prepare_contacts(values)
    _validate_referral(values)
    if not str(values.get("first_name") or "").strip():
        raise HTTPException(422, "Вкажіть ім’я")
    status = _validate_person_status(payload.get("status", "case"))
    person_id = new_id()
    person = {"_id": person_id, **values, "status": status, "source": "consultant",
              "profile_version": 1, "created_at": now(), "updated_at": now(),
              "access_admin_ids": [staff["_id"]], "responsible_staff_id": staff["_id"],
              "workflow_stage": "new_request", "needs_contact": True,
              "client_request_ids": [], "client_request_labels": {}}
    await db.mnp_persons.insert_one(person)
    await db.mnp_person_access.insert_one({"_id": f"{person_id}:{staff['_id']}",
                                           "person_id": person_id, "admin_id": staff["_id"],
                                           "is_creator": True, "granted_by": staff["_id"],
                                           "created_at": now()})
    return await _person_view(db, person)


@router.get("/admin/persons/duplicates")
async def find_person_duplicates(phone: str | None = None, email: str | None = None,
                                 exclude_person_id: str | None = None, db: Database = None,
                                 staff=Depends(current_staff)):
    _, phone_key = _normalize_phone(phone)
    _, email_key = _normalize_email(email)
    if not phone_key and not email_key:
        return []
    matches = []
    async for person in db.mnp_persons.find({}):
        person_id = str(person["_id"])
        if person_id == exclude_person_id:
            continue
        stored_phone = person.get("phone_normalized")
        if not stored_phone and person.get("phone"):
            try:
                _, stored_phone = _normalize_phone(person.get("phone"))
            except HTTPException:
                stored_phone = None
        stored_email = person.get("email_normalized") or str(person.get("email") or "").strip().lower()
        reasons = []
        if phone_key and stored_phone == phone_key:
            reasons.append("phone")
        if email_key and stored_email == email_key:
            reasons.append("email")
        if not reasons:
            continue
        has_access = staff["role"] in (SUPER_ADMIN, ADMIN) or staff["_id"] in person.get("access_admin_ids", [])
        visible_name = " ".join(x for x in (person.get("first_name"), person.get("last_name")) if x) or "Клієнт"
        matches.append({
            "id": person_id if has_access else None,
            "name": visible_name if has_access else "Інший клієнт у базі",
            "phone": person.get("phone") if has_access else None,
            "email": person.get("email") if has_access else None,
            "match_reasons": reasons, "has_access": has_access,
        })
        if len(matches) >= 5:
            break
    return matches


@router.get("/admin/consultants")
async def list_consultants(db: Database, _staff=Depends(current_staff)):
    rows = [staff_view(row) async for row in db.admin_users.find({"is_active": {"$ne": False}})]
    return sorted(rows, key=lambda row: ((row.get("full_name") or row["email"]).casefold(), row["id"]))


@router.get("/admin/persons/{person_id}")
async def get_person(person_id: str, db: Database, staff=Depends(current_staff)):
    return await _person_view(db, await _staff_person(db, person_id, staff))


@router.patch("/admin/persons/{person_id}")
async def update_person(person_id: str, payload: dict = Body(...), db: Database = None,
                        staff=Depends(current_staff)):
    current = await _staff_person(db, person_id, staff)
    changes = _clean(payload, CORE_FIELDS | MOBILITY_FIELDS | {"status"})
    _prepare_contacts(changes)
    _validate_referral(changes, current)
    if "status" in changes:
        if staff.get("role") != SUPER_ADMIN:
            raise HTTPException(403, "Змінювати статус клієнта може лише суперадміністратор")
        changes["status"] = _validate_person_status(changes["status"])
        changes["status_updated_by_staff_id"] = staff["_id"]
        changes["status_updated_at"] = now()
    changes["updated_at"] = now()
    await db.mnp_persons.update_one({"_id": person_id}, {"$set": changes})
    return await _person_view(db, await db.mnp_persons.find_one({"_id": person_id}))


@router.get("/admin/employment-stages")
async def list_employment_stages(db: Database, staff=Depends(current_staff)):
    query = {} if staff["role"] in (SUPER_ADMIN, ADMIN) else {"is_active": {"$ne": False}}
    rows = [_employment_stage_view(row) async for row in db.mnp_employment_stages.find(query)]
    return sorted(rows, key=lambda row: (not row["is_active"], row["name"].casefold()))


@router.post("/admin/employment-stages", status_code=201)
async def create_employment_stage(payload: dict = Body(...), db: Database = None,
                                  staff=Depends(privileged_staff)):
    name, normalized_name = _stage_name(payload)
    row = {"_id": new_id(), "name": name, "normalized_name": normalized_name,
           "is_active": True, "created_by": staff["_id"],
           "created_at": now(), "updated_at": now()}
    try:
        await db.mnp_employment_stages.insert_one(row)
    except DuplicateKeyError as exc:
        raise HTTPException(409, "Такий етап уже існує") from exc
    return _employment_stage_view(row)


@router.patch("/admin/employment-stages/{stage_id}")
async def update_employment_stage(stage_id: str, payload: dict = Body(...), db: Database = None,
                                  staff=Depends(privileged_staff)):
    current = await db.mnp_employment_stages.find_one({"_id": stage_id})
    if not current:
        raise HTTPException(404, "Етап не знайдено")
    name, normalized_name = _stage_name(payload)
    try:
        await db.mnp_employment_stages.update_one(
            {"_id": stage_id}, {"$set": {"name": name, "normalized_name": normalized_name,
                                            "updated_by": staff["_id"], "updated_at": now()}}
        )
    except DuplicateKeyError as exc:
        raise HTTPException(409, "Такий етап уже існує") from exc
    return _employment_stage_view(await db.mnp_employment_stages.find_one({"_id": stage_id}))


@router.delete("/admin/employment-stages/{stage_id}")
async def delete_employment_stage(stage_id: str, db: Database,
                                  staff=Depends(privileged_staff)):
    current = await db.mnp_employment_stages.find_one({"_id": stage_id})
    if not current:
        raise HTTPException(404, "Етап не знайдено")
    used = await db.mnp_persons.count_documents({"employment_stage_id": stage_id})
    if used:
        await db.mnp_employment_stages.update_one(
            {"_id": stage_id}, {"$set": {"is_active": False,
                                            "archived_by": staff["_id"], "updated_at": now()}}
        )
        return {"archived": True, "used_by": used}
    await db.mnp_employment_stages.delete_one({"_id": stage_id})
    return {"archived": False, "used_by": 0}


@router.patch("/admin/persons/{person_id}/employment")
async def update_person_employment(person_id: str, payload: dict = Body(...), db: Database = None,
                                   staff=Depends(current_staff)):
    await _staff_person(db, person_id, staff)
    if not isinstance(payload, dict) or not set(payload).issubset({"stage_id", "offer_text"}) or not payload:
        raise HTTPException(422, "Передайте етап або пропозицію")
    changes: dict[str, Any] = {}
    if "stage_id" in payload:
        raw_stage_id = payload["stage_id"]
        stage_id = None if raw_stage_id is None or raw_stage_id == "" else raw_stage_id
        if stage_id is not None and not isinstance(stage_id, str):
            raise HTTPException(422, "Оберіть етап зі списку")
        stage = await db.mnp_employment_stages.find_one({"_id": stage_id}) if stage_id else None
        if stage_id and (not stage or stage.get("is_active") is False):
            raise HTTPException(422, "Цей етап більше недоступний для вибору")
        changes["employment_stage_id"] = stage_id
        changes["employment_stage_name"] = stage.get("name") if stage else None
    if "offer_text" in payload:
        offer = payload["offer_text"]
        if offer is not None and not isinstance(offer, str):
            raise HTTPException(422, "Пропозиція має бути текстом")
        offer = (offer or "").strip()
        if len(offer) > EMPLOYMENT_OFFER_MAX_LENGTH:
            raise HTTPException(422, f"Пропозиція має містити до {EMPLOYMENT_OFFER_MAX_LENGTH} символів")
        changes["employment_offer_text"] = offer or None
    changes["updated_at"] = now()
    await db.mnp_persons.update_one({"_id": person_id}, {"$set": changes})
    return await _person_view(db, await db.mnp_persons.find_one({"_id": person_id}))


@router.get("/admin/client-request-types")
async def list_client_request_types(db: Database, staff=Depends(current_staff)):
    query = {} if staff["role"] in (SUPER_ADMIN, ADMIN) else {"is_active": {"$ne": False}}
    rows = [_request_type_view(row) async for row in db.mnp_client_request_types.find(query)]
    return sorted(rows, key=lambda row: (not row["is_active"], row["name"].casefold()))


@router.post("/admin/client-request-types", status_code=201)
async def create_client_request_type(payload: dict = Body(...), db: Database = None,
                                     staff=Depends(privileged_staff)):
    name, normalized_name = _request_type_name(payload)
    row = {"_id": new_id(), "name": name, "normalized_name": normalized_name,
           "is_active": True, "created_by": staff["_id"],
           "created_at": now(), "updated_at": now()}
    try:
        await db.mnp_client_request_types.insert_one(row)
    except DuplicateKeyError as exc:
        raise HTTPException(409, "Такий запит уже існує") from exc
    return _request_type_view(row)


@router.patch("/admin/client-request-types/{request_type_id}")
async def update_client_request_type(request_type_id: str, payload: dict = Body(...),
                                     db: Database = None, staff=Depends(privileged_staff)):
    current = await db.mnp_client_request_types.find_one({"_id": request_type_id})
    if not current:
        raise HTTPException(404, "Запит не знайдено")
    name, normalized_name = _request_type_name(payload)
    try:
        await db.mnp_client_request_types.update_one(
            {"_id": request_type_id},
            {"$set": {"name": name, "normalized_name": normalized_name,
                      "updated_by": staff["_id"], "updated_at": now()}},
        )
    except DuplicateKeyError as exc:
        raise HTTPException(409, "Такий запит уже існує") from exc
    return _request_type_view(await db.mnp_client_request_types.find_one({"_id": request_type_id}))


@router.delete("/admin/client-request-types/{request_type_id}")
async def delete_client_request_type(request_type_id: str, db: Database,
                                     staff=Depends(privileged_staff)):
    current = await db.mnp_client_request_types.find_one({"_id": request_type_id})
    if not current:
        raise HTTPException(404, "Запит не знайдено")
    used = await db.mnp_persons.count_documents({"client_request_ids": request_type_id})
    if used:
        await db.mnp_client_request_types.update_one(
            {"_id": request_type_id},
            {"$set": {"is_active": False, "archived_by": staff["_id"], "updated_at": now()}},
        )
        return {"archived": True, "used_by": used}
    await db.mnp_client_request_types.delete_one({"_id": request_type_id})
    return {"archived": False, "used_by": 0}


@router.patch("/admin/persons/{person_id}/workflow")
async def update_person_workflow(person_id: str, payload: dict = Body(...), db: Database = None,
                                 staff=Depends(current_staff)):
    person = await _staff_person(db, person_id, staff)
    allowed = {"client_request_ids", "responsible_staff_id", "workflow_stage",
               "closure_reason", "closure_note", "needs_contact",
               "next_action_text", "next_action_at", "notes"}
    if not isinstance(payload, dict) or not payload or not set(payload).issubset(allowed):
        raise HTTPException(422, "Передайте дані супроводу клієнта")
    changes: dict[str, Any] = {}

    target_stage = _workflow_stage(person)
    if "workflow_stage" in payload:
        target_stage = _validate_workflow_stage(payload["workflow_stage"])
        changes["workflow_stage"] = target_stage
        if target_stage == "needs_contact":
            changes["needs_contact"] = True
        elif target_stage not in ("new_request",):
            changes["needs_contact"] = False

    if ("workflow_stage" in payload or "closure_reason" in payload
            or "closure_note" in payload):
        closure_reason = payload.get("closure_reason", person.get("closure_reason"))
        closure_note = payload.get("closure_note", person.get("closure_note"))
        if closure_note is not None and not isinstance(closure_note, str):
            raise HTTPException(422, "Уточнення причини закриття має бути текстом")
        closure_note = (closure_note or "").strip()
        if len(closure_note) > CLOSURE_NOTE_MAX_LENGTH:
            raise HTTPException(422, f"Уточнення має містити до {CLOSURE_NOTE_MAX_LENGTH} символів")
        if target_stage == "closed":
            if closure_reason not in CLOSURE_REASON_UK:
                raise HTTPException(422, "Оберіть причину закриття клієнта")
            if closure_reason == "other" and not closure_note:
                raise HTTPException(422, "Уточніть іншу причину закриття")
            changes["closure_reason"] = closure_reason
            changes["closure_note"] = closure_note or None
        else:
            changes["closure_reason"] = None
            changes["closure_note"] = None

    if "client_request_ids" in payload:
        request_ids = payload["client_request_ids"]
        if (not isinstance(request_ids, list) or len(request_ids) > 20
                or any(not isinstance(value, str) or not value for value in request_ids)
                or len(set(request_ids)) != len(request_ids)):
            raise HTTPException(422, "Оберіть до 20 запитів клієнта зі списку")
        current_ids = set(person.get("client_request_ids") or [])
        labels = {}
        for request_id in request_ids:
            row = await db.mnp_client_request_types.find_one({"_id": request_id})
            if not row or (row.get("is_active") is False and request_id not in current_ids):
                raise HTTPException(422, "Один із запитів більше недоступний для вибору")
            labels[request_id] = row["name"]
        changes["client_request_ids"] = request_ids
        changes["client_request_labels"] = labels

    if "responsible_staff_id" in payload:
        responsible_id = payload["responsible_staff_id"]
        if responsible_id == "":
            responsible_id = None
        if responsible_id is not None and (isinstance(responsible_id, bool) or not isinstance(responsible_id, int)):
            raise HTTPException(422, "Оберіть відповідального консультанта зі списку")
        if staff["role"] == MANAGER:
            current_id = person.get("responsible_staff_id")
            if responsible_id not in (None, staff["_id"]) or (responsible_id is None and current_id not in (None, staff["_id"])):
                raise HTTPException(403, "Менеджер може призначити відповідальним лише себе")
        responsible = None
        if responsible_id is not None:
            responsible = await db.admin_users.find_one({"_id": responsible_id})
            if (not responsible or (responsible.get("is_active") is False
                                    and responsible_id != person.get("responsible_staff_id"))):
                raise HTTPException(422, "Цей працівник більше недоступний")
        changes["responsible_staff_id"] = responsible_id
        if responsible and responsible.get("role") == MANAGER:
            await db.mnp_person_access.update_one(
                {"_id": f"{person_id}:{responsible_id}"},
                {"$setOnInsert": {"person_id": person_id, "admin_id": responsible_id,
                                  "is_creator": False, "granted_by": staff["_id"],
                                  "created_at": now()}}, upsert=True,
            )
            await db.mnp_persons.update_one(
                {"_id": person_id}, {"$addToSet": {"access_admin_ids": responsible_id}},
            )

    if "needs_contact" in payload:
        if not isinstance(payload["needs_contact"], bool):
            raise HTTPException(422, "Ознака контакту має бути так або ні")
        changes["needs_contact"] = payload["needs_contact"]

    if "notes" in payload:
        notes = payload["notes"]
        if notes is not None and (not isinstance(notes, str) or len(notes) > 10000):
            raise HTTPException(422, "Нотатки мають містити до 10000 символів")
        changes["notes"] = (notes or "").strip() or None

    action_text = payload.get("next_action_text", person.get("next_action_text"))
    action_at = (_next_action_at(payload["next_action_at"])
                 if "next_action_at" in payload else person.get("next_action_at"))
    if action_text is not None and not isinstance(action_text, str):
        raise HTTPException(422, "Наступна дія має бути текстом")
    action_text = (action_text or "").strip()
    if len(action_text) > NEXT_ACTION_MAX_LENGTH:
        raise HTTPException(422, f"Наступна дія має містити до {NEXT_ACTION_MAX_LENGTH} символів")
    if bool(action_text) != bool(action_at):
        raise HTTPException(422, "Для наступної дії вкажіть і опис, і дату")
    if "next_action_text" in payload or "next_action_at" in payload:
        changes["next_action_text"] = action_text or None
        changes["next_action_at"] = action_at

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
        if fact_type == "skills":
            await _sync_person_tags(db, str(person["_id"]))
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
        if fact_type == "skills":
            await _sync_person_tags(db, str(person["_id"]))
        return await _person_view(db, person)

    async def remove(person_id: str, fact_type: str, fact_id: str, db, actor):
        if fact_type not in FACTS:
            raise HTTPException(404, "Невідомий розділ")
        person = await _fact_owner(db, person_id, actor if staff_mode else None, None if staff_mode else actor)
        result = await db[FACTS[fact_type]].delete_one({"_id": fact_id, "person_id": str(person["_id"])})
        if not result.deleted_count:
            raise HTTPException(404, "Запис не знайдено")
        if fact_type == "skills":
            await _sync_person_tags(db, str(person["_id"]))
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
    if fact_type == "skills":
        await _sync_person_tags(db, person_id)
    return await _person_view(db, person)


@router.patch("/admin/persons/{person_id}/{fact_type}/{fact_id}")
async def admin_edit_fact(person_id: str, fact_type: str, fact_id: str, payload: dict = Body(...),
                          db: Database = None, staff=Depends(current_staff)):
    if fact_type not in FACTS: raise HTTPException(404, "Невідомий розділ")
    person = await _staff_person(db, person_id, staff)
    result = await db[FACTS[fact_type]].update_one({"_id": fact_id, "person_id": person_id},
                                                   {"$set": {**payload, "updated_at": now()}})
    if not result.matched_count: raise HTTPException(404, "Запис не знайдено")
    if fact_type == "skills":
        await _sync_person_tags(db, person_id)
    return await _person_view(db, person)


@router.delete("/admin/persons/{person_id}/{fact_type}/{fact_id}")
async def admin_delete_fact(person_id: str, fact_type: str, fact_id: str, db: Database,
                            staff=Depends(current_staff)):
    person = await _staff_person(db, person_id, staff)
    if fact_type not in FACTS: raise HTTPException(404, "Невідомий розділ")
    await db[FACTS[fact_type]].delete_one({"_id": fact_id, "person_id": person_id})
    if fact_type == "skills":
        await _sync_person_tags(db, person_id)
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
