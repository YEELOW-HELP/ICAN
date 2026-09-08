from __future__ import annotations

from dataclasses import dataclass

from app.db.models_crm import CareerConsultation, Client, ClientLanguage, ClientProfile, ClientSkill, WorkExperience

# All fields that count toward the general "% filled" progress bar shown
# throughout the UI (client-level + client_profile-level).
_GENERAL_FIELDS = [
    "country", "city", "phone", "email",
]
_GENERAL_PROFILE_FIELDS = [
    "currently_employed", "current_position", "search_reasons", "readiness_to_start", "urgency",
    "education_level", "specialty",
    "primary_target", "min_salary", "employment_types", "work_formats", "schedules", "work_cities",
    "relocation_ready", "start_date",
]


@dataclass
class ReadinessCheck:
    ready: bool
    missing: list[str]


def profile_completion(
    client: Client,
    profile: ClientProfile | None,
    work_experiences: list[WorkExperience],
    skills: list[ClientSkill],
    languages: list[ClientLanguage],
) -> int:
    total = len(_GENERAL_FIELDS) + len(_GENERAL_PROFILE_FIELDS) + 3  # +3 for experience/skills/languages presence
    filled = sum(1 for f in _GENERAL_FIELDS if getattr(client, f, None))

    if profile is not None:
        filled += sum(1 for f in _GENERAL_PROFILE_FIELDS if getattr(profile, f, None))

    filled += 1 if work_experiences else 0
    filled += 1 if skills else 0
    filled += 1 if languages else 0

    return round(filled / total * 100)


def check_screening_complete(client: Client, profile: ClientProfile | None, skills: list[ClientSkill]) -> ReadinessCheck:
    """ТЗ §11: the lighter set of fields a Manager must fill before finishing
    the primary screening — a subset of the READY_FOR_MATCHING critical list."""
    missing: list[str] = []

    if not client.phone:
        missing.append("Телефон")
    if not client.country or not client.city:
        missing.append("Країна та місто")

    if profile is None:
        missing.append("Профіль клієнта не заповнено")
        return ReadinessCheck(ready=False, missing=missing)

    if profile.currently_employed is None:
        missing.append("Поточна ситуація (працює зараз)")
    if not skills:
        missing.append("Базові навички")
    if not profile.primary_target:
        missing.append("Яку роботу шукає")
    if not profile.min_salary:
        missing.append("Мінімальна зарплата")
    if not profile.employment_types:
        missing.append("Тип зайнятості")
    if not profile.work_formats:
        missing.append("Формат роботи")
    if not profile.schedules:
        missing.append("Графік")
    if not profile.constraints and not profile.constraints_comment:
        missing.append("Критичні обмеження (або підтвердження їх відсутності)")

    return ReadinessCheck(ready=not missing, missing=missing)


def check_ready_for_matching(
    client: Client,
    profile: ClientProfile | None,
    work_experiences: list[WorkExperience],
    skills: list[ClientSkill],
    languages: list[ClientLanguage],
    consultation: CareerConsultation | None,
) -> ReadinessCheck:
    """ТЗ §13: READY_FOR_MATCHING requires these specific critical fields —
    not 100% of every optional field in the client card."""
    missing: list[str] = []

    if not client.country or not client.city:
        missing.append("Країна та місто")

    if profile is None:
        missing.append("Профіль клієнта не заповнено")
        return ReadinessCheck(ready=False, missing=missing)

    if profile.currently_employed is None:
        missing.append("Поточна ситуація (працює зараз)")

    if not work_experiences and not profile.nonstandard_info:
        missing.append("Ключовий досвід (або пояснення його відсутності)")

    if not skills:
        missing.append("Основні навички")

    if not languages:
        missing.append("Мови")

    if not profile.primary_target:
        missing.append("Primary Career Target")

    if not profile.min_salary or not profile.salary_currency:
        missing.append("Мінімальна зарплата та валюта")

    if not profile.employment_types:
        missing.append("Тип зайнятості")

    if not profile.work_formats:
        missing.append("Формат роботи")

    if not profile.schedules:
        missing.append("Графік")

    if not profile.work_cities:
        missing.append("Географія")

    if not profile.constraints and not profile.constraints_comment:
        missing.append("Критичні обмеження (або підтвердження їх відсутності)")

    if consultation is None or not consultation.conclusion:
        missing.append("Career Consultant Conclusion")

    return ReadinessCheck(ready=not missing, missing=missing)
