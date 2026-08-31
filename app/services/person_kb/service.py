"""Person KB CRUD -- the single write path for `MnpPerson` and its facts."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models_career_card import MnpSkill, SkillStatus
from app.db.models_person_kb import (
    CustomSkillStatus,
    MnpPerson,
    MnpPersonActivity,
    MnpPersonCredential,
    MnpPersonDocument,
    MnpPersonEducation,
    MnpPersonExperience,
    MnpPersonLanguageV1,
    MnpPersonSkillV1,
    PersonEvidenceState,
    PersonSource,
    PersonStatus,
    TriState,
    WorkFormat,
)
from app.db.models_platform import AuditLog
from app.services.career_kb_mnp.skills import normalize_phrase


class PersonKbError(Exception):
    """Bad input into the Person KB service."""


class PersonNotFoundError(PersonKbError):
    pass


_UNSET: object = object()


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- collection registry ----------------------------------------------
COLLECTIONS = {
    "educations": (MnpPersonEducation, (
        "education_level", "institution_name", "specialty_or_qualification", "start_year",
        "end_year", "status", "description", "supporting_document_id", "evidence_state")),
    "credentials": (MnpPersonCredential, (
        "credential_type", "title", "provider", "issue_date", "expiry_date", "credential_number",
        "description", "supporting_document_id", "evidence_state")),
    "experiences": (MnpPersonExperience, (
        "company_name", "raw_job_title", "canonical_career_id", "start_date", "end_date",
        "is_current", "responsibilities_description", "achievements", "tools_used", "industry",
        "employment_type", "supporting_document_id", "evidence_state")),
    "activities": (MnpPersonActivity, (
        "activity_type", "title", "organization", "role", "start_date", "end_date", "description",
        "result_or_achievement", "supporting_document_id", "evidence_state")),
    "languages": (MnpPersonLanguageV1, (
        "language", "level", "certificate", "supporting_document_id", "evidence_state")),
}

_DATE_FIELDS = {"issue_date", "expiry_date", "start_date", "end_date", "date_of_birth"}
_RAW_IMMUTABLE = {"raw_job_title"}  # never overwritten by a mapper -- editable only by the person/admin


_UUID_FIELDS = {"supporting_document_id", "canonical_career_id", "canonical_skill_id"}


def _uid(v) -> uuid.UUID | None:
    if v in (None, ""):
        return None
    return v if isinstance(v, uuid.UUID) else uuid.UUID(str(v))


def _coerce(field: str, value):
    if value in (None, ""):
        return None
    if field in _UUID_FIELDS:
        return _uid(value)
    if field in _DATE_FIELDS and isinstance(value, str):
        return date.fromisoformat(value)
    if field in ("start_year", "end_year", "last_used_year", "years_used") and isinstance(value, str):
        return int(value)
    return value


# --- person root -----------------------------------------------------
_PERSON_CORE = (
    "first_name", "last_name", "phone", "email", "telegram_username",
    "city", "region", "country", "date_of_birth", "notes",
)
_MOBILITY = (
    "has_driver_license", "driver_license_categories", "has_car",
    "willing_to_relocate", "work_geography", "work_format",
)


def _clean_telegram(v: str | None) -> str | None:
    if not v:
        return None
    v = v.strip()
    for pfx in ("https://t.me/", "http://t.me/", "t.me/", "@"):
        if v.lower().startswith(pfx):
            v = v[len(pfx):]
    return v.strip("/ ") or None


async def _audit(session: AsyncSession, *, actor_admin_id: int | None, person_id: uuid.UUID,
                 action: str, after: dict | None = None) -> None:
    session.add(AuditLog(
        actor_admin_id=actor_admin_id, entity_type="mnp_person", entity_id=str(person_id),
        action=action, after_snapshot={**(after or {}), "person_id": str(person_id), "kb": "person_kb_base_v1"}))


async def get_person(session: AsyncSession, person_id: uuid.UUID) -> MnpPerson:
    person = (await session.execute(
        select(MnpPerson).where(MnpPerson.id == person_id).options(
            selectinload(MnpPerson.educations), selectinload(MnpPerson.credentials),
            selectinload(MnpPerson.experiences), selectinload(MnpPerson.activities),
            selectinload(MnpPerson.skills), selectinload(MnpPerson.languages),
            selectinload(MnpPerson.documents))
        .execution_options(populate_existing=True))).scalar_one_or_none()
    if person is None:
        raise PersonNotFoundError(f"no MnpPerson {person_id}")
    return person


async def get_person_by_identity(session: AsyncSession, identity_user_id: uuid.UUID) -> MnpPerson | None:
    row = (await session.execute(
        select(MnpPerson).where(MnpPerson.identity_user_id == identity_user_id))).scalar_one_or_none()
    return await get_person(session, row.id) if row else None


async def list_persons(session: AsyncSession) -> list[MnpPerson]:
    rows = (await session.execute(select(MnpPerson).order_by(MnpPerson.updated_at.desc()))).scalars().all()
    return list(rows)


async def create_person(session: AsyncSession, *, first_name: str, source: PersonSource,
                        actor_admin_id: int | None = None, identity_user_id: uuid.UUID | None = None,
                        **fields) -> MnpPerson:
    first_name = (first_name or "").strip()
    if not first_name:
        raise PersonKbError("first_name is required")
    person = MnpPerson(first_name=first_name, source=source, status=PersonStatus.DRAFT,
                       identity_user_id=identity_user_id)
    for f in _PERSON_CORE:
        if f in fields and f != "first_name":
            setattr(person, f, _clean_telegram(fields[f]) if f == "telegram_username"
                    else _coerce(f, fields[f]))
    session.add(person)
    await session.flush()
    await _audit(session, actor_admin_id=actor_admin_id, person_id=person.id, action="person_created",
                 after={"source": source.value, "first_name": first_name})
    await session.commit()
    return await get_person(session, person.id)


async def update_person_core(session: AsyncSession, person_id: uuid.UUID, *, actor_admin_id: int | None = None,
                             **fields) -> MnpPerson:
    person = await get_person(session, person_id)
    changed = {}
    for f in _PERSON_CORE + _MOBILITY:
        if f not in fields:
            continue
        v = fields[f]
        if f == "telegram_username":
            v = _clean_telegram(v)
        elif f in ("has_driver_license", "has_car", "willing_to_relocate"):
            v = TriState(v) if v else TriState.UNKNOWN
        elif f == "work_format":
            v = WorkFormat(v) if v else WorkFormat.UNKNOWN
        elif f == "work_geography":
            v = list(v) if v else None
        else:
            v = _coerce(f, v)
        setattr(person, f, v)
        changed[f] = v.value if hasattr(v, "value") else v
    if changed:
        person.profile_version += 1
        await session.flush()
        await _audit(session, actor_admin_id=actor_admin_id, person_id=person.id,
                     action="person_core_updated", after={"fields": list(changed)})
    await session.commit()
    return await get_person(session, person.id)


async def set_status(session: AsyncSession, person_id: uuid.UUID, *, status: str,
                     actor_admin_id: int | None = None) -> MnpPerson:
    person = await get_person(session, person_id)
    target = PersonStatus(status)
    person.status = target
    person.archived_at = _now() if target == PersonStatus.ARCHIVED else None
    person.profile_version += 1
    await session.flush()
    await _audit(session, actor_admin_id=actor_admin_id, person_id=person.id,
                 action=f"person_status_{target.value}")
    await session.commit()
    return await get_person(session, person.id)


def activation_readiness(person: MnpPerson) -> list[str]:
    """V1 rule: a Person may be ACTIVE once it has a name and at least one
    substantive fact block. A partially filled DRAFT never auto-activates."""
    missing: list[str] = []
    if not person.first_name.strip():
        missing.append("ім'я")
    n_facts = (len(person.educations) + len(person.experiences) + len(person.activities)
               + len(person.skills) + len(person.languages))
    if n_facts == 0:
        missing.append("щонайменше один блок фактів (освіта / досвід / активність / навички / мови)")
    return missing


async def activate_person(session: AsyncSession, person_id: uuid.UUID, *,
                          actor_admin_id: int | None = None) -> MnpPerson:
    person = await get_person(session, person_id)
    missing = activation_readiness(person)
    if missing:
        raise PersonKbError("Не можна активувати профіль: бракує — " + "; ".join(missing))
    return await set_status(session, person_id, status="active", actor_admin_id=actor_admin_id)


# --- nested collections ---------------------------------------------
async def add_row(session: AsyncSession, person_id: uuid.UUID, collection: str, payload: dict, *,
                  actor_admin_id: int | None = None, source: PersonSource = PersonSource.USER_MANUAL) -> MnpPerson:
    person = await get_person(session, person_id)
    model, allowed = COLLECTIONS[collection]
    kw = {k: _coerce(k, payload[k]) for k in allowed if k in payload and payload[k] not in (None, "")}
    if collection == "experiences":
        if not (payload.get("raw_job_title") or "").strip():
            raise PersonKbError("raw_job_title is required for an experience")
        kw["is_current"] = TriState(payload["is_current"]) if payload.get("is_current") else TriState.UNKNOWN
    if collection == "activities" and not (payload.get("title") or "").strip():
        raise PersonKbError("title is required for an activity")
    if collection == "credentials" and not (payload.get("title") or "").strip():
        raise PersonKbError("title is required for a credential")
    if collection == "languages" and not (payload.get("language") or "").strip():
        raise PersonKbError("language is required")
    ev = kw.pop("evidence_state", None)
    row = model(person_id=person.id, source=source, **kw)
    if ev:
        row.evidence_state = PersonEvidenceState(ev)
    session.add(row)
    person.profile_version += 1
    await session.flush()
    await _audit(session, actor_admin_id=actor_admin_id, person_id=person.id,
                 action=f"{collection}_added", after={"row_id": str(row.id)})
    await session.commit()
    return await get_person(session, person.id)


async def update_row(session: AsyncSession, person_id: uuid.UUID, collection: str, row_id: uuid.UUID,
                     payload: dict, *, actor_admin_id: int | None = None,
                     source: PersonSource = PersonSource.USER_MANUAL) -> MnpPerson:
    person = await get_person(session, person_id)
    model, allowed = COLLECTIONS[collection]
    row = await session.get(model, _uid(row_id))
    if row is None or row.person_id != person.id:
        raise PersonNotFoundError(f"no {collection} row {row_id} for person {person_id}")
    for k in allowed:
        if k not in payload:
            continue
        if k in _RAW_IMMUTABLE and not payload.get(k):
            continue  # never blank out the raw fact
        if k == "evidence_state":
            row.evidence_state = PersonEvidenceState(payload[k]) if payload[k] else row.evidence_state
        elif k == "is_current":
            row.is_current = TriState(payload[k]) if payload[k] else TriState.UNKNOWN
        else:
            setattr(row, k, _coerce(k, payload[k]))
    row.source = source
    person.profile_version += 1
    await session.flush()
    await _audit(session, actor_admin_id=actor_admin_id, person_id=person.id,
                 action=f"{collection}_updated", after={"row_id": str(row_id)})
    await session.commit()
    return await get_person(session, person.id)


async def delete_row(session: AsyncSession, person_id: uuid.UUID, collection: str, row_id: uuid.UUID, *,
                     actor_admin_id: int | None = None) -> MnpPerson:
    person = await get_person(session, person_id)
    model, _ = COLLECTIONS[collection]
    row = await session.get(model, _uid(row_id))
    if row is None or row.person_id != person.id:
        raise PersonNotFoundError(f"no {collection} row {row_id}")
    await session.delete(row)
    person.profile_version += 1
    await session.flush()
    await _audit(session, actor_admin_id=actor_admin_id, person_id=person.id,
                 action=f"{collection}_deleted", after={"row_id": str(row_id)})
    await session.commit()
    return await get_person(session, person.id)


# --- skills (shared canonical taxonomy) ----------------------------
async def add_skill(session: AsyncSession, person_id: uuid.UUID, *, canonical_skill_id: str | None = None,
                    raw_input: str | None = None, proficiency: str | None = None,
                    years_used: int | None = None, last_used_year: int | None = None,
                    notes: str | None = None, evidence_state: str | None = None,
                    actor_admin_id: int | None = None,
                    source: PersonSource = PersonSource.USER_MANUAL) -> MnpPerson:
    person = await get_person(session, person_id)
    row = MnpPersonSkillV1(person_id=person.id, source=source)

    if canonical_skill_id:
        skill = await session.get(MnpSkill, uuid.UUID(str(canonical_skill_id)))
        if skill is None or skill.status == SkillStatus.ARCHIVED:
            raise PersonKbError("unknown canonical skill")
        row.canonical_skill_id = skill.id
        row.custom_status = CustomSkillStatus.CANONICAL
        row.raw_input = skill.canonical_name_uk
    elif raw_input and raw_input.strip():
        # try to resolve against the SAME canonical taxonomy the Career KB uses
        resolved = await _resolve_skill(session, raw_input.strip())
        if resolved is not None:
            row.canonical_skill_id = resolved.id
            row.custom_status = CustomSkillStatus.CANONICAL
            row.raw_input = raw_input.strip()
        else:
            row.raw_input = raw_input.strip()
            row.custom_status = CustomSkillStatus.PENDING_REVIEW  # never silently becomes canonical
    else:
        raise PersonKbError("provide canonical_skill_id or raw_input")

    if proficiency:
        from app.db.models_person_kb import PersonSkillProficiency
        row.proficiency = PersonSkillProficiency(proficiency)  # None stays None -- UNKNOWN != beginner
    row.years_used = years_used
    row.last_used_year = last_used_year
    row.notes = notes or None
    if evidence_state:
        row.evidence_state = PersonEvidenceState(evidence_state)
    session.add(row)
    person.profile_version += 1
    await session.flush()
    await _audit(session, actor_admin_id=actor_admin_id, person_id=person.id, action="skill_added",
                 after={"row_id": str(row.id), "custom_status": row.custom_status.value})
    await session.commit()
    return await get_person(session, person.id)


async def update_skill(session: AsyncSession, person_id: uuid.UUID, row_id: uuid.UUID, payload: dict, *,
                       actor_admin_id: int | None = None,
                       source: PersonSource = PersonSource.USER_MANUAL) -> MnpPerson:
    person = await get_person(session, person_id)
    row = await session.get(MnpPersonSkillV1, _uid(row_id))
    if row is None or row.person_id != person.id:
        raise PersonNotFoundError(f"no skill row {row_id}")
    from app.db.models_person_kb import PersonSkillProficiency
    if "proficiency" in payload:
        row.proficiency = PersonSkillProficiency(payload["proficiency"]) if payload["proficiency"] else None
    for k in ("years_used", "last_used_year", "notes"):
        if k in payload:
            setattr(row, k, payload[k] or None)
    if payload.get("evidence_state"):
        row.evidence_state = PersonEvidenceState(payload["evidence_state"])
    if payload.get("canonical_skill_id"):
        skill = await session.get(MnpSkill, uuid.UUID(str(payload["canonical_skill_id"])))
        if skill is not None:
            row.canonical_skill_id = skill.id
            row.custom_status = CustomSkillStatus.CANONICAL
    row.source = source
    person.profile_version += 1
    await session.flush()
    await _audit(session, actor_admin_id=actor_admin_id, person_id=person.id, action="skill_updated",
                 after={"row_id": str(row_id)})
    await session.commit()
    return await get_person(session, person.id)


async def delete_skill(session: AsyncSession, person_id: uuid.UUID, row_id: uuid.UUID, *,
                       actor_admin_id: int | None = None) -> MnpPerson:
    person = await get_person(session, person_id)
    row = await session.get(MnpPersonSkillV1, _uid(row_id))
    if row is None or row.person_id != person.id:
        raise PersonNotFoundError(f"no skill row {row_id}")
    await session.delete(row)
    person.profile_version += 1
    await session.flush()
    await _audit(session, actor_admin_id=actor_admin_id, person_id=person.id, action="skill_deleted",
                 after={"row_id": str(row_id)})
    await session.commit()
    return await get_person(session, person.id)


async def _resolve_skill(session: AsyncSession, phrase: str) -> MnpSkill | None:
    """Exact match against canonical name (uk/en) or an alias -- the same
    resolution the Career KB skill flow uses. No fuzzy / LLM matching."""
    norm = normalize_phrase(phrase)
    skills = (await session.execute(
        select(MnpSkill).where(MnpSkill.status != SkillStatus.ARCHIVED))).scalars().all()
    for s in skills:
        if norm in (normalize_phrase(s.canonical_name_uk), normalize_phrase(s.canonical_name_en)):
            return s
    from app.db.models_career_card import MnpSkillAlias
    aliases = (await session.execute(select(MnpSkillAlias))).scalars().all()
    for a in aliases:
        if normalize_phrase(a.alias) == norm:
            s = await session.get(MnpSkill, a.skill_id)
            if s is not None and s.status != SkillStatus.ARCHIVED:
                return s
    return None


async def search_canonical_skills(session: AsyncSession, q: str, *, limit: int = 20) -> list[MnpSkill]:
    q = (q or "").strip().lower()
    stmt = select(MnpSkill).where(MnpSkill.status == SkillStatus.ACTIVE)
    if q:
        stmt = stmt.where(func.lower(MnpSkill.canonical_name_uk).contains(q)
                          | func.lower(MnpSkill.canonical_name_en).contains(q))
    return list((await session.execute(stmt.limit(limit))).scalars().all())


# --- documents -----------------------------------------------------
async def add_document(session: AsyncSession, person_id: uuid.UUID, *, document_type: str, filename: str,
                       storage_ref: str, mime_type: str | None = None, file_size: int | None = None,
                       note: str | None = None) -> MnpPersonDocument:
    from app.db.models_person_kb import PersonDocumentType
    person = await get_person(session, person_id)
    doc = MnpPersonDocument(
        person_id=person.id, document_type=PersonDocumentType(document_type), filename=filename,
        storage_ref=storage_ref, mime_type=mime_type, file_size=file_size, note=note)
    session.add(doc)
    await session.flush()
    await session.commit()
    return doc
