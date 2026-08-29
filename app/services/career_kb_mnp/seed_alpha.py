"""MNP V1 BLOCK A -- 5-career vertical slice seed
(`MNP_READY_TO_CODE_CHECKLIST.md`: "implement a 5-career vertical slice
... expand to 50 careers only after vertical slice passes").

Deliberately editorial/curated content (`source="mnp_editorial_v1"`) --
genuine occupational knowledge (typical tasks/skills/requirements for
these 5 roles), not a fabricated market fact. No `MnpMarketSnapshot`/
`MnpSalarySnapshot` rows are created here: MNP_UA_MARKET_DATA_MODEL_V1
"Rules" forbids inventing salary/vacancy numbers, and no legally-cleared
Ukrainian market source is wired up yet (`MNP_MARKET_SOURCE_DUE_DILIGENCE_TZ`:
"No scraper is a product requirement until legal/technical access is
approved"). Every seeded `MnpCareer` is `market_data_limited=True` and the
UI must show `MARKET_DATA_LIMITED`, never a placeholder number, until a
real snapshot exists.

Idempotent: safe to call multiple times against the same DB (every
sub-step checks-then-creates)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_career_kb_mnp import (
    CareerAliasType,
    CareerLifecycleStatus,
    ImportanceLevel,
    RequirementCategory,
    RequirementHardness,
    RequirementType,
)
from app.db.models_career_card import SkillAliasType, SkillType
from app.services.career_kb_mnp.careers import (
    add_career_alias,
    add_career_attribute,
    add_career_task,
    add_requirement,
    add_skill_requirement,
    create_career,
    get_or_create_career_family,
    transition_career_status,
)
from app.services.career_kb_mnp.skills import activate_skill, add_skill_alias, create_skill

TAXONOMY_VERSION = "mnp_skill_taxonomy_alpha_v0.1"

# (canonical_name_en, canonical_name_uk, skill_type, skill_family, [uk aliases])
ALPHA_SKILLS = [
    ("Sales Negotiation", "Ведення переговорів у продажах", SkillType.COMMUNICATION, "Sales",
     ["переговори", "ведення переговорів"]),
    ("B2B Sales", "Продажі B2B", SkillType.FUNCTIONAL, "Sales", ["продажі b2b", "корпоративні продажі"]),
    ("CRM Software", "Робота з CRM", SkillType.TOOL, "Sales", ["crm", "1c crm", "bitrix24", "amocrm"]),
    ("Team Leadership", "Управління командою", SkillType.MANAGEMENT, "Management",
     ["керівництво командою", "управління персоналом"]),
    ("Customer Support", "Обслуговування клієнтів", SkillType.FUNCTIONAL, "Customer Service",
     ["клієнтський сервіс", "підтримка клієнтів"]),
    ("Active Listening", "Активне слухання", SkillType.COMMUNICATION, "Customer Service", ["активне слухання"]),
    ("Conflict Resolution", "Врегулювання конфліктів", SkillType.COMMUNICATION, "Customer Service",
     ["робота зі скаргами", "врегулювання конфліктів"]),
    ("Financial Accounting", "Бухгалтерський облік", SkillType.TECHNICAL, "Finance",
     ["бухоблік", "бухгалтерський облік"]),
    ("1C Accounting", "1С:Бухгалтерія", SkillType.TOOL, "Finance", ["1с", "1c", "1с бухгалтерія"]),
    ("Tax Reporting", "Податкова звітність", SkillType.TECHNICAL, "Finance", ["податкова звітність", "звітність"]),
    ("Excel", "Excel", SkillType.TOOL, "Data & Analytics", ["excel", "ms excel", "microsoft excel"]),
    ("Python Programming", "Програмування Python", SkillType.TECHNICAL, "Software", ["python", "пайтон"]),
    ("Web Backend Development", "Розробка backend", SkillType.TECHNICAL, "Software",
     ["backend", "бекенд розробка"]),
    ("SQL", "SQL", SkillType.TOOL, "Software", ["sql", "бази даних sql"]),
    ("Git", "Git", SkillType.TOOL, "Software", ["git", "версійний контроль"]),
    ("Logistics Planning", "Планування логістики", SkillType.FUNCTIONAL, "Logistics",
     ["логістичне планування", "планування перевезень"]),
    ("Warehouse Management Systems", "Системи управління складом", SkillType.TOOL, "Logistics",
     ["wms", "складський облік"]),
    ("Supply Chain Coordination", "Координація ланцюга поставок", SkillType.FUNCTIONAL, "Logistics",
     ["координація поставок", "supply chain"]),
    ("English (Business)", "Ділова англійська", SkillType.COMMUNICATION, "General", ["ділова англійська"]),
]

CAREER_FAMILIES = [
    ("sales", "Продажі та розвиток бізнесу", "Sales & Business Development"),
    ("customer_service", "Клієнтський сервіс", "Customer Success & Service"),
    ("finance", "Фінанси", "Finance"),
    ("it_digital", "ІТ та цифрові технології", "IT & Digital"),
    ("logistics", "Логістика та ланцюги поставок", "Logistics & Supply Chain"),
]

# code -> (name_uk, name_en, family_code, description_short_uk)
ALPHA_CAREERS = {
    "sales_manager": (
        "Менеджер з продажу", "Sales Manager", "sales",
        "Веде переговори з клієнтами, розвиває портфель продажів B2B/B2C та відповідає за виконання плану продажів.",
    ),
    "customer_service_representative": (
        "Спеціаліст з обслуговування клієнтів", "Customer Service Representative", "customer_service",
        "Обробляє звернення клієнтів, вирішує проблеми та підтримує якість сервісу компанії.",
    ),
    "accountant": (
        "Бухгалтер", "Accountant", "finance",
        "Веде бухгалтерський облік, готує податкову звітність та контролює фінансову документацію підприємства.",
    ),
    "software_developer": (
        "Розробник програмного забезпечення", "Software Developer", "it_digital",
        "Розробляє, тестує та підтримує програмні продукти на основі вимог бізнесу.",
    ),
    "logistics_coordinator": (
        "Координатор логістики", "Logistics Coordinator", "logistics",
        "Планує та координує переміщення товарів, взаємодіє з перевізниками та складом.",
    ),
}

# career_code -> [(skill_name_en, importance, required_level, requirement_type)]
CAREER_SKILL_REQUIREMENTS = {
    "sales_manager": [
        ("Sales Negotiation", ImportanceLevel.CRITICAL, "strong", RequirementType.MUST_HAVE),
        ("B2B Sales", ImportanceLevel.HIGH, "working", RequirementType.MUST_HAVE),
        ("CRM Software", ImportanceLevel.HIGH, "working", RequirementType.HIGH_VALUE),
        ("Team Leadership", ImportanceLevel.MEDIUM, "basic", RequirementType.DIFFERENTIATOR),
        ("English (Business)", ImportanceLevel.LOW, "basic", RequirementType.OPTIONAL),
    ],
    "customer_service_representative": [
        ("Customer Support", ImportanceLevel.CRITICAL, "working", RequirementType.MUST_HAVE),
        ("Active Listening", ImportanceLevel.HIGH, "working", RequirementType.MUST_HAVE),
        ("Conflict Resolution", ImportanceLevel.HIGH, "working", RequirementType.HIGH_VALUE),
        ("CRM Software", ImportanceLevel.MEDIUM, "basic", RequirementType.DIFFERENTIATOR),
    ],
    "accountant": [
        ("Financial Accounting", ImportanceLevel.CRITICAL, "strong", RequirementType.MUST_HAVE),
        ("1C Accounting", ImportanceLevel.HIGH, "working", RequirementType.MUST_HAVE),
        ("Tax Reporting", ImportanceLevel.HIGH, "working", RequirementType.MUST_HAVE),
        ("Excel", ImportanceLevel.MEDIUM, "working", RequirementType.HIGH_VALUE),
    ],
    "software_developer": [
        ("Python Programming", ImportanceLevel.CRITICAL, "working", RequirementType.MUST_HAVE),
        ("Web Backend Development", ImportanceLevel.HIGH, "working", RequirementType.MUST_HAVE),
        ("SQL", ImportanceLevel.HIGH, "working", RequirementType.MUST_HAVE),
        ("Git", ImportanceLevel.MEDIUM, "basic", RequirementType.HIGH_VALUE),
        ("English (Business)", ImportanceLevel.MEDIUM, "working", RequirementType.HIGH_VALUE),
    ],
    "logistics_coordinator": [
        ("Logistics Planning", ImportanceLevel.CRITICAL, "working", RequirementType.MUST_HAVE),
        ("Warehouse Management Systems", ImportanceLevel.HIGH, "basic", RequirementType.HIGH_VALUE),
        ("Supply Chain Coordination", ImportanceLevel.HIGH, "working", RequirementType.MUST_HAVE),
        ("Excel", ImportanceLevel.MEDIUM, "working", RequirementType.HIGH_VALUE),
    ],
}

# career_code -> [(category, description, hardness, value)]
CAREER_REQUIREMENTS = {
    "sales_manager": [
        (RequirementCategory.EXPERIENCE, "Досвід у продажах від 1 року", RequirementHardness.SOFT, "1_year"),
        (RequirementCategory.EDUCATION, "Вища освіта є перевагою, але не обов'язкова", RequirementHardness.SOFT, None),
    ],
    "customer_service_representative": [
        (RequirementCategory.EXPERIENCE, "Досвід роботи з клієнтами вітається, але не обов'язковий", RequirementHardness.SOFT, None),
    ],
    "accountant": [
        (RequirementCategory.EDUCATION, "Вища освіта за напрямом облік і аудит/фінанси", RequirementHardness.SOFT, "bachelor"),
        (RequirementCategory.EXPERIENCE, "Досвід ведення обліку від 1 року", RequirementHardness.SOFT, "1_year"),
    ],
    "software_developer": [
        (RequirementCategory.EXPERIENCE, "Портфоліо або комерційний досвід розробки", RequirementHardness.SOFT, None),
    ],
    "logistics_coordinator": [
        (RequirementCategory.EXPERIENCE, "Досвід роботи в логістиці або на складі вітається", RequirementHardness.SOFT, None),
    ],
}

# career_code -> [(attribute_group, attribute_key, value_numeric 0..1)]
CAREER_ATTRIBUTES = {
    "sales_manager": [
        ("work_context", "customer_interaction", 0.9),
        ("work_context", "autonomy", 0.6),
        ("work_context", "pace", 0.7),
    ],
    "customer_service_representative": [
        ("work_context", "customer_interaction", 1.0),
        ("work_context", "routine", 0.6),
        ("work_context", "pace", 0.7),
    ],
    "accountant": [
        ("work_context", "customer_interaction", 0.2),
        ("work_context", "routine", 0.7),
        ("work_context", "autonomy", 0.5),
    ],
    "software_developer": [
        ("work_context", "customer_interaction", 0.2),
        ("work_context", "autonomy", 0.7),
        ("work_context", "routine", 0.3),
    ],
    "logistics_coordinator": [
        ("work_context", "customer_interaction", 0.4),
        ("work_context", "routine", 0.5),
        ("work_context", "pace", 0.8),
    ],
}

ALPHA_CAREER_CODES = list(ALPHA_CAREERS.keys())


async def _get_or_create_skill_idempotent(session: AsyncSession, name_en: str, name_uk, skill_type, family):
    from sqlalchemy import select

    from app.db.models_career_card import MnpSkill

    existing = await session.execute(select(MnpSkill).where(MnpSkill.canonical_name_en == name_en))
    found = existing.scalar_one_or_none()
    if found is not None:
        return found
    return await create_skill(
        session, canonical_name_en=name_en, canonical_name_uk=name_uk, skill_type=skill_type,
        taxonomy_version=TAXONOMY_VERSION, skill_family=family,
    )


async def seed_alpha_career_kb(session: AsyncSession) -> None:
    """Idempotent orchestrator for the 5-career vertical slice."""

    skills_by_name = {}
    for name_en, name_uk, skill_type, family, aliases in ALPHA_SKILLS:
        skill = await _get_or_create_skill_idempotent(session, name_en, name_uk, skill_type, family)
        if skill.status == skill.status.DRAFT:
            await activate_skill(session, skill)
        for alias in aliases:
            await add_skill_alias(session, skill, alias=alias, language="uk", alias_type=SkillAliasType.UKRAINIAN_MARKET_TERM)
        skills_by_name[name_en] = skill

    families_by_code = {}
    for code, name_uk, name_en in CAREER_FAMILIES:
        families_by_code[code] = await get_or_create_career_family(session, code=code, name_uk=name_uk, name_en=name_en)

    for code, (name_uk, name_en, family_code, description) in ALPHA_CAREERS.items():
        from sqlalchemy import select

        from app.db.models_career_kb_mnp import MnpCareer

        existing = await session.execute(select(MnpCareer).where(MnpCareer.code == code))
        career = existing.scalar_one_or_none()
        if career is None:
            career = await create_career(
                session, code=code, canonical_name_uk=name_uk, canonical_name_en=name_en,
                description_short_uk=description, career_family=families_by_code[family_code],
            )
            await add_career_alias(session, career, alias=name_uk, alias_type=CareerAliasType.MARKET_TITLE)

            for skill_name, importance, required_level, req_type in CAREER_SKILL_REQUIREMENTS[code]:
                skill = skills_by_name[skill_name]
                await add_skill_requirement(
                    session, career, skill.id, importance=importance, required_level=required_level,
                    requirement_type=req_type, source="mnp_editorial_v1", confidence=0.7,
                )

            for category, description_text, hardness, value in CAREER_REQUIREMENTS.get(code, []):
                await add_requirement(
                    session, career, category=category, description=description_text, hardness=hardness,
                    value=value, source="mnp_editorial_v1", confidence=0.6,
                )

            for group, key, value_numeric in CAREER_ATTRIBUTES.get(code, []):
                await add_career_attribute(
                    session, career, attribute_group=group, attribute_key=key, value_numeric=value_numeric,
                    source="mnp_editorial_v1", confidence=0.5,
                )

            task_titles = {
                "sales_manager": ["Пошук нових клієнтів", "Проведення переговорів", "Ведення CRM"],
                "customer_service_representative": ["Обробка звернень клієнтів", "Вирішення скарг"],
                "accountant": ["Ведення первинної документації", "Підготовка звітності"],
                "software_developer": ["Написання коду", "Код-рев'ю", "Виправлення дефектів"],
                "logistics_coordinator": ["Планування маршрутів", "Координація з перевізниками"],
            }
            for i, title in enumerate(task_titles.get(code, []), start=1):
                await add_career_task(
                    session, career, task_code=f"{code}_task_{i}", title_uk=title,
                    importance=ImportanceLevel.HIGH, source="mnp_editorial_v1",
                )

            # DRAFT -> VALIDATED -> ACTIVE (Minimum publish gate satisfied
            # above: identity, family, description, tasks, MUST_HAVE
            # skills, requirements, work-context attributes, one alias).
            await transition_career_status(session, career, to_status=CareerLifecycleStatus.VALIDATED)
            await transition_career_status(session, career, to_status=CareerLifecycleStatus.ACTIVE)

    await session.commit()
