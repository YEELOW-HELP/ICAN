"""Starter-catalog DATA + shared shorthands (see catalog_starter.py for
policy / provenance).

`STARTER_CAREERS[career_code] = dict(...)` -- one dict per new MNP career,
registered by `_c(...)` calls in the per-family modules
(`catalog_fam_*.py`). All human-readable text is Ukrainian-first, MNP
editorial, written independently (no Work.ua prose).

Skills: `(name_en, name_uk, type)` -> defaults importance="medium",
level="working", req_type="high_value"; or the 6-tuple
`(name_en, name_uk, type, importance, level, req_type)`.
Requirements: `(category, description_uk, hardness, value)`.
Career path steps: `(order, step_type, name_uk, typical_experience_uk)`.
"""

from __future__ import annotations

STARTER_FAMILIES: dict[str, tuple[str, str]] = {
    "sales": ("Продажі та розвиток бізнесу", "Sales & Business Development"),
    "customer_service": ("Клієнтський сервіс", "Customer Success & Service"),
    "finance": ("Фінанси та облік", "Finance & Accounting"),
    "it_digital": ("ІТ та цифрові технології", "IT & Digital"),
    "logistics": ("Логістика та ланцюги поставок", "Logistics & Supply Chain"),
    "marketing": ("Маркетинг, реклама та PR", "Marketing, Advertising & PR"),
    "management": ("Менеджмент та управління проєктами", "Management & Project Delivery"),
    "hr": ("HR та підбір персоналу", "HR & Recruiting"),
    "legal": ("Право та юридичні послуги", "Legal"),
    "healthcare": ("Медицина та охорона здоров'я", "Healthcare"),
    "education": ("Освіта та наука", "Education & Science"),
    "construction": ("Будівництво, ремонт та нерухомість", "Construction & Real Estate"),
    "manufacturing": ("Виробництво та робітничі професії", "Manufacturing & Skilled Trades"),
    "beauty": ("Краса та догляд за собою", "Beauty & Personal Care"),
    "hospitality": ("Гостинність, харчування та туризм", "Hospitality, Food & Tourism"),
    "creative": ("Мистецтво, медіа та творчі професії", "Arts, Media & Creative"),
    "security": ("Безпека та охорона", "Security & Safety"),
    "agriculture": ("Сільське та лісове господарство", "Agriculture & Forestry"),
    "transport": ("Транспорт та перевезення", "Transport & Driving"),
    "admin": ("Адміністрування та офіс", "Administration & Office"),
    "sport": ("Спорт та фітнес", "Sport & Fitness"),
}

# common skill shorthands (3-tuple: name_en, name_uk, skill_type) --------
S_UA_COMM = ("Written Business Communication", "Ділове письмове спілкування", "communication")
S_TEAM = ("Teamwork", "Робота в команді", "communication")
S_TIME = ("Time Management", "Тайм-менеджмент", "management")
S_PROBLEM = ("Problem Solving", "Розв'язання проблем", "communication")
S_ADAPT = ("Adaptability", "Адаптивність", "communication")
S_DETAIL = ("Attention to Detail", "Уважність до деталей", "communication")
S_STRESS = ("Stress Resistance", "Стресостійкість", "communication")
S_EMPATHY = ("Empathy", "Емпатія", "communication")
S_LISTEN = ("Active Listening", "Активне слухання", "communication")
S_ENG = ("English (Business)", "Ділова англійська", "functional")
S_EXCEL = ("Excel", "Excel", "tool")
S_MSOFFICE = ("Microsoft Office", "Пакет Microsoft Office", "tool")
S_NEGO = ("Sales Negotiation", "Ведення переговорів", "communication")
S_CRM = ("CRM Software", "Робота з CRM", "tool")
S_LEAD = ("Team Leadership", "Управління командою", "management")
S_SAFETY = ("Occupational Safety", "Дотримання правил охорони праці", "technical")
S_STAMINA = ("Physical Stamina", "Фізична витривалість", "functional")
S_TOOLS = ("Hand & Power Tools", "Робота з ручним та електроінструментом", "technical")
S_DRAWINGS = ("Technical Drawings", "Читання креслень", "technical")
S_CASH = ("Cash Handling", "Робота з готівкою та касою", "functional")
S_POS = ("POS Systems", "Робота з касовим апаратом (POS)", "tool")
S_HYGIENE = ("Food Safety & Hygiene", "Санітарні норми та гігієна", "technical")
S_CUSTCARE = ("Customer Service", "Обслуговування клієнтів", "functional")
S_FIRSTAID = ("First Aid", "Домедична допомога", "technical")

# requirement shorthands ------------------------------------------------
EDU_HIGHER = ("education", "Вища освіта за фахом", "soft", "bachelor")
EDU_HIGHER_PREF = ("education", "Вища освіта — перевага, не обов'язкова", "soft", None)
EDU_VOCATIONAL = ("education", "Професійно-технічна освіта за фахом", "soft", None)
EDU_SECONDARY = ("education", "Повна загальна середня освіта", "soft", None)
EXP_1Y = ("experience", "Досвід роботи за напрямом від 1 року — бажаний", "soft", "1_year")

REG_NOTE = ("Професія регульована в Україні. Конкретні вимоги до допуску, ліцензії або "
            "сертифікації потребують підтвердження авторитетним джерелом перед публікацією.")

_UK_LANG_REQ = ("language", "Вільне володіння українською мовою", "soft", "uk")

STARTER_CAREERS: dict[str, dict] = {}


def _c(code: str, **kw) -> None:
    kw.setdefault("reqs", [])
    if not any(r[0] == "language" for r in kw["reqs"]):
        kw["reqs"] = [*kw["reqs"], _UK_LANG_REQ]
    kw.setdefault("path", [])
    kw.setdefault("regulated", False)
    kw.setdefault("data_gaps", [])
    if code in STARTER_CAREERS:
        raise ValueError(f"duplicate starter career_code: {code}")
    STARTER_CAREERS[code] = kw


# populate STARTER_CAREERS from the per-family modules
from app.services.career_kb_mnp import catalog_families  # noqa: E402,F401
