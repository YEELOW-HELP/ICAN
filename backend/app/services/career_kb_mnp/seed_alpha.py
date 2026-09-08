"""MNP V1 -- Career Knowledge Base: the 5-career vertical slice, filled to
product quality (`MNP_READY_TO_CODE_CHECKLIST.md`: 5 careers first, 50
only after Founder Acceptance).

FOUNDER LANGUAGE POLICY (binding):
  * internal schema  -> English-first  (career_code, skill_type, enums, ...)
  * human-readable   -> Ukrainian-first (name_uk, *_uk descriptions, pros/cons,
                        responsibilities, path steps, entry route, ...)
English (`canonical_name_en`, ESCO/O*NET labels) is a secondary reference
layer only. No runtime machine translation anywhere.

All content here is `source="mnp_editorial_v1"` -- genuine occupational
knowledge for the Ukrainian market, curated by MNP. It is NOT a fabricated
market fact: no `MnpMarketSnapshot` / `MnpSalarySnapshot` row is created
(`MNP_UA_MARKET_DATA_MODEL_V1` "Rules"). Every seeded career is
`market_data_limited=True` and the UI must show "Недостатньо ринкових
даних", never a placeholder number.

hard vs soft skills: derived from `MnpSkill.skill_type`
(`SOFT_SKILL_TYPES` below) -- no separate flag, no duplicate entity
(brief §4).

BOOTSTRAP ONLY. Once the Career KB Editor exists (`app/services/
career_kb_mnp/editor.py`), the DB + editor are the operational source of
truth. This seed only ever CREATES careers that do not yet exist; it
never re-touches an existing career -- a manual admin edit to a
description / skill / relation / status is never silently reverted by a
re-run. Safe to call repeatedly (e.g. from `scripts/dev_seed.py` or a
test fixture) but it is NOT an authoring mechanism.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_career_card import (
    MnpKnowledge,
    MnpSkill,
    SkillAliasType,
    SkillStatus,
    SkillType,
)
from app.db.models_career_kb_mnp import (
    CareerAliasType,
    CareerDifficulty,
    CareerLifecycleStatus,
    CareerPathStepType,
    CareerRelationType,
    EntryWithoutExperience,
    ImportanceLevel,
    MnpCareer,
    ProConType,
    RequirementCategory,
    RequirementHardness,
    RequirementType,
)
from app.services.career_kb_mnp.careers import (
    add_career_alias,
    add_career_attribute,
    add_career_path_step,
    add_career_procon,
    add_career_relation,
    add_career_task,
    add_knowledge_requirement,
    add_requirement,
    add_skill_requirement,
    create_career,
    get_or_create_career_family,
    set_career_entry,
    transition_career_status,
)
from app.services.career_kb_mnp.skills import activate_skill, add_skill_alias, create_skill

TAXONOMY_VERSION = "mnp_skill_taxonomy_alpha_v0.1"
SOURCE = "mnp_editorial_v1"
SOURCE_VERSION = "career_kb_v1"

# `Тверді навички` vs `М'які навички` (brief §20) -- a skill is
# intrinsically hard or soft, so this is a property of the skill's type,
# not of the career<->skill link.
SOFT_SKILL_TYPES = frozenset({SkillType.COMMUNICATION, SkillType.MANAGEMENT})


def is_soft_skill(skill_type: SkillType) -> bool:
    return skill_type in SOFT_SKILL_TYPES


CRIT, HIGH, MED, LOW = (
    ImportanceLevel.CRITICAL, ImportanceLevel.HIGH, ImportanceLevel.MEDIUM, ImportanceLevel.LOW,
)
MUST, VALUE, DIFF, OPT = (
    RequirementType.MUST_HAVE, RequirementType.HIGH_VALUE,
    RequirementType.DIFFERENTIATOR, RequirementType.OPTIONAL,
)
EDU, EXP, CRED, LANG, LEGAL, OTHER = (
    RequirementCategory.EDUCATION, RequirementCategory.EXPERIENCE, RequirementCategory.CREDENTIAL,
    RequirementCategory.LANGUAGE, RequirementCategory.LEGAL, RequirementCategory.OTHER,
)
SOFT_REQ, HARD_REQ = RequirementHardness.SOFT, RequirementHardness.HARD


# ---------------------------------------------------------------------------
# A. SKILL TAXONOMY  (canonical_name_en, canonical_name_uk, type, family, [uk aliases])
#    type in {COMMUNICATION, MANAGEMENT} => soft skill; otherwise hard.
# ---------------------------------------------------------------------------
ALPHA_SKILLS: list[tuple] = [
    # -- Sales --
    ("Sales Negotiation", "Ведення переговорів у продажах", SkillType.COMMUNICATION, "Sales",
     ["переговори", "ведення переговорів", "перемовини"]),
    ("B2B Sales", "Продажі B2B", SkillType.FUNCTIONAL, "Sales", ["продажі b2b", "корпоративні продажі"]),
    ("B2C Sales", "Продажі B2C", SkillType.FUNCTIONAL, "Sales", ["роздрібні продажі", "продажі кінцевим клієнтам"]),
    ("Lead Qualification", "Кваліфікація лідів", SkillType.FUNCTIONAL, "Sales",
     ["кваліфікація клієнтів", "обробка лідів"]),
    ("Sales Pipeline Management", "Управління воронкою продажів", SkillType.FUNCTIONAL, "Sales",
     ["воронка продажів", "робота з воронкою"]),
    ("Sales Forecasting", "Прогнозування продажів", SkillType.FUNCTIONAL, "Sales", ["прогноз продажів"]),
    ("CRM Software", "Робота з CRM", SkillType.TOOL, "Sales",
     ["crm", "bitrix24", "amocrm", "1c crm", "salesforce", "срм"]),
    ("Objection Handling", "Робота із запереченнями", SkillType.COMMUNICATION, "Sales",
     ["відпрацювання заперечень", "робота з запереченнями"]),
    ("Account Management", "Ведення ключових клієнтів", SkillType.FUNCTIONAL, "Sales",
     ["key account", "супровід клієнтів", "ведення клієнтів"]),
    ("Team Leadership", "Управління командою", SkillType.MANAGEMENT, "Management",
     ["керівництво командою", "управління персоналом", "управління командою"]),
    # -- Customer service --
    ("Customer Support", "Обслуговування клієнтів", SkillType.FUNCTIONAL, "Customer Service",
     ["клієнтський сервіс", "підтримка клієнтів"]),
    ("Active Listening", "Активне слухання", SkillType.COMMUNICATION, "Customer Service", ["активне слухання"]),
    ("Conflict Resolution", "Врегулювання конфліктів", SkillType.COMMUNICATION, "Customer Service",
     ["робота зі скаргами", "врегулювання конфліктів", "робота з конфліктами"]),
    ("Ticketing Systems", "Робота із системами звернень", SkillType.TOOL, "Customer Service",
     ["helpdesk", "zendesk", "система звернень", "тикетна система"]),
    ("Written Business Communication", "Ділове письмове спілкування", SkillType.COMMUNICATION, "General",
     ["ділове листування", "письмова комунікація", "ділова переписка"]),
    ("Empathy", "Емпатія", SkillType.COMMUNICATION, "General", ["емпатія", "клієнтоорієнтованість"]),
    ("Time Management", "Тайм-менеджмент", SkillType.MANAGEMENT, "General",
     ["управління часом", "пріоритезація", "тайм менеджмент"]),
    # -- Finance / accounting --
    ("Financial Accounting", "Бухгалтерський облік", SkillType.TECHNICAL, "Finance",
     ["бухоблік", "бухгалтерський облік", "ведення обліку"]),
    ("1C Accounting", "1С:Бухгалтерія", SkillType.TOOL, "Finance",
     ["1с", "1c", "1с бухгалтерія", "bas бухгалтерія", "бас бухгалтерія"]),
    ("Tax Reporting", "Податкова звітність", SkillType.TECHNICAL, "Finance",
     ["податкова звітність", "звітність", "подання звітності"]),
    ("Payroll Accounting", "Облік заробітної плати", SkillType.TECHNICAL, "Finance",
     ["розрахунок зарплати", "зарплатний облік", "нарахування зарплати"]),
    ("Primary Documentation", "Ведення первинної документації", SkillType.FUNCTIONAL, "Finance",
     ["первинка", "первинні документи", "первинна документація"]),
    ("Bank-Client Systems", "Робота з клієнт-банком", SkillType.TOOL, "Finance",
     ["клієнт-банк", "банківські платежі", "клієнт банк"]),
    ("Excel", "Excel", SkillType.TOOL, "Data & Analytics",
     ["excel", "ms excel", "microsoft excel", "ексель", "робота з таблицями"]),
    ("Attention to Detail", "Уважність до деталей", SkillType.COMMUNICATION, "General",
     ["уважність", "точність", "уважність до деталей"]),
    # -- Software --
    ("Python Programming", "Програмування Python", SkillType.TECHNICAL, "Software", ["python", "пайтон"]),
    ("Web Backend Development", "Розробка backend", SkillType.TECHNICAL, "Software",
     ["backend", "бекенд розробка", "серверна розробка", "бекенд"]),
    ("REST API Design", "Проєктування REST API", SkillType.TECHNICAL, "Software",
     ["rest api", "api", "розробка api"]),
    ("SQL", "SQL", SkillType.TOOL, "Software", ["sql", "бази даних sql", "postgresql", "mysql", "субд"]),
    ("Git", "Git", SkillType.TOOL, "Software", ["git", "версійний контроль", "github", "gitlab", "гіт"]),
    ("Automated Testing", "Автоматизоване тестування", SkillType.TECHNICAL, "Software",
     ["unit-тести", "автотести", "тестування коду", "юніт тести"]),
    ("Code Review", "Код-рев'ю", SkillType.TECHNICAL, "Software", ["code review", "рев'ю коду", "код рев'ю"]),
    ("Debugging", "Налагодження коду", SkillType.TECHNICAL, "Software", ["дебаг", "пошук помилок", "налагодження"]),
    # -- Logistics --
    ("Logistics Planning", "Планування логістики", SkillType.FUNCTIONAL, "Logistics",
     ["логістичне планування", "планування перевезень", "планування доставок"]),
    ("Route Optimization", "Оптимізація маршрутів", SkillType.FUNCTIONAL, "Logistics",
     ["побудова маршрутів", "оптимізація доставки", "маршрутизація"]),
    ("Warehouse Management Systems", "Системи управління складом (WMS)", SkillType.TOOL, "Logistics",
     ["wms", "складський облік", "система управління складом"]),
    ("Supply Chain Coordination", "Координація ланцюга поставок", SkillType.FUNCTIONAL, "Logistics",
     ["координація поставок", "supply chain", "ланцюг постачання", "ланцюг поставок"]),
    ("Carrier Management", "Робота з перевізниками", SkillType.FUNCTIONAL, "Logistics",
     ["робота з перевізниками", "транспортні компанії", "підбір перевізників"]),
    ("Customs Documentation", "Митне оформлення документів", SkillType.TECHNICAL, "Logistics",
     ["митне оформлення", "зед документи", "митниця"]),
    ("Inventory Control", "Контроль складських залишків", SkillType.FUNCTIONAL, "Logistics",
     ["облік залишків", "інвентаризація", "контроль залишків"]),
    # -- General / cross-role --
    ("English (Business)", "Ділова англійська", SkillType.FUNCTIONAL, "General",
     ["ділова англійська", "англійська мова", "англійська"]),
    ("Teamwork", "Робота в команді", SkillType.COMMUNICATION, "General", ["командна робота", "робота в команді"]),
    ("Problem Solving", "Розв'язання проблем", SkillType.COMMUNICATION, "General",
     ["вирішення проблем", "аналітичне мислення", "розв'язання проблем"]),
    ("Adaptability", "Адаптивність", SkillType.COMMUNICATION, "General",
     ["гнучкість", "адаптивність", "стресостійкість"]),
]

# ---------------------------------------------------------------------------
# B. KNOWLEDGE (canonical_name_en, canonical_name_uk)
# ---------------------------------------------------------------------------
ALPHA_KNOWLEDGE: list[tuple[str, str]] = [
    ("Ukrainian Tax Law", "Податкове законодавство України"),
    ("National Accounting Standards (P(S)BO)", "Національні положення (стандарти) бухгалтерського обліку"),
    ("Labour Law Basics", "Основи трудового законодавства"),
    ("Data Structures and Algorithms", "Структури даних та алгоритми"),
    ("Incoterms", "Правила Інкотермс (Incoterms)"),
    ("Consumer Protection Basics", "Основи законодавства про захист прав споживачів"),
]

CAREER_FAMILIES = [
    ("sales", "Продажі та розвиток бізнесу", "Sales & Business Development"),
    ("customer_service", "Клієнтський сервіс", "Customer Success & Service"),
    ("finance", "Фінанси та облік", "Finance & Accounting"),
    ("it_digital", "ІТ та цифрові технології", "IT & Digital"),
    ("logistics", "Логістика та ланцюги поставок", "Logistics & Supply Chain"),
]

# ---------------------------------------------------------------------------
# C. CAREERS
#    responsibilities: (title_uk, description_uk, importance)
#    skills:           (skill_name_en, importance, required_level, requirement_type)
#    knowledge:        (knowledge_name_en, importance)
#    requirements:     (category, description_uk, hardness, value)
#    path:             (step_order, step_type, step_name_uk, description_uk,
#                       typical_experience_text_uk, is_current[optional])
#    relations:        (to_career_code, relation_type)
#    attributes:       (group, key, value_numeric)
# ---------------------------------------------------------------------------
ALPHA_CAREERS: dict[str, dict] = {
    "sales_manager": dict(
        name_uk="Менеджер з продажу", name_en="Sales Manager", family="sales",
        short_uk="Веде переговори з клієнтами, розвиває портфель продажів і відповідає за виконання плану.",
        long_uk=(
            "Менеджер з продажу відповідає за пошук клієнтів, проведення переговорів та укладання угод. "
            "Він супроводжує клієнта від першого контакту до підписання договору й повторних продажів, "
            "фіксує всю роботу в CRM і працює на виконання місячного та квартального плану. Залежно від "
            "компанії фокус може бути на активному пошуку нових клієнтів (B2B), роботі з наявною базою "
            "або на роздрібних продажах (B2C)."
        ),
        difficulty=CareerDifficulty.MODERATE,
        entry_without_experience=EntryWithoutExperience.YES,
        entry_route_uk=(
            "Типовий вхід — з позиції менеджера з продажу-стажера або спеціаліста кол-центру. Ключове "
            "на старті — комунікабельність, дисципліна в роботі з CRM і готовність вивчати продукт. "
            "Профільна освіта не обов'язкова."
        ),
        aliases_uk=["Sales-менеджер", "Менеджер з продажів", "Фахівець з продажу", "Account manager",
                    "Менеджер по продажам"],
        responsibilities=[
            ("Пошук та залучення нових клієнтів",
             "Опрацювання вхідних звернень і активний пошук клієнтів через холодні та теплі контакти.", HIGH),
            ("Проведення зустрічей і презентацій",
             "Презентація продукту або послуги під потреби клієнта, демонстрації, повторні зустрічі.", CRIT),
            ("Ведення переговорів щодо умов та ціни",
             "Обговорення обсягів, ціни, знижок і термінів; відпрацювання заперечень до досягнення згоди.", CRIT),
            ("Підготовка комерційних пропозицій і договорів",
             "Формування пропозицій, узгодження умов із суміжними відділами, супровід підписання договору.", HIGH),
            ("Ведення історії комунікації та угод у CRM",
             "Фіксація кожного контакту, етапу угоди та домовленостей у CRM-системі.", HIGH),
            ("Супровід клієнта після продажу",
             "Контроль виконання зобов'язань, збір зворотного зв'язку, повторні та додаткові продажі.", MED),
            ("Виконання плану продажів",
             "Робота на виконання індивідуального місячного та квартального плану за виручкою й маржею.", CRIT),
            ("Аналіз воронки та прогнозування результату",
             "Оцінка ймовірності закриття угод, прогноз виручки на період, коригування пріоритетів.", MED),
        ],
        skills=[
            ("Sales Negotiation", CRIT, "strong", MUST),
            ("Objection Handling", CRIT, "strong", MUST),
            ("B2B Sales", HIGH, "working", MUST),
            ("Sales Pipeline Management", HIGH, "working", MUST),
            ("CRM Software", HIGH, "working", MUST),
            ("Active Listening", HIGH, "working", MUST),
            ("Lead Qualification", MED, "working", VALUE),
            ("Sales Forecasting", MED, "basic", VALUE),
            ("Account Management", MED, "working", VALUE),
            ("Time Management", MED, "working", VALUE),
            ("Adaptability", MED, "working", VALUE),
            ("Team Leadership", LOW, "basic", DIFF),
            ("Teamwork", LOW, "basic", OPT),
            ("English (Business)", LOW, "basic", OPT),
        ],
        knowledge=[],
        requirements=[
            (EXP, "Досвід у продажах або активній роботі з клієнтами від 1 року — бажаний, не обов'язковий",
             SOFT_REQ, "1_year"),
            (EDU, "Вища освіта є перевагою, але не є обов'язковою вимогою", SOFT_REQ, None),
            (LANG, "Вільне володіння українською мовою", SOFT_REQ, "uk"),
        ],
        pros=[
            "Низький поріг входу: можна почати без профільної освіти та досвіду",
            "Прозорий зв'язок між зусиллями та доходом завдяки бонусній частині",
            "Швидке кар'єрне зростання за результатами, а не за вислугою років",
            "Навички переговорів і роботи з людьми корисні в будь-якій наступній ролі",
            "Багато вакансій у різних галузях по всій Україні та у віддаленому форматі",
        ],
        cons=[
            "Дохід нестабільний і залежить від виконання плану",
            "Високий рівень стресу через тиск планів і відмови клієнтів",
            "Ненормований графік у сезонні піки та наприкінці місяця",
            "Ризик емоційного вигорання при постійній роботі із запереченнями",
            "Результат сильно залежить від якості продукту та маркетингу компанії",
        ],
        path=[
            (1, CareerPathStepType.ENTRY, "Менеджер з продажу-стажер",
             "Навчання продукту, робота за скриптами, перші угоди під наглядом наставника.", "0–6 місяців"),
            (2, CareerPathStepType.CORE, "Менеджер з продажу",
             "Самостійне ведення угод і виконання індивідуального плану.", "1–3 роки", True),
            (3, CareerPathStepType.SENIOR, "Провідний менеджер / Key Account Manager",
             "Робота з ключовими клієнтами, складні угоди, наставництво новачків.", "3–5 років"),
            (4, CareerPathStepType.LEAD, "Керівник відділу продажів",
             "Управління командою, планування, найм і розвиток менеджерів.", "5+ років"),
            (5, CareerPathStepType.EXECUTIVE, "Комерційний директор",
             "Стратегія продажів компанії, відповідальність за P&L напряму.", "8+ років"),
        ],
        relations=[("customer_service_representative", CareerRelationType.COMMON_TRANSITION),
                   ("logistics_coordinator", CareerRelationType.ADJACENT)],
        attributes=[("work_context", "customer_interaction", 0.9), ("work_context", "autonomy", 0.6),
                    ("work_context", "pace", 0.7), ("work_context", "routine", 0.3)],
    ),
    "customer_service_representative": dict(
        name_uk="Спеціаліст з обслуговування клієнтів", name_en="Customer Service Representative",
        family="customer_service",
        short_uk="Обробляє звернення клієнтів, вирішує проблеми та підтримує якість сервісу компанії.",
        long_uk=(
            "Спеціаліст з обслуговування клієнтів — перша лінія контакту між компанією та клієнтом. "
            "Він приймає звернення телефоном, у чаті та поштою, консультує щодо продуктів і послуг, "
            "розв'язує проблеми та скарги, а складні випадки передає профільним відділам. Робота "
            "здебільшого відбувається за визначеними процедурами й скриптами, з фіксацією кожного "
            "звернення в системі."
        ),
        difficulty=CareerDifficulty.EASY,
        entry_without_experience=EntryWithoutExperience.YES,
        entry_route_uk=(
            "Одна з найдоступніших офісних професій для старту кар'єри. Вхід можливий одразу після "
            "школи або коледжу після короткого внутрішнього навчання. Головне — грамотна мова, спокій "
            "у конфліктних ситуаціях і впевнена робота з комп'ютером."
        ),
        aliases_uk=["Оператор кол-центру", "Фахівець підтримки", "Спеціаліст контакт-центру",
                    "Менеджер з обслуговування клієнтів", "Support-спеціаліст"],
        responsibilities=[
            ("Прийом і обробка звернень клієнтів",
             "Опрацювання звернень телефоном, у чаті та поштою в межах узгоджених показників швидкості.", CRIT),
            ("Консультування щодо продуктів і послуг",
             "Пояснення умов, допомога з вибором, інформування про статус замовлень і платежів.", CRIT),
            ("Розв'язання типових проблем за процедурами",
             "Відпрацювання стандартних сценаріїв: повернення, заміни, технічні збої, коригування даних.", HIGH),
            ("Опрацювання скарг і врегулювання конфліктів",
             "Зниження напруги в розмові, пошук прийнятного рішення, компенсації в межах повноважень.", HIGH),
            ("Ескалація складних випадків",
             "Передача нестандартних звернень профільним відділам із повним описом ситуації.", MED),
            ("Фіксація звернень у системі",
             "Внесення суті звернення, вжитих дій і результату в CRM або систему звернень.", HIGH),
            ("Дотримання показників якості сервісу",
             "Контроль часу відповіді, оцінки клієнта (CSAT) та частки вирішених з першого контакту.", MED),
        ],
        skills=[
            ("Customer Support", CRIT, "working", MUST),
            ("Active Listening", CRIT, "strong", MUST),
            ("Conflict Resolution", HIGH, "working", MUST),
            ("Empathy", HIGH, "working", MUST),
            ("Written Business Communication", HIGH, "working", MUST),
            ("Ticketing Systems", HIGH, "working", MUST),
            ("Time Management", MED, "working", VALUE),
            ("Attention to Detail", MED, "working", VALUE),
            ("CRM Software", MED, "basic", VALUE),
            ("Excel", LOW, "basic", OPT),
            ("English (Business)", LOW, "basic", OPT),
        ],
        knowledge=[("Consumer Protection Basics", MED)],
        requirements=[
            (EDU, "Повна загальна середня освіта; профільна освіта не потрібна", SOFT_REQ, None),
            (EXP, "Досвід не обов'язковий — компанії навчають на робочому місці", SOFT_REQ, None),
            (LANG, "Грамотна усна та письмова українська мова", SOFT_REQ, "uk"),
        ],
        pros=[
            "Найнижчий поріг входу серед офісних професій — можна почати без досвіду",
            "Стабільний графік і передбачувані обов'язки",
            "Можливість працювати віддалено або гібридно",
            "Хороша стартова точка для переходу в продажі, HR, аналітику чи IT-підтримку",
            "Розвиває комунікацію, стресостійкість і знання продукту",
        ],
        cons=[
            "Невисока стартова зарплата",
            "Емоційне навантаження від роботи зі скаргами та невдоволеними клієнтами",
            "Багато рутини та повторюваних звернень",
            "Змінний графік, робота у вихідні та свята в частині компаній",
            "Обмежена автономія: робота за скриптами та жорсткими метриками",
        ],
        path=[
            (1, CareerPathStepType.ENTRY, "Спеціаліст підтримки-стажер",
             "Навчання продукту та процедур, робота під наглядом наставника.", "0–3 місяці"),
            (2, CareerPathStepType.CORE, "Спеціаліст з обслуговування клієнтів",
             "Самостійна обробка звернень усіх типів у межах своєї лінії.", "6 місяців – 2 роки", True),
            (3, CareerPathStepType.SENIOR, "Старший спеціаліст / підтримка 2-ї лінії",
             "Складні кейси, ведення бази знань, навчання новачків.", "2–4 роки"),
            (4, CareerPathStepType.LEAD, "Супервайзер / керівник групи підтримки",
             "Управління змінами, контроль якості та показників команди.", "4+ роки"),
            (5, CareerPathStepType.LEAD, "Керівник відділу клієнтського сервісу",
             "Процеси, стандарти сервісу, бюджет і розвиток відділу.", "6+ років"),
        ],
        relations=[("sales_manager", CareerRelationType.COMMON_TRANSITION)],
        attributes=[("work_context", "customer_interaction", 1.0), ("work_context", "routine", 0.7),
                    ("work_context", "pace", 0.7), ("work_context", "autonomy", 0.3)],
    ),
    "accountant": dict(
        name_uk="Бухгалтер", name_en="Accountant", family="finance",
        short_uk="Веде бухгалтерський облік, готує податкову звітність і контролює фінансову документацію підприємства.",
        long_uk=(
            "Бухгалтер відповідає за достовірний облік господарських операцій підприємства: обробляє "
            "первинні документи, нараховує заробітну плату та податки, проводить банківські й касові "
            "операції, звіряє розрахунки з контрагентами та готує регламентовану звітність для "
            "податкової та органів статистики. Робота вимагає точності, знання чинного законодавства "
            "України та впевненого володіння обліковими програмами (найчастіше 1С/BAS)."
        ),
        difficulty=CareerDifficulty.CHALLENGING,
        entry_without_experience=EntryWithoutExperience.LIMITED,
        entry_route_uk=(
            "Стандартний вхід — з посади помічника бухгалтера або бухгалтера на окрему ділянку "
            "(первинка, банк, зарплата) після профільного навчання. Повністю без освіти у сфері обліку "
            "увійти складно: потрібне розуміння П(С)БО та податкового обліку."
        ),
        aliases_uk=["Бухгалтер на первинну документацію", "Помічник бухгалтера", "Фахівець з обліку",
                    "Бухгалтер-калькулятор"],
        responsibilities=[
            ("Обробка та проведення первинних документів",
             "Перевірка й рознесення накладних, актів, рахунків та інших первинних документів в обліку.", CRIT),
            ("Ведення обліку за ділянками",
             "Облік банку, каси, основних засобів, розрахунків з постачальниками та покупцями.", CRIT),
            ("Нарахування заробітної плати та податків із неї",
             "Розрахунок зарплати, відпускних, лікарняних, ЄСВ, ПДФО та військового збору.", HIGH),
            ("Розрахунок податків і підготовка податкової звітності",
             "Розрахунок ПДВ, податку на прибуток, єдиного податку; формування та подання декларацій.", CRIT),
            ("Звірка розрахунків",
             "Складання актів звірки з контрагентами та звірка з бюджетом за податками й зборами.", HIGH),
            ("Підготовка фінансової та статистичної звітності",
             "Формування балансу, звіту про фінансові результати та статистичних форм у встановлені строки.", HIGH),
            ("Робота в обліковій системі та клієнт-банку",
             "Ведення обліку в 1С/BAS, формування і проведення платежів через систему клієнт-банк.", HIGH),
            ("Контроль строків сплати податків і подання звітів",
             "Ведення податкового календаря, недопущення прострочень і штрафних санкцій.", MED),
        ],
        skills=[
            ("Financial Accounting", CRIT, "strong", MUST),
            ("Tax Reporting", CRIT, "working", MUST),
            ("Primary Documentation", HIGH, "working", MUST),
            ("1C Accounting", HIGH, "working", MUST),
            ("Attention to Detail", CRIT, "strong", MUST),
            ("Payroll Accounting", HIGH, "working", VALUE),
            ("Bank-Client Systems", MED, "working", VALUE),
            ("Excel", MED, "working", VALUE),
            ("Time Management", HIGH, "working", VALUE),
            ("Written Business Communication", MED, "working", OPT),
        ],
        knowledge=[
            ("Ukrainian Tax Law", CRIT),
            ("National Accounting Standards (P(S)BO)", CRIT),
            ("Labour Law Basics", MED),
        ],
        requirements=[
            (EDU, "Вища або фахова передвища освіта за напрямом «Облік і оподаткування» чи «Фінанси»",
             SOFT_REQ, "bachelor"),
            (EXP, "Досвід ведення обліку від 1 року для позиції бухгалтера (помічник — без досвіду)",
             SOFT_REQ, "1_year"),
            (CRED, "Сертифікація CAP/CIPA або ACCA — перевага для рівня головного бухгалтера, не обов'язкова на старті",
             SOFT_REQ, None),
            (LANG, "Вільне володіння українською мовою", SOFT_REQ, "uk"),
        ],
        pros=[
            "Стабільний попит: бухгалтер потрібен майже кожному підприємству та ФОП",
            "Передбачуваний графік поза періодами закриття та звітності",
            "Можливість працювати віддалено або обслуговувати кількох клієнтів як аутсорсер",
            "Чіткі кар'єрні щаблі та зростання доходу з досвідом і сертифікацією",
            "Знання застосовні у власному бізнесі та особистих фінансах",
        ],
        cons=[
            "Висока відповідальність: помилки призводять до штрафів для компанії",
            "Пікові навантаження та понаднормова робота в періоди звітності",
            "Постійні зміни законодавства вимагають безперервного навчання",
            "Багато рутинної та монотонної роботи з документами",
            "Складний вхід без профільної освіти",
        ],
        path=[
            (1, CareerPathStepType.ENTRY, "Помічник бухгалтера",
             "Обробка первинки, архів, прості проводки під контролем бухгалтера.", "0–1 рік"),
            (2, CareerPathStepType.CORE, "Бухгалтер на ділянку",
             "Самостійне ведення однієї-двох ділянок обліку (банк, зарплата, ПДВ).", "1–3 роки", True),
            (3, CareerPathStepType.SENIOR, "Провідний бухгалтер",
             "Повний облік на невеликому підприємстві, підготовка звітності.", "3–6 років"),
            (4, CareerPathStepType.LEAD, "Головний бухгалтер",
             "Організація обліку, звітність, взаємодія з аудиторами та податковою.", "6+ років"),
            (5, CareerPathStepType.EXECUTIVE, "Фінансовий директор",
             "Фінансова стратегія, бюджетування, управлінський облік.", "10+ років"),
        ],
        relations=[("logistics_coordinator", CareerRelationType.RELATED)],
        attributes=[("work_context", "customer_interaction", 0.2), ("work_context", "routine", 0.7),
                    ("work_context", "autonomy", 0.5), ("work_context", "pace", 0.5)],
    ),
    "software_developer": dict(
        name_uk="Розробник програмного забезпечення", name_en="Software Developer", family="it_digital",
        short_uk="Проєктує, розробляє, тестує та підтримує програмні продукти на основі вимог бізнесу.",
        long_uk=(
            "Розробник програмного забезпечення створює й підтримує програмні продукти: аналізує "
            "вимоги, проєктує рішення, пише та тестує код, проходить код-рев'ю та випускає зміни у "
            "виробниче середовище. Працює в команді за гнучкими методологіями (Scrum/Kanban), "
            "співпрацює з тестувальниками, аналітиками та продуктовими менеджерами. Ця картка описує "
            "узагальнену роль backend-розробника; конкретний стек залежить від компанії."
        ),
        difficulty=CareerDifficulty.CHALLENGING,
        entry_without_experience=EntryWithoutExperience.LIMITED,
        entry_route_uk=(
            "Вхід — через позицію Junior-розробника після курсів, самонавчання або технічного ЗВО. "
            "Обов'язкова умова — портфоліо навчальних чи pet-проєктів і володіння хоча б однією мовою "
            "програмування. Перше працевлаштування зазвичай найскладніший етап."
        ),
        aliases_uk=["Програміст", "Backend-розробник", "Розробник ПЗ", "Software Engineer", "Developer",
                    "Розробник"],
        responsibilities=[
            ("Аналіз вимог і уточнення деталей задачі",
             "Розбір user story, уточнення крайніх випадків з аналітиком або замовником, оцінка обсягу.", HIGH),
            ("Проєктування рішення",
             "Визначення структури модулів, схеми даних та контрактів API до початку написання коду.", HIGH),
            ("Написання та рефакторинг коду",
             "Реалізація функціональності згідно зі стандартами команди, документування, рефакторинг.", CRIT),
            ("Написання автоматизованих тестів",
             "Покриття власного коду unit- та інтеграційними тестами, підтримка стабільності збірки.", HIGH),
            ("Проходження та проведення код-рев'ю",
             "Рев'ю змін колег і врахування зауважень до власних змін перед злиттям у основну гілку.", HIGH),
            ("Пошук і виправлення дефектів",
             "Відтворення багів, локалізація причини, виправлення та підтвердження регресійними тестами.", HIGH),
            ("Участь у плануванні спринтів",
             "Оцінювання задач, декомпозиція, участь у щоденних зустрічах і ретроспективах.", MED),
            ("Підтримка продукту у виробничому середовищі",
             "Реагування на інциденти, аналіз логів і метрик, випуск виправлень.", MED),
        ],
        skills=[
            ("Python Programming", CRIT, "working", MUST),
            ("Web Backend Development", HIGH, "working", MUST),
            ("SQL", HIGH, "working", MUST),
            ("REST API Design", HIGH, "working", MUST),
            ("Git", HIGH, "working", MUST),
            ("Problem Solving", CRIT, "strong", MUST),
            ("Debugging", HIGH, "working", VALUE),
            ("Automated Testing", MED, "working", VALUE),
            ("English (Business)", HIGH, "working", VALUE),
            ("Teamwork", HIGH, "working", VALUE),
            ("Code Review", MED, "basic", DIFF),
            ("Written Business Communication", MED, "basic", OPT),
            ("Adaptability", MED, "working", OPT),
        ],
        knowledge=[("Data Structures and Algorithms", HIGH)],
        requirements=[
            (EXP, "Портфоліо навчальних або комерційних проєктів; для Junior комерційний досвід не обов'язковий",
             SOFT_REQ, None),
            (EDU, "Технічна освіта є перевагою, але курси та самонавчання приймаються ринком", SOFT_REQ, None),
            (LANG, "Англійська мова на рівні читання технічної документації (від B1)", SOFT_REQ, "en:b1"),
        ],
        pros=[
            "Один із найвищих рівнів доходу серед масових професій в Україні",
            "Гнучкий графік і поширений повністю віддалений формат роботи",
            "Можливість працювати на міжнародні компанії, залишаючись в Україні",
            "Постійне професійне зростання та навчання новим технологіям",
            "Висока стійкість професії до економічних спадів",
        ],
        cons=[
            "Складний і тривалий вхід: перше працевлаштування вимагає значних зусиль",
            "Потреба безперервно вчитися — стек технологій швидко змінюється",
            "Сидяча робота та ризик вигорання при понаднормовому навантаженні",
            "Високі вимоги до логічного мислення та англійської мови",
            "Висока конкуренція серед початківців на Junior-позиції",
        ],
        path=[
            (1, CareerPathStepType.ENTRY, "Junior-розробник",
             "Прості задачі під наглядом ментора, засвоєння процесів команди.", "0–1,5 року"),
            (2, CareerPathStepType.CORE, "Middle-розробник",
             "Самостійне ведення функціональності від задачі до релізу.", "1,5–4 роки", True),
            (3, CareerPathStepType.SENIOR, "Senior-розробник",
             "Складні технічні рішення, менторство, вплив на архітектуру.", "4–7 років"),
            (4, CareerPathStepType.LEAD, "Технічний лідер / Team Lead",
             "Технічні рішення команди, планування, розвиток розробників.", "6+ років"),
            (5, CareerPathStepType.EXECUTIVE, "Архітектор ПЗ / Engineering Manager",
             "Архітектура продукту або управління кількома командами.", "8+ років"),
        ],
        relations=[("customer_service_representative", CareerRelationType.RELATED)],
        attributes=[("work_context", "customer_interaction", 0.2), ("work_context", "autonomy", 0.7),
                    ("work_context", "routine", 0.3), ("work_context", "pace", 0.5)],
    ),
    "logistics_coordinator": dict(
        name_uk="Координатор логістики", name_en="Logistics Coordinator", family="logistics",
        short_uk="Планує та координує переміщення товарів, взаємодіє з перевізниками, складом і клієнтами.",
        long_uk=(
            "Координатор логістики організовує рух товарів від постачальника до кінцевого отримувача: "
            "планує відвантаження, підбирає перевізників, будує маршрути, готує товаросупровідні "
            "документи та відстежує статус доставок. Він вирішує оперативні проблеми (затримки, "
            "пошкодження, нестача) і тримає зв'язок між складом, транспортом, відділом продажів і "
            "клієнтом. Роль вимагає уважності до деталей і вміння працювати в багатозадачному режимі."
        ),
        difficulty=CareerDifficulty.MODERATE,
        entry_without_experience=EntryWithoutExperience.LIMITED,
        entry_route_uk=(
            "Типовий вхід — з посади оператора складу, диспетчера або асистента відділу логістики. "
            "Профільна освіта бажана, але не обов'язкова: багато координаторів приходять із суміжних "
            "операційних ролей і вчаться на робочому місці."
        ),
        aliases_uk=["Логіст", "Спеціаліст з логістики", "Диспетчер логістики", "Менеджер з логістики",
                    "Координатор ланцюга поставок"],
        responsibilities=[
            ("Планування відвантажень і графіка доставок",
             "Складання щоденного плану відвантажень з урахуванням пріоритетів клієнтів і завантаження складу.", CRIT),
            ("Підбір перевізників та узгодження умов",
             "Запит тарифів, порівняння пропозицій, узгодження термінів і відповідальності за вантаж.", HIGH),
            ("Побудова та оптимізація маршрутів",
             "Формування маршрутів доставки з урахуванням географії, обмежень і вартості.", HIGH),
            ("Підготовка товаросупровідних документів",
             "Оформлення ТТН, видаткових накладних, за потреби — документів для митного оформлення.", HIGH),
            ("Відстеження статусу вантажів",
             "Моніторинг доставок у режимі реального часу та оперативне реагування на відхилення.", CRIT),
            ("Координація між складом, транспортом і клієнтом",
             "Узгодження вікон відвантаження та приймання, інформування клієнта про статус і затримки.", HIGH),
            ("Контроль складських залишків",
             "Відстеження рівня запасів і своєчасне ініціювання поповнення за критичними позиціями.", MED),
            ("Ведення звітності з логістики",
             "Облік витрат на доставку, розрахунок показників вчасності та збереження вантажу.", MED),
        ],
        skills=[
            ("Logistics Planning", CRIT, "working", MUST),
            ("Supply Chain Coordination", HIGH, "working", MUST),
            ("Carrier Management", HIGH, "working", MUST),
            ("Attention to Detail", HIGH, "working", MUST),
            ("Problem Solving", CRIT, "strong", MUST),
            ("Route Optimization", MED, "working", VALUE),
            ("Inventory Control", MED, "working", VALUE),
            ("Warehouse Management Systems", MED, "basic", VALUE),
            ("Excel", MED, "working", VALUE),
            ("Time Management", HIGH, "working", VALUE),
            ("Written Business Communication", MED, "working", OPT),
            ("Customs Documentation", LOW, "basic", DIFF),
        ],
        knowledge=[("Incoterms", MED)],
        requirements=[
            (EXP, "Досвід у логістиці, на складі або в операційній ролі від 1 року — бажаний", SOFT_REQ, "1_year"),
            (EDU, "Освіта у сфері логістики чи менеджменту — перевага, не обов'язкова", SOFT_REQ, None),
            (LANG, "Вільне володіння українською мовою", SOFT_REQ, "uk"),
        ],
        pros=[
            "Стабільний попит: логістика потрібна ритейлу, виробництву та e-commerce",
            "Різноманітні задачі — мало монотонності",
            "Зрозумілий кар'єрний шлях до керівних ролей у ланцюгах поставок",
            "Досвід цінується в суміжних сферах: закупівлі, ЗЕД, операційний менеджмент",
            "Можливість зростання доходу зі спеціалізацією (міжнародна логістика, ЗЕД)",
        ],
        cons=[
            "Високий темп і стрес через форс-мажори з доставками",
            "Відповідальність за помилки підрядників — перевізників, складу, митниці",
            "Можливі позаробочі дзвінки під час зривів у доставці",
            "Багато паперової роботи та узгоджень",
            "Результат залежить від зовнішніх чинників — погода, стан доріг, митниця",
        ],
        path=[
            (1, CareerPathStepType.ENTRY, "Асистент відділу логістики / диспетчер",
             "Оформлення документів і відстеження доставок під контролем координатора.", "0–1 рік"),
            (2, CareerPathStepType.CORE, "Координатор логістики",
             "Самостійне ведення напряму доставок і роботи з перевізниками.", "1–3 роки", True),
            (3, CareerPathStepType.SENIOR, "Провідний спеціаліст з логістики",
             "Складні напрями (міжнародна логістика, ЗЕД), оптимізація витрат.", "3–5 років"),
            (4, CareerPathStepType.LEAD, "Керівник відділу логістики",
             "Управління командою, бюджет логістики, вибір підрядників.", "5+ років"),
            (5, CareerPathStepType.EXECUTIVE, "Директор із ланцюгів поставок",
             "Стратегія ланцюга поставок компанії загалом.", "8+ років"),
        ],
        relations=[("sales_manager", CareerRelationType.ADJACENT),
                   ("accountant", CareerRelationType.RELATED)],
        attributes=[("work_context", "customer_interaction", 0.4), ("work_context", "routine", 0.5),
                    ("work_context", "pace", 0.8), ("work_context", "autonomy", 0.5)],
    ),
}

ALPHA_CAREER_CODES = list(ALPHA_CAREERS.keys())


# ---------------------------------------------------------------------------
async def _get_or_create_skill(session, name_en, name_uk, skill_type, family):
    found = (
        await session.execute(select(MnpSkill).where(MnpSkill.canonical_name_en == name_en))
    ).scalar_one_or_none()
    if found is not None:
        return found
    return await create_skill(
        session, canonical_name_en=name_en, canonical_name_uk=name_uk, skill_type=skill_type,
        taxonomy_version=TAXONOMY_VERSION, skill_family=family,
    )


async def _get_or_create_knowledge(session, name_en, name_uk):
    found = (
        await session.execute(select(MnpKnowledge).where(MnpKnowledge.canonical_name_en == name_en))
    ).scalar_one_or_none()
    if found is not None:
        return found
    row = MnpKnowledge(canonical_name_en=name_en, canonical_name_uk=name_uk, status=SkillStatus.ACTIVE)
    session.add(row)
    await session.flush()
    return row


async def seed_alpha_career_kb(session: AsyncSession) -> None:
    """Idempotent orchestrator for the 5-career vertical slice."""

    skills_by_name: dict = {}
    for name_en, name_uk, skill_type, family, aliases in ALPHA_SKILLS:
        skill = await _get_or_create_skill(session, name_en, name_uk, skill_type, family)
        if skill.status == SkillStatus.DRAFT:
            await activate_skill(session, skill)
        for alias in aliases:
            await add_skill_alias(
                session, skill, alias=alias, language="uk", alias_type=SkillAliasType.UKRAINIAN_MARKET_TERM,
                source=SOURCE,
            )
        skills_by_name[name_en] = skill

    knowledge_by_name: dict = {}
    for name_en, name_uk in ALPHA_KNOWLEDGE:
        knowledge_by_name[name_en] = await _get_or_create_knowledge(session, name_en, name_uk)

    families_by_code: dict = {}
    for code, name_uk, name_en in CAREER_FAMILIES:
        families_by_code[code] = await get_or_create_career_family(
            session, code=code, name_uk=name_uk, name_en=name_en
        )

    # `seed_alpha_career_kb` is BOOTSTRAP-ONLY. Once a career exists in the
    # DB it is owned by the Career KB Editor / admin -- the seed must never
    # touch it again (no re-adding a deleted relation/skill, no restoring
    # an edited description, no re-activating an archived career). Only
    # careers this run actually creates get their child content wired up.
    careers_by_code: dict = {}
    newly_created: set[str] = set()
    for code, spec in ALPHA_CAREERS.items():
        existing = (
            await session.execute(select(MnpCareer).where(MnpCareer.code == code))
        ).scalar_one_or_none()
        if existing is not None:
            careers_by_code[code] = existing
            continue
        newly_created.add(code)

        career = await create_career(
            session, code=code, canonical_name_uk=spec["name_uk"], canonical_name_en=spec["name_en"],
            description_short_uk=spec["short_uk"], description_long_uk=spec["long_uk"],
            career_family=families_by_code[spec["family"]],
        )
        careers_by_code[code] = career

        await set_career_entry(
            session, career, difficulty_level=spec["difficulty"],
            entry_without_experience=spec["entry_without_experience"],
            typical_entry_route_uk=spec["entry_route_uk"],
        )

        for alias in spec["aliases_uk"]:
            await add_career_alias(
                session, career, alias=alias, alias_type=CareerAliasType.MARKET_TITLE, source=SOURCE
            )

        for i, (title_uk, description_uk, importance) in enumerate(spec["responsibilities"], start=1):
            await add_career_task(
                session, career, task_code=f"{code}_r{i}", title_uk=title_uk, description=description_uk,
                importance=importance, source=SOURCE, source_version=SOURCE_VERSION, confidence=0.7,
            )

        for name_en, importance, level, req_type in spec["skills"]:
            await add_skill_requirement(
                session, career, skills_by_name[name_en].id, importance=importance, required_level=level,
                requirement_type=req_type, source=SOURCE, source_version=SOURCE_VERSION, confidence=0.7,
            )

        for name_en, importance in spec["knowledge"]:
            await add_knowledge_requirement(
                session, career, knowledge_by_name[name_en].id, importance=importance, required_level="working",
                requirement_type=MUST, source=SOURCE, confidence=0.7,
            )

        for category, description_uk, hardness, value in spec["requirements"]:
            await add_requirement(
                session, career, category=category, description=description_uk, hardness=hardness,
                value=value, country="UA", source=SOURCE, source_version=SOURCE_VERSION, confidence=0.65,
            )

        for i, text in enumerate(spec["pros"], start=1):
            await add_career_procon(
                session, career, type=ProConType.ADVANTAGE, text_uk=text, sort_order=i,
                source=SOURCE, source_version=SOURCE_VERSION, confidence=0.6,
            )
        for i, text in enumerate(spec["cons"], start=1):
            await add_career_procon(
                session, career, type=ProConType.DISADVANTAGE, text_uk=text, sort_order=i,
                source=SOURCE, source_version=SOURCE_VERSION, confidence=0.6,
            )

        for step in spec["path"]:
            order, step_type, name_uk_, desc_uk, exp_text = step[0], step[1], step[2], step[3], step[4]
            is_current = len(step) > 5 and bool(step[5])
            await add_career_path_step(
                session, career, step_order=order, step_name_uk=name_uk_, step_type=step_type,
                description_uk=desc_uk, typical_experience_text_uk=exp_text,
                is_current_career_step=is_current, source=SOURCE, source_version=SOURCE_VERSION,
            )

        for group, key, value_numeric in spec["attributes"]:
            await add_career_attribute(
                session, career, attribute_group=group, attribute_key=key, value_numeric=value_numeric,
                source=SOURCE, confidence=0.5,
            )

    # Career-to-career relations -- only for careers this run created
    # (an admin may have intentionally removed a seeded relation).
    for code, spec in ALPHA_CAREERS.items():
        if code not in newly_created:
            continue
        for to_code, rel_type in spec.get("relations", []):
            if to_code in careers_by_code:
                await add_career_relation(
                    session, careers_by_code[code], careers_by_code[to_code],
                    relation_type=rel_type, source=SOURCE,
                )

    # Lifecycle: DRAFT -> VALIDATED -> ACTIVE, only for careers this run
    # created (never re-activate something an admin archived).
    for code in newly_created:
        career = careers_by_code[code]
        if career.status == CareerLifecycleStatus.DRAFT:
            await transition_career_status(session, career, to_status=CareerLifecycleStatus.VALIDATED)
        if career.status == CareerLifecycleStatus.VALIDATED:
            await transition_career_status(session, career, to_status=CareerLifecycleStatus.ACTIVE)

    await session.commit()
