"""MNP Career KB -- STARTER CATALOG (Work.ua Career Guide discovery universe).

Work.ua's Career Guide (149 professions, snapshot 2026-08-31 --
`data_explorer/workua/inventory/`) answers ONE question: *which
professions does the largest Ukrainian job portal currently show
users?*. Not a line of Work.ua prose is copied -- every description,
responsibility, skill and pro/con here is MNP editorial content written
independently from general occupational knowledge
(`source="mnp_editorial_v1"`).

The 4 Work.ua professions that map to the Founder-reviewed alpha five
(`accountant`, `sales_manager`, `logistics_coordinator`,
`customer_service_representative`) are NOT recreated -- only a Work.ua
discovery reference is recorded (`WORKUA_REFERENCE`).

Every career created here starts as **DRAFT**: hidden from the public
catalog, excluded from production matching, visible + editable in the
Career KB Editor, publishable only after human review.

Market data is deliberately absent (`market_data_limited=True`, no
salary / vacancy / demand numbers -- that is the future MARKET KB
UKRAINE).

Content depth is pragmatic (Founder brief §9): 3-6 responsibilities,
5-10 skills, only known requirements, 3-4 pros / cons, a career path only
where a typical route is genuinely defensible. Deliberate gaps are listed
in `data_gaps`, never invented. Regulated professions (§13) carry
`regulated=True` and a note -- a HARD/legal blocker is NEVER asserted
here without an authoritative source.
"""

from __future__ import annotations

CATALOG_SOURCE = "mnp_editorial_v1"
CATALOG_SOURCE_VERSION = "career_kb_starter_v1"
WORKUA_DISCOVERY_REF = "work.ua/career-guide (discovery only), snapshot 2026-08-31"

# alpha career_code  <-  Work.ua slug/title  (existing cards, NOT recreated)
WORKUA_REFERENCE: dict[str, dict] = {
    "accountant": {"slug": "accountant", "title_uk": "Бухгалтер", "mapping_status": "exact"},
    "sales_manager": {"slug": "sales-manager", "title_uk": "Менеджер з продажу", "mapping_status": "exact"},
    "logistics_coordinator": {"slug": "logistician", "title_uk": "Логіст",
                              "mapping_status": "candidate_confident"},
    "customer_service_representative": {"slug": "call-center-operator", "title_uk": "Оператор call-центру",
                                       "mapping_status": "candidate_wider"},
}

# Ukrainian aliases worth storing for skill-resolution (only where useful).
SKILL_ALIASES: dict[str, list[str]] = {
    "Microsoft Office": ["ms office", "офісні програми", "word", "ексель"],
    "1C Enterprise": ["1с", "1c", "bas", "бас"],
    "Cash Handling": ["каса", "робота з касою", "касові операції"],
    "POS Systems": ["рро", "касовий апарат", "pos-термінал"],
    "Technical Drawings": ["креслення", "читання креслень"],
    "Hand & Power Tools": ["ручний інструмент", "електроінструмент"],
    "Occupational Safety": ["охорона праці", "техніка безпеки"],
    "Public Speaking": ["презентації", "публічні виступи"],
    "Stress Resistance": ["стресостійкість"],
    "Google Ads": ["google ads", "контекстна реклама", "гугл реклама"],
    "Meta Ads": ["facebook ads", "таргетована реклама", "instagram ads"],
    "Google Analytics": ["google analytics", "веб-аналітика", "гугл аналітика"],
    "Adobe Photoshop": ["photoshop", "фотошоп"],
    "Figma": ["figma", "фігма"],
    "Python Programming": ["python", "пайтон"],
    "First Aid": ["перша допомога", "домедична допомога"],
    "Driving Licence": ["посвідчення водія", "водійські права"],
}

# STARTER_CAREERS is assembled from per-family blocks in catalog_data.py to
# keep this module readable.
from app.services.career_kb_mnp.catalog_data import STARTER_CAREERS, STARTER_FAMILIES  # noqa: E402,F401

__all__ = [
    "CATALOG_SOURCE", "CATALOG_SOURCE_VERSION", "WORKUA_DISCOVERY_REF",
    "WORKUA_REFERENCE", "SKILL_ALIASES", "STARTER_CAREERS", "STARTER_FAMILIES",
]
