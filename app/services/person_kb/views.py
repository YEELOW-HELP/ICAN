"""Person KB serialization for admin / user UI + Excel. Ukrainian-first
human labels; English internal codes preserved alongside."""

from __future__ import annotations

from app.db.models_person_kb import MnpPerson

UK = {
    "status": {"draft": "Чернетка", "active": "Активний", "archived": "В архіві"},
    "source": {"user_manual": "Заповнив користувач", "admin_manual": "Створив адміністратор",
               "admin_edit": "Виправив адміністратор", "cv_import": "З резюме (кандидат)",
               "cv_confirmed": "З резюме (підтверджено)"},
    "evidence_state": {"self_reported": "Зі слів", "document_supported": "Підтверджено документом",
                       "system_detected": "Знайдено системою (не підтверджено)",
                       "user_confirmed": "Підтверджено користувачем"},
    "tri": {"yes": "Так", "no": "Ні", "unknown": "Немає даних"},
    "education_level": {"secondary": "Середня", "vocational": "Професійно-технічна",
                        "incomplete_higher": "Неповна вища", "bachelor": "Бакалавр",
                        "specialist": "Спеціаліст", "master": "Магістр", "phd": "Доктор філософії / PhD",
                        "other": "Інше", "unknown": "Немає даних"},
    "education_status": {"completed": "Завершено", "ongoing": "Триває", "incomplete": "Незавершено",
                         "unknown": "Немає даних"},
    "credential_type": {"course": "Курс", "certificate": "Сертифікат", "license": "Ліцензія",
                        "professional_credential": "Професійна кваліфікація", "other": "Інше"},
    "activity_type": {"project": "Проєкт", "academic_project": "Навчальний проєкт",
                      "practice": "Практика", "internship": "Стажування", "volunteering": "Волонтерство",
                      "student_activity": "Студентська активність", "student_government": "Студентське самоврядування",
                      "event_organization": "Організація подій", "pet_project": "Власний проєкт",
                      "other": "Інше"},
    "language_level": {"a1": "A1", "a2": "A2", "b1": "B1", "b2": "B2", "c1": "C1", "c2": "C2",
                       "native": "Рідна", "unknown": "Немає даних", "other": "Інше"},
    "proficiency": {"basic": "Базовий", "working": "Впевнений", "strong": "Високий", None: "Немає даних"},
    "custom_status": {"canonical": "У таксономії", "pending_review": "На розгляді (не в таксономії)",
                      "rejected": "Відхилено"},
    "work_format": {"onsite": "В офісі", "remote": "Віддалено", "hybrid": "Гібрид", "any": "Будь-який",
                    "unknown": "Немає даних"},
    "document_type": {"cv": "Резюме", "diploma": "Диплом", "diploma_supplement": "Додаток до диплому",
                      "certificate": "Сертифікат", "driver_license": "Посвідчення водія",
                      "recommendation": "Рекомендація", "arbeitszeugnis": "Arbeitszeugnis",
                      "employment_document": "Документ про працевлаштування", "portfolio": "Портфоліо",
                      "other": "Інше"},
    "work_geography": {"own_city": "Своє місто", "region": "Область", "ukraine": "Україна",
                       "remote": "Віддалено", "other": "Інше"},
}


def _v(x):
    return x.value if hasattr(x, "value") else x


def lbl(group: str, code) -> str:
    code = _v(code)
    return UK.get(group, {}).get(code, code if code is not None else "Немає даних")


def _iso(d):
    return d.isoformat() if d is not None else None


