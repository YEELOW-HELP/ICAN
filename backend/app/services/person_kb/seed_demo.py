"""Bootstrap-only demo Person KB rows (golden personas A + B) so the
Founder / team can open the module without entering data first.

BOOTSTRAP-ONLY (Founder Decision, PERSON_KB_BASE_V1 §38): a person whose
demo marker already exists is left completely untouched -- a repeated seed
NEVER overwrites a manual edit. Synthetic data only.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_person_kb import MnpPerson, PersonSource
from app.services.person_kb import service

_MARKER = "[demo]"  # kept in `notes` -- the idempotency key

PERSONA_A = {
    "first_name": "Андрій", "last_name": "Демо-Випускник", "city": "Харків",
    "email": "demo.graduate@example.com",
    "educations": [{"education_level": "bachelor", "institution_name": "ХНУ ім. Каразіна",
                    "specialty_or_qualification": "Комп'ютерні науки", "start_year": 2020,
                    "end_year": 2024, "status": "completed"}],
    "activities": [
        {"activity_type": "academic_project", "title": "Курсовий проєкт: аналітична панель",
         "description": "Розробив дашборд на Python + SQL для навчального курсу.",
         "result_or_achievement": "Оцінка «відмінно»"},
        {"activity_type": "student_government", "title": "Староста групи", "role": "Староста",
         "description": "Організація розкладу, комунікація з деканатом."},
    ],
    "skills_raw": ["Excel", "PowerPoint", "Python"],
    "languages": [{"language": "English", "level": "b1"}, {"language": "Українська", "level": "native"}],
    "mobility": {"has_driver_license": "no", "willing_to_relocate": "yes", "work_format": "hybrid"},
}

PERSONA_B = {
    "first_name": "Марина", "last_name": "Демо-Досвідчена", "city": "Дніпро",
    "phone": "+380 50 000 00 00", "telegram_username": "@marina_demo",
    "educations": [{"education_level": "specialist", "institution_name": "ДНУ",
                    "specialty_or_qualification": "Економіка підприємства", "end_year": 2012,
                    "status": "completed"}],
    "experiences": [
        {"raw_job_title": "Керівник відділу продажів", "company_name": "ТОВ «Промтех»",
         "start_date": "2019-03-01", "is_current": "yes",
         "responsibilities_description": "Управління командою з 6 осіб, планування, ключові клієнти.",
         "achievements": "Зростання виручки на 40% за 2 роки.", "tools_used": "1С, CRM Bitrix24"},
        {"raw_job_title": "Менеджер з продажу", "company_name": "ТОВ «Ромашка»",
         "start_date": "2014-06-01", "end_date": "2019-02-28", "is_current": "no",
         "responsibilities_description": "Активні продажі B2B, ведення переговорів."},
    ],
    "credentials": [{"credential_type": "course", "title": "Курс «Управління продажами»",
                     "provider": "Laba", "issue_date": "2021-05-01"}],
    "skills_raw": ["Ведення переговорів", "CRM", "Управління командою"],
    "languages": [{"language": "English", "level": "b2"}, {"language": "Українська", "level": "native"}],
    "mobility": {"has_driver_license": "yes", "driver_license_categories": "B",
                 "has_car": "yes", "willing_to_relocate": "no", "work_format": "onsite"},
}


async def _has_demo(session: AsyncSession, first_name: str) -> bool:
    row = (await session.execute(
        select(MnpPerson).where(MnpPerson.first_name == first_name))).scalars().first()
    return row is not None and (row.notes or "").startswith(_MARKER)


async def _seed_one(session: AsyncSession, spec: dict) -> None:
    if await _has_demo(session, spec["first_name"]):
        return
    person = await service.create_person(
        session, first_name=spec["first_name"], last_name=spec.get("last_name"),
        source=PersonSource.ADMIN_MANUAL, phone=spec.get("phone"), email=spec.get("email"),
        telegram_username=spec.get("telegram_username"), city=spec.get("city"),
        notes=_MARKER + " синтетичні дані для перегляду модуля")
    for e in spec.get("educations", []):
        await service.add_row(session, person.id, "educations", e, source=PersonSource.ADMIN_MANUAL)
    for x in spec.get("experiences", []):
        await service.add_row(session, person.id, "experiences", x, source=PersonSource.ADMIN_MANUAL)
    for a in spec.get("activities", []):
        await service.add_row(session, person.id, "activities", a, source=PersonSource.ADMIN_MANUAL)
    for c in spec.get("credentials", []):
        await service.add_row(session, person.id, "credentials", c, source=PersonSource.ADMIN_MANUAL)
    for lg in spec.get("languages", []):
        await service.add_row(session, person.id, "languages", lg, source=PersonSource.ADMIN_MANUAL)
    for raw in spec.get("skills_raw", []):
        await service.add_skill(session, person.id, raw_input=raw, source=PersonSource.ADMIN_MANUAL)
    if spec.get("mobility"):
        await service.update_person_core(session, person.id, **spec["mobility"])


async def seed_demo_persons(session: AsyncSession) -> dict:
    before = len(await service.list_persons(session))
    await _seed_one(session, PERSONA_A)
    await _seed_one(session, PERSONA_B)
    after = len(await service.list_persons(session))
    return {"created": after - before, "total": after}
