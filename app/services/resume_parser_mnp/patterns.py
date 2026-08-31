"""Deterministic dictionaries/regex for MNP's LLM-free Resume Parser
(MNP_RESUME_PARSER_V1 "Deterministic normalization": section
dictionaries, UK/RU/EN title aliases, date parsing). Every pattern here
is a plain string/regex match -- no fuzzy scoring, no model calls."""

from __future__ import annotations

import re

# Section headers, UK/RU/EN -- matched as a whole line (case-insensitive,
# optional trailing colon).
SECTION_HEADERS: dict[str, list[str]] = {
    "experience": [
        "досвід роботи", "робочий досвід", "досвід", "experience", "work experience",
        "опыт работы", "трудовой опыт",
    ],
    "education": ["освіта", "education", "образование"],
    "skills": ["навички", "ключові навички", "skills", "навыки", "ключевые навыки"],
    "languages": ["мови", "мовні навички", "languages", "языки"],
    "credentials": [
        "сертифікати", "сертифікація", "certifications", "certificates", "ліцензії",
        "сертификаты", "лицензии",
    ],
}

_HEADER_LINE_RE = re.compile(
    r"^\s*(" + "|".join(re.escape(h) for headers in SECTION_HEADERS.values() for h in headers) + r")\s*:?\s*$",
    re.IGNORECASE | re.UNICODE,
)


def match_section_header(line: str) -> str | None:
    """Returns the canonical section key ("experience", "education", ...)
    if `line` is (only) a recognized section header, else None."""

    stripped = line.strip()
    if not stripped or not _HEADER_LINE_RE.match(stripped):
        return None
    lowered = stripped.rstrip(":").strip().lower()
    for section, headers in SECTION_HEADERS.items():
        if lowered in headers:
            return section
    return None


# Date ranges inside an experience block, e.g. "01.2020 - 05.2022",
# "2020-2022", "2019 - теперішній час", "2021 - present", "Jan 2020 -
# Present". Group 1 = start, group 2 = end (or a "current" marker word).
CURRENT_WORDS = (
    "теперішній час", "по т.ч.", "по теперішній час", "present", "current", "now",
    "настоящее время", "по настоящее время",
)
DATE_RANGE_RE = re.compile(
    r"(\d{1,2}[./]\d{4}|\d{4})\s*[-–—]\s*(\d{1,2}[./]\d{4}|\d{4}|" + "|".join(re.escape(w) for w in CURRENT_WORDS) + r")",
    re.IGNORECASE | re.UNICODE,
)

MONTHS_UA = {
    "січня": 1, "лютого": 2, "березня": 3, "квітня": 4, "травня": 5, "червня": 6,
    "липня": 7, "серпня": 8, "вересня": 9, "жовтня": 10, "листопада": 11, "грудня": 12,
}

# Management-scope inference (MNP_RESUME_PARSER_V1 "Extract": "management
# scope/team size where explicit") -- explicit numeric team size only,
# never inferred from a bare job title alone.
TEAM_SIZE_RE = re.compile(
    r"(?:команд\w*|team)\s*(?:з|of|із|из)?\s*(\d{1,3})\s*(?:осіб|людей|человек|people|співробітник\w*|сотрудник\w*|employees)?",
    re.IGNORECASE | re.UNICODE,
)

# Education level keywords -> canonical MNP level string.
EDUCATION_LEVEL_KEYWORDS: dict[str, str] = {
    "бакалавр": "bachelor", "bachelor": "bachelor",
    "магістр": "master", "магистр": "master", "master": "master",
    "спеціаліст": "specialist", "специалист": "specialist",
    "кандидат наук": "phd", "phd": "phd", "доктор філософії": "phd",
    "молодший спеціаліст": "junior_specialist",
}

GRADUATION_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")

# Languages, canonical ISO-ish code -> UK/RU/EN name variants to match.
LANGUAGE_NAMES: dict[str, list[str]] = {
    "en": ["англійська", "английский", "english"],
    "uk": ["українська", "украинский", "ukrainian"],
    "de": ["німецька", "немецкий", "german", "deutsch"],
    "pl": ["польська", "польский", "polish"],
    "ru": ["російська", "русский", "russian"],
    "fr": ["французька", "французский", "french"],
    "es": ["іспанська", "испанский", "spanish"],
}

# Proficiency level words -> canonical level string (overall_level).
LANGUAGE_LEVEL_WORDS: dict[str, str] = {
    "native": "native", "рідна": "native", "родной": "native",
    "fluent": "fluent", "вільно": "fluent", "свободно": "fluent",
    "advanced": "advanced", "просунутий": "advanced", "продвинутый": "advanced",
    "upper-intermediate": "upper_intermediate", "upper intermediate": "upper_intermediate",
    "intermediate": "intermediate", "середній": "intermediate", "средний": "intermediate",
    "elementary": "elementary", "beginner": "elementary", "базовий": "elementary", "базовый": "elementary",
    "a1": "a1", "a2": "a2", "b1": "b1", "b2": "b2", "c1": "c1", "c2": "c2",
}

CREDENTIAL_KEYWORDS = (
    "сертифікат", "сертификат", "certificate", "certification", "license", "ліцензія", "лицензия",
)

SKILL_SEPARATORS_RE = re.compile(r"[,;••\n]|(?:\s{2,})")

# A responsibility line counts as an "achievement" (MNP_RESUME_PARSER_V1
# "Extract": "responsibilities and achievements") when it states a
# measurable outcome -- a percentage, currency amount, or an explicit
# result verb -- rather than just describing an ongoing duty.
ACHIEVEMENT_INDICATOR_RE = re.compile(
    r"\d+\s*%|\bзбільшив\w*|\bзменшив\w*|\bдосяг\w*|\bувеличил\w*|\bуменьшил\w*|\bдостиг\w*"
    r"|\bincreased\b|\breduced\b|\bachieved\b|\bgrew\b|\bimproved\b|\bсэкономил\w*|\bзаощадив\w*",
    re.IGNORECASE | re.UNICODE,
)