def serialize_person(person: MnpPerson) -> dict:
    def edu(e):
        return {"id": str(e.id), "education_level": _v(e.education_level),
                "education_level_uk": lbl("education_level", e.education_level),
                "institution_name": e.institution_name,
                "specialty_or_qualification": e.specialty_or_qualification,
                "start_year": e.start_year, "end_year": e.end_year,
                "status": _v(e.status), "status_uk": lbl("education_status", e.status),
                "description": e.description, "supporting_document_id": str(e.supporting_document_id) if e.supporting_document_id else None,
                "evidence_state": _v(e.evidence_state), "evidence_state_uk": lbl("evidence_state", e.evidence_state),
                "source": _v(e.source)}

    def cred(c):
        return {"id": str(c.id), "credential_type": _v(c.credential_type),
                "credential_type_uk": lbl("credential_type", c.credential_type), "title": c.title,
                "provider": c.provider, "issue_date": _iso(c.issue_date), "expiry_date": _iso(c.expiry_date),
                "credential_number": c.credential_number, "description": c.description,
                "supporting_document_id": str(c.supporting_document_id) if c.supporting_document_id else None,
                "evidence_state": _v(c.evidence_state), "evidence_state_uk": lbl("evidence_state", c.evidence_state),
                "source": _v(c.source)}

    def exp(x):
        return {"id": str(x.id), "company_name": x.company_name, "raw_job_title": x.raw_job_title,
                "canonical_career_id": str(x.canonical_career_id) if x.canonical_career_id else None,
                "start_date": _iso(x.start_date), "end_date": _iso(x.end_date),
                "is_current": _v(x.is_current), "is_current_uk": lbl("tri", x.is_current),
                "responsibilities_description": x.responsibilities_description,
                "achievements": x.achievements, "tools_used": x.tools_used, "industry": x.industry,
                "employment_type": x.employment_type,
                "supporting_document_id": str(x.supporting_document_id) if x.supporting_document_id else None,
                "evidence_state": _v(x.evidence_state), "evidence_state_uk": lbl("evidence_state", x.evidence_state),
                "source": _v(x.source)}

    def act(a):
        return {"id": str(a.id), "activity_type": _v(a.activity_type),
                "activity_type_uk": lbl("activity_type", a.activity_type), "title": a.title,
                "organization": a.organization, "role": a.role, "start_date": _iso(a.start_date),
                "end_date": _iso(a.end_date), "description": a.description,
                "result_or_achievement": a.result_or_achievement,
                "supporting_document_id": str(a.supporting_document_id) if a.supporting_document_id else None,
                "evidence_state": _v(a.evidence_state), "evidence_state_uk": lbl("evidence_state", a.evidence_state),
                "source": _v(a.source)}

    def sk(s):
        return {"id": str(s.id), "canonical_skill_id": str(s.canonical_skill_id) if s.canonical_skill_id else None,
                "raw_input": s.raw_input, "custom_status": _v(s.custom_status),
                "custom_status_uk": lbl("custom_status", s.custom_status),
                "proficiency": _v(s.proficiency), "proficiency_uk": lbl("proficiency", _v(s.proficiency)),
                "years_used": s.years_used, "last_used_year": s.last_used_year, "notes": s.notes,
                "evidence_state": _v(s.evidence_state), "evidence_state_uk": lbl("evidence_state", s.evidence_state),
                "source": _v(s.source)}

    def lang(l):
        return {"id": str(l.id), "language": l.language, "level": _v(l.level),
                "level_uk": lbl("language_level", l.level), "certificate": l.certificate,
                "supporting_document_id": str(l.supporting_document_id) if l.supporting_document_id else None,
                "evidence_state": _v(l.evidence_state), "evidence_state_uk": lbl("evidence_state", l.evidence_state),
                "source": _v(l.source)}

    def doc(d):
        return {"id": str(d.id), "document_type": _v(d.document_type),
                "document_type_uk": lbl("document_type", d.document_type), "filename": d.filename,
                "mime_type": d.mime_type, "file_size": d.file_size, "note": d.note,
                "created_at": d.created_at.isoformat() if d.created_at else None}

    return {
        "id": str(person.id),
        "identity_user_id": str(person.identity_user_id) if person.identity_user_id else None,
        "core": {
            "first_name": person.first_name, "last_name": person.last_name, "phone": person.phone,
            "email": person.email, "telegram_username": person.telegram_username,
            "city": person.city, "region": person.region, "country": person.country,
            "date_of_birth": _iso(person.date_of_birth),
            "status": _v(person.status), "status_uk": lbl("status", person.status),
            "source": _v(person.source), "source_uk": lbl("source", person.source),
            "profile_version": person.profile_version, "notes": person.notes,
        },
        "mobility": {
            "has_driver_license": _v(person.has_driver_license),
            "has_driver_license_uk": lbl("tri", person.has_driver_license),
            "driver_license_categories": person.driver_license_categories,
            "has_car": _v(person.has_car), "has_car_uk": lbl("tri", person.has_car),
            "willing_to_relocate": _v(person.willing_to_relocate),
            "willing_to_relocate_uk": lbl("tri", person.willing_to_relocate),
            "work_geography": person.work_geography or [],
            "work_geography_uk": [lbl("work_geography", g) for g in (person.work_geography or [])],
            "work_format": _v(person.work_format), "work_format_uk": lbl("work_format", person.work_format),
        },
        "educations": [edu(e) for e in person.educations],
        "credentials": [cred(c) for c in person.credentials],
        "experiences": [exp(x) for x in person.experiences],
        "activities": [act(a) for a in person.activities],
        "skills": [sk(s) for s in person.skills],
        "languages": [lang(l) for l in person.languages],
        "documents": [doc(d) for d in person.documents],
        "created_at": person.created_at.isoformat() if person.created_at else None,
        "updated_at": person.updated_at.isoformat() if person.updated_at else None,
    }


def person_list_row(person: MnpPerson) -> dict:
    return {
        "id": str(person.id),
        "name": " ".join(x for x in (person.first_name, person.last_name) if x),
        "phone": person.phone, "email": person.email, "telegram_username": person.telegram_username,
        "city": person.city, "status": _v(person.status), "status_uk": lbl("status", person.status),
        "source": _v(person.source),
        "updated_at": person.updated_at.isoformat() if person.updated_at else None,
    }
