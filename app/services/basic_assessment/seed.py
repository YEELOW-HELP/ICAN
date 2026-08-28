"""Seeds the Founder-approved "Matching V1 Alpha Long Form"
(`assessment_version="matching_v1_alpha_long_form_v0.1"`) -- the ~75-item
BASIC_STRUCTURED bank approved for Alpha in Founder Review "M1 GO"
(2026-08-28), built exactly to the counts and structure in
`methodology_lab/05_GOLDEN_TEST/MNP_BASIC_SHORT_FORM_STRATEGY_V0.1.md` §2:
RIASEC 6x3, Work Style 10x2, Work Values 8x2, Work Environment 5x1, Goals 2,
Constraints 10, Experience 4 = 75.

Item wording is original MNP phrasing following the template and reverse-
item policy documented in `MNP_GOLDEN_TEST_V0.1.md` §3/§5 -- no proprietary
questionnaire's item text is copied. Every scale's compatibility metadata
(mapping_status/matching_usage/source) is taken directly from
`MNP_SCALE_TO_ONET_MAPPING_V0.1.md`; `matching_usage` is always derived via
`compute_matching_usage()`, never hand-set, so a PROXY/MNP_ONLY scale can
never accidentally end up MATCH_ENABLED.

Idempotent: re-running this against a DB that already has the
`matching_v1_alpha_long_form_v0.1` definition is a no-op (returns the
existing definition unchanged) -- safe to call from a startup hook or a
test fixture without risking duplicate rows.

Zero-AI: this module does not import `app.ai_gateway` or any PRO Hybrid
extraction/synthesis service.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_basic_assessment import (
    AssessmentDefinition,
    AssessmentItem,
    AssessmentItemOption,
    AssessmentMode,
    AssessmentScale,
    AssessmentSection,
    MappingStatus,
    MatchingUsage,
    ResponseType,
    ScaleFamily,
    compute_matching_usage,
)

ASSESSMENT_VERSION = "matching_v1_alpha_long_form_v0.1"
METHODOLOGY_VERSION = "golden_test_v0.1"
SOURCE_DOC = "MNP_GOLDEN_TEST_V0.1.md"
MAPPING_DOC = "MNP_SCALE_TO_ONET_MAPPING_V0.1.md"


@dataclass
class ItemOptionSpec:
    key: str
    label_uk: str


@dataclass
class ItemSpec:
    key_suffix: str
    question_uk: str
    response_type: ResponseType
    reverse_scored: bool = False
    reverse_exempt: bool = False
    options: list[ItemOptionSpec] = field(default_factory=list)


@dataclass
class ScaleSpec:
    scale_family: ScaleFamily
    scale_key: str
    label_uk: str
    mapping_status: MappingStatus
    items: list[ItemSpec]
    source_system: str | None = None
    source_element_id: str | None = None
    source_element_name: str | None = None
    source_version: str | None = None
    transformation_version: str | None = None
    provisional_override: bool | None = None


# ---------------------------------------------------------------------------
# A. RIASEC -- 6 scales x 3 items, all DIRECT (MNP_SCALE_TO_ONET_MAPPING §A)
# ---------------------------------------------------------------------------

_RIASEC = [
    ScaleSpec(
        ScaleFamily.RIASEC, "R", "Реалістичний", MappingStatus.DIRECT,
        source_system="onet", source_element_name="Interests — Realistic", source_version="30.3",
        items=[
            ItemSpec("1", "Мені подобається працювати руками — ремонтувати, збирати, налаштовувати обладнання", ResponseType.LIKERT_5, reverse_exempt=True),
            ItemSpec("2", "Мені комфортно виконувати фізичну або технічну роботу", ResponseType.LIKERT_5, reverse_exempt=True),
            ItemSpec("3", "Я із задоволенням розбираюся, як влаштовані механізми та інструменти", ResponseType.LIKERT_5, reverse_exempt=True),
        ],
    ),
    ScaleSpec(
        ScaleFamily.RIASEC, "I", "Дослідницький", MappingStatus.DIRECT,
        source_system="onet", source_element_name="Interests — Investigative", source_version="30.3",
        items=[
            ItemSpec("1", "Мені цікаво розбиратися, чому щось працює саме так, а не інакше", ResponseType.LIKERT_5, reverse_exempt=True),
            ItemSpec("2", "Мені подобається аналізувати дані та шукати закономірності", ResponseType.LIKERT_5, reverse_exempt=True),
            ItemSpec("3", "Я люблю вивчати нові теми, навіть якщо це непросто", ResponseType.LIKERT_5, reverse_exempt=True),
        ],
    ),
    ScaleSpec(
        ScaleFamily.RIASEC, "A", "Артистичний", MappingStatus.DIRECT,
        source_system="onet", source_element_name="Interests — Artistic", source_version="30.3",
        items=[
            ItemSpec("1", "Мені подобається створювати щось оригінальне — текст, дизайн, музику, відео", ResponseType.LIKERT_5, reverse_exempt=True),
            ItemSpec("2", "Я отримую задоволення від творчого самовираження", ResponseType.LIKERT_5, reverse_exempt=True),
            ItemSpec("3", "Мені подобається придумувати нестандартні рішення", ResponseType.LIKERT_5, reverse_exempt=True),
        ],
    ),
    ScaleSpec(
        ScaleFamily.RIASEC, "S", "Соціальний", MappingStatus.DIRECT,
        source_system="onet", source_element_name="Interests — Social", source_version="30.3",
        items=[
            ItemSpec("1", "Мені важливо, щоб моя робота допомагала іншим людям", ResponseType.LIKERT_5, reverse_exempt=True),
            ItemSpec("2", "Мені подобається навчати або консультувати інших", ResponseType.LIKERT_5, reverse_exempt=True),
            ItemSpec("3", "Я легко знаходжу спільну мову з різними людьми", ResponseType.LIKERT_5, reverse_exempt=True),
        ],
    ),
    ScaleSpec(
        ScaleFamily.RIASEC, "E", "Підприємницький", MappingStatus.DIRECT,
        source_system="onet", source_element_name="Interests — Enterprising", source_version="30.3",
        items=[
            ItemSpec("1", "Мені подобається переконувати людей і вести перемовини", ResponseType.LIKERT_5, reverse_exempt=True),
            ItemSpec("2", "Мені комфортно брати на себе ініціативу в проєктах", ResponseType.LIKERT_5, reverse_exempt=True),
            ItemSpec("3", "Мені подобається розвивати власні ідеї чи справу", ResponseType.LIKERT_5, reverse_exempt=True),
        ],
    ),
    ScaleSpec(
        ScaleFamily.RIASEC, "C", "Конвенційний", MappingStatus.DIRECT,
        source_system="onet", source_element_name="Interests — Conventional", source_version="30.3",
        items=[
            ItemSpec("1", "Мені комфортно працювати з чіткими інструкціями та структурованими даними", ResponseType.LIKERT_5, reverse_exempt=True),
            ItemSpec("2", "Мені подобається наводити лад у документах та процесах", ResponseType.LIKERT_5, reverse_exempt=True),
            ItemSpec("3", "Я віддаю перевагу передбачуваним, добре організованим завданням", ResponseType.LIKERT_5, reverse_exempt=True),
        ],
    ),
]

# ---------------------------------------------------------------------------
# B. Work Style -- 10 scales x 2 items (1 straight + 1 reverse each), per
#    MNP_SCALE_TO_ONET_MAPPING_V0.1.md §B
# ---------------------------------------------------------------------------

_WORK_STYLE = [
    ScaleSpec(ScaleFamily.WORK_STYLE, "autonomy", "Автономність", MappingStatus.MNP_ONLY, items=[
        ItemSpec("1", "Я працюю найкраще, коли сам вирішую, як виконати завдання", ResponseType.LIKERT_5),
        ItemSpec("2", "Мені некомфортно, коли доводиться приймати рішення самостійно, без чіткої вказівки", ResponseType.LIKERT_5, reverse_scored=True),
    ]),
    ScaleSpec(ScaleFamily.WORK_STYLE, "structure_preference", "Схильність до структурованості", MappingStatus.DERIVED,
              source_system="onet", source_element_name="Structured Work / Unstructured Work (Work Context)", source_version="30.3",
              items=[
        ItemSpec("1", "Мені комфортніше, коли є чіткий алгоритм дій для кожної задачі", ResponseType.LIKERT_5),
        ItemSpec("2", "Мені швидко набридає робота за жорстко визначеним алгоритмом", ResponseType.LIKERT_5, reverse_scored=True),
    ]),
    ScaleSpec(ScaleFamily.WORK_STYLE, "ambiguity_tolerance", "Толерантність до невизначеності", MappingStatus.DIRECT,
              source_system="onet", source_element_name="Tolerance for Ambiguity", source_version="30.3", items=[
        ItemSpec("1", "Я спокійно почуваюся в ситуаціях невизначеності, коли не все відомо заздалегідь", ResponseType.LIKERT_5),
        ItemSpec("2", "Мене турбує, коли завдання сформульоване нечітко", ResponseType.LIKERT_5, reverse_scored=True),
    ]),
    ScaleSpec(ScaleFamily.WORK_STYLE, "pace", "Темп роботи", MappingStatus.PROXY,
              source_system="onet", source_element_name="Time Pressure / Stress Tolerance (proxy)", source_version="30.3", items=[
        ItemSpec("1", "Мені подобається працювати у швидкому темпі, з частою зміною задач", ResponseType.LIKERT_5),
        ItemSpec("2", "Я віддаю перевагу рівномірному, неспішному темпу роботи", ResponseType.LIKERT_5, reverse_scored=True),
    ]),
    ScaleSpec(ScaleFamily.WORK_STYLE, "collaboration", "Схильність до співпраці", MappingStatus.DERIVED,
              source_system="onet", source_element_name="Social Orientation + Cooperation", source_version="30.3", items=[
        ItemSpec("1", "Мені подобається працювати в команді, а не поодинці", ResponseType.LIKERT_5),
        ItemSpec("2", "Я продуктивніший(-а), коли працюю самостійно, без постійної взаємодії з іншими", ResponseType.LIKERT_5, reverse_scored=True),
    ]),
    ScaleSpec(ScaleFamily.WORK_STYLE, "leadership", "Лідерство", MappingStatus.DIRECT,
              source_system="onet", source_element_name="Leadership Orientation", source_version="30.3", items=[
        ItemSpec("1", "Мені комфортно брати на себе роль лідера в групі", ResponseType.LIKERT_5),
        ItemSpec("2", "Я не прагну керувати іншими чи брати відповідальність за групу", ResponseType.LIKERT_5, reverse_scored=True),
    ]),
    ScaleSpec(ScaleFamily.WORK_STYLE, "customer_interaction", "Контакт із клієнтами", MappingStatus.PROXY,
              source_system="onet", source_element_name="Deal With External Customers (Work Context)", source_version="30.3", items=[
        ItemSpec("1", "Мені подобається спілкуватися з клієнтами напряму", ResponseType.LIKERT_5),
        ItemSpec("2", "Я віддаю перевагу роботі без прямого контакту з клієнтами", ResponseType.LIKERT_5, reverse_scored=True),
    ]),
    ScaleSpec(ScaleFamily.WORK_STYLE, "decision_responsibility", "Відповідальність за рішення", MappingStatus.PROXY,
              source_system="onet", source_element_name="Freedom to Make Decisions / Responsibility for Outcomes (Work Context)", source_version="30.3", items=[
        ItemSpec("1", "Мені комфортно нести відповідальність за наслідки власних рішень на роботі", ResponseType.LIKERT_5),
        ItemSpec("2", "Я почуваюся некомфортно, коли моє рішення суттєво впливає на інших", ResponseType.LIKERT_5, reverse_scored=True),
    ]),
    ScaleSpec(ScaleFamily.WORK_STYLE, "routine_tolerance", "Толерантність до рутини", MappingStatus.PROXY,
              source_system="onet", source_element_name="Importance of Repeating Same Tasks (Work Context, inverse)", source_version="30.3", items=[
        ItemSpec("1", "Я спокійно ставлюся до одноманітної, повторюваної роботи", ResponseType.LIKERT_5),
        ItemSpec("2", "Мене швидко втомлює одноманітна, повторювана робота", ResponseType.LIKERT_5, reverse_scored=True),
    ]),
    ScaleSpec(ScaleFamily.WORK_STYLE, "initiative", "Ініціативність", MappingStatus.DIRECT,
              source_system="onet", source_element_name="Initiative", source_version="30.3", items=[
        ItemSpec("1", "Я із задоволенням беру на себе додаткові завдання та відповідальність", ResponseType.LIKERT_5),
        ItemSpec("2", "Я віддаю перевагу чітко визначеним обов'язкам, без ініціативи понад них", ResponseType.LIKERT_5, reverse_scored=True),
    ]),
]

# ---------------------------------------------------------------------------
# C. Work Values -- 8 scales x 2 items, per MNP_SCALE_TO_ONET_MAPPING_V0.1.md §C
# ---------------------------------------------------------------------------

_WORK_VALUES = [
    ScaleSpec(ScaleFamily.WORK_VALUES, "income", "Дохід", MappingStatus.PROXY,
              source_system="onet", source_element_name="Working Conditions (partial)", source_version="30.3", items=[
        ItemSpec("1", "Для мене важливо, щоб робота давала високий і стабільний дохід", ResponseType.LIKERT_5),
        ItemSpec("2", "Розмір заробітної плати не є для мене вирішальним фактором при виборі роботи", ResponseType.LIKERT_5, reverse_scored=True),
    ]),
    ScaleSpec(ScaleFamily.WORK_VALUES, "stability", "Стабільність", MappingStatus.PROXY,
              source_system="onet", source_element_name="Support (partial)", source_version="30.3", items=[
        ItemSpec("1", "Для мене важлива впевненість у завтрашньому дні та стабільність зайнятості", ResponseType.LIKERT_5),
        ItemSpec("2", "Мене не лякає непередбачуваність чи тимчасовість роботи", ResponseType.LIKERT_5, reverse_scored=True),
    ]),
    ScaleSpec(ScaleFamily.WORK_VALUES, "growth", "Кар'єрне зростання", MappingStatus.MNP_ONLY, items=[
        ItemSpec("1", "Для мене важливо мати можливість кар'єрного росту та підвищення", ResponseType.LIKERT_5),
        ItemSpec("2", "Мене влаштовує робота без перспектив просування, якщо вона стабільна", ResponseType.LIKERT_5, reverse_scored=True),
    ]),
    ScaleSpec(ScaleFamily.WORK_VALUES, "independence_value", "Незалежність", MappingStatus.DIRECT,
              source_system="onet", source_element_name="Independence", source_version="30.3", items=[
        ItemSpec("1", "Для мене важливо мати свободу приймати рішення без постійного контролю", ResponseType.LIKERT_5),
        ItemSpec("2", "Мені не принципово, наскільки самостійно я можу діяти на роботі", ResponseType.LIKERT_5, reverse_scored=True),
    ]),
    ScaleSpec(ScaleFamily.WORK_VALUES, "impact_helping", "Користь іншим", MappingStatus.DIRECT,
              source_system="onet", source_element_name="Relationships", source_version="30.3", items=[
        ItemSpec("1", "Для мене важливо, щоб моя робота приносила користь іншим людям", ResponseType.LIKERT_5),
        ItemSpec("2", "Я не надаю особливого значення тому, чи допомагає моя робота іншим", ResponseType.LIKERT_5, reverse_scored=True),
    ]),
    ScaleSpec(ScaleFamily.WORK_VALUES, "recognition_status", "Визнання", MappingStatus.DIRECT,
              source_system="onet", source_element_name="Recognition", source_version="30.3", items=[
        ItemSpec("1", "Для мене важливо, щоб мої досягнення визнавали й цінували", ResponseType.LIKERT_5),
        ItemSpec("2", "Визнання з боку інших не є для мене важливим", ResponseType.LIKERT_5, reverse_scored=True),
    ]),
    ScaleSpec(ScaleFamily.WORK_VALUES, "work_life_balance", "Баланс роботи й життя", MappingStatus.MNP_ONLY, items=[
        ItemSpec("1", "Для мене важливо мати достатньо часу на особисте життя поза роботою", ResponseType.LIKERT_5),
        ItemSpec("2", "Я готовий(-а) жертвувати особистим часом заради роботи", ResponseType.LIKERT_5, reverse_scored=True),
    ]),
    ScaleSpec(ScaleFamily.WORK_VALUES, "learning", "Навчання", MappingStatus.MNP_ONLY, items=[
        ItemSpec("1", "Для мене важливо постійно навчатися новому у своїй роботі", ResponseType.LIKERT_5),
        ItemSpec("2", "Мене цілком влаштовує виконувати одні й ті самі задачі без нових знань", ResponseType.LIKERT_5, reverse_scored=True),
    ]),
]

# ---------------------------------------------------------------------------
# D. Work Environment -- 5 scales x 1 item (floor exception, per short-form
#    doc §3 -- explicitly reverse_exempt at this length)
# ---------------------------------------------------------------------------

_WORK_ENVIRONMENT = [
    ScaleSpec(ScaleFamily.WORK_ENVIRONMENT, "setting", "Робоче середовище", MappingStatus.DERIVED,
              source_system="onet", source_element_name="Indoors/Outdoors/Vehicle Work Contexts", source_version="30.3", items=[
        ItemSpec("1", "Мені комфортніше працювати в офісі чи на визначеному робочому місці, ніж повністю віддалено", ResponseType.LIKERT_5, reverse_exempt=True),
    ]),
    ScaleSpec(ScaleFamily.WORK_ENVIRONMENT, "collaboration_context", "Командний контекст", MappingStatus.DIRECT,
              source_system="onet", source_element_name="Work With Work Group or Team", source_version="30.3", items=[
        ItemSpec("1", "Мені комфортніше, коли я щодня взаємодію з командою, а не працюю ізольовано", ResponseType.LIKERT_5, reverse_exempt=True),
    ]),
    ScaleSpec(ScaleFamily.WORK_ENVIRONMENT, "schedule_predictability", "Передбачуваність графіку", MappingStatus.DIRECT,
              source_system="onet", source_element_name="Work Schedule — Regular/Irregular/Seasonal", source_version="30.3", items=[
        ItemSpec("1", "Мені комфортніше мати стабільний, передбачуваний графік роботи", ResponseType.LIKERT_5, reverse_exempt=True),
    ]),
    ScaleSpec(ScaleFamily.WORK_ENVIRONMENT, "physical_environment", "Фізичне середовище", MappingStatus.DERIVED,
              source_system="onet", source_element_name="Physical-demand Work Contexts", source_version="30.3", items=[
        ItemSpec("1", "Мені комфортно виконувати роботу, що вимагає фізичної активності або перебування поза офісом", ResponseType.LIKERT_5, reverse_exempt=True),
    ]),
    ScaleSpec(ScaleFamily.WORK_ENVIRONMENT, "customer_interaction_context", "Контакт із відвідувачами", MappingStatus.DIRECT,
              source_system="onet", source_element_name="Deal With External Customers", source_version="30.3", items=[
        ItemSpec("1", "Мені комфортно, коли робота передбачає постійний контакт із клієнтами чи відвідувачами", ResponseType.LIKERT_5, reverse_exempt=True),
    ]),
]

# ---------------------------------------------------------------------------
# E. Goals -- 2 structured items, MNP_ONLY (never a Fit input -- Golden Test
#    doc §13 / Open Question C)
# ---------------------------------------------------------------------------

_CAREER_DOMAIN_OPTIONS = [
    ItemOptionSpec("technology", "Технології та ІТ"),
    ItemOptionSpec("healthcare", "Охорона здоров'я"),
    ItemOptionSpec("engineering", "Інженерія"),
    ItemOptionSpec("logistics_transport", "Логістика та транспорт"),
    ItemOptionSpec("skilled_trades", "Робітничі професії"),
    ItemOptionSpec("sales", "Продажі"),
    ItemOptionSpec("customer_service", "Обслуговування клієнтів"),
    ItemOptionSpec("management", "Менеджмент"),
    ItemOptionSpec("finance", "Фінанси"),
    ItemOptionSpec("education", "Освіта"),
    ItemOptionSpec("creative", "Творчі професії"),
    ItemOptionSpec("marketing", "Маркетинг"),
    ItemOptionSpec("social_sector", "Соціальна сфера"),
    ItemOptionSpec("administration", "Адміністрування"),
    ItemOptionSpec("hospitality_service", "Готельно-ресторанна справа"),
    ItemOptionSpec("manufacturing", "Виробництво"),
]

_GOALS = [
    ScaleSpec(ScaleFamily.GOALS, "desired_domains", "Бажані напрямки", MappingStatus.MNP_ONLY, items=[
        ItemSpec("domains", "Які напрямки діяльності вас цікавлять найбільше? (можна обрати кілька)",
                 ResponseType.MULTI_CHOICE, reverse_exempt=True, options=_CAREER_DOMAIN_OPTIONS),
    ]),
    ScaleSpec(ScaleFamily.GOALS, "horizon", "Часовий горизонт", MappingStatus.MNP_ONLY, items=[
        ItemSpec("horizon", "Коли ви плануєте змінити або почати кар'єру?", ResponseType.SINGLE_CHOICE, reverse_exempt=True, options=[
            ItemOptionSpec("now", "Зараз"),
            ItemOptionSpec("months_3_6", "Через 3–6 місяців"),
            ItemOptionSpec("months_6_12", "Через 6–12 місяців"),
            ItemOptionSpec("exploring", "Поки що вивчаю варіанти"),
        ]),
    ]),
]

# ---------------------------------------------------------------------------
# F. Constraints -- 10 structured items, MNP_ONLY (feasibility input only,
#    per Golden Test doc §14)
# ---------------------------------------------------------------------------

_CONSTRAINTS = [
    ScaleSpec(ScaleFamily.CONSTRAINTS, "language", "Мова", MappingStatus.MNP_ONLY, items=[
        ItemSpec("language", "Який ваш рівень володіння основною іноземною мовою, потрібною для роботи?", ResponseType.SINGLE_CHOICE, reverse_exempt=True, options=[
            ItemOptionSpec("none", "Не володію"),
            ItemOptionSpec("basic", "Базовий"),
            ItemOptionSpec("intermediate", "Середній"),
            ItemOptionSpec("advanced", "Просунутий"),
            ItemOptionSpec("fluent", "Вільно"),
        ]),
    ]),
    ScaleSpec(ScaleFamily.CONSTRAINTS, "education", "Освіта", MappingStatus.MNP_ONLY, items=[
        ItemSpec("education", "Ваш найвищий здобутий рівень освіти?", ResponseType.SINGLE_CHOICE, reverse_exempt=True, options=[
            ItemOptionSpec("secondary", "Середня освіта"),
            ItemOptionSpec("vocational", "Професійно-технічна освіта"),
            ItemOptionSpec("bachelor", "Бакалавр"),
            ItemOptionSpec("master", "Магістр"),
            ItemOptionSpec("phd", "Науковий ступінь"),
        ]),
    ]),
    ScaleSpec(ScaleFamily.CONSTRAINTS, "credential_legal", "Ліцензії/дозволи", MappingStatus.MNP_ONLY, items=[
        ItemSpec("credential", "У мене є чинні професійні ліцензії або дозволи, які можуть знадобитися для роботи за фахом",
                 ResponseType.BOOLEAN, reverse_exempt=True),
    ]),
    ScaleSpec(ScaleFamily.CONSTRAINTS, "geography_mobility", "Географія/мобільність", MappingStatus.MNP_ONLY, items=[
        ItemSpec("geo_mobility", "Наскільки ви готові до релокації заради роботи?", ResponseType.SINGLE_CHOICE, reverse_exempt=True, options=[
            ItemOptionSpec("willing_anywhere", "Готовий(-а) переїхати"),
            ItemOptionSpec("willing_within_region", "Готовий(-а) лише в межах свого міста/регіону"),
            ItemOptionSpec("not_willing", "Не готовий(-а) переїжджати"),
        ]),
    ]),
    ScaleSpec(ScaleFamily.CONSTRAINTS, "work_format", "Формат роботи", MappingStatus.MNP_ONLY, items=[
        ItemSpec("work_format", "Який формат роботи для вас бажаний?", ResponseType.SINGLE_CHOICE, reverse_exempt=True, options=[
            ItemOptionSpec("office", "Офіс"),
            ItemOptionSpec("remote", "Віддалено"),
            ItemOptionSpec("hybrid", "Гібридно"),
        ]),
    ]),
    ScaleSpec(ScaleFamily.CONSTRAINTS, "work_schedule", "Графік роботи", MappingStatus.MNP_ONLY, items=[
        ItemSpec("work_schedule", "Який графік роботи для вас прийнятний?", ResponseType.SINGLE_CHOICE, reverse_exempt=True, options=[
            ItemOptionSpec("full_time", "Повний робочий день"),
            ItemOptionSpec("part_time", "Неповний робочий день"),
            ItemOptionSpec("flexible", "Гнучкий графік"),
            ItemOptionSpec("shift", "Змінний графік"),
        ]),
    ]),
    ScaleSpec(ScaleFamily.CONSTRAINTS, "time_capacity", "Часовий ресурс на навчання", MappingStatus.MNP_ONLY, items=[
        ItemSpec("time_capacity", "Скільки годин на тиждень ви можете виділити на навчання/перехід у нову професію?",
                 ResponseType.SINGLE_CHOICE, reverse_exempt=True, options=[
            ItemOptionSpec("none", "Немає часу"),
            ItemOptionSpec("1_5h", "1–5 годин"),
            ItemOptionSpec("6_10h", "6–10 годин"),
            ItemOptionSpec("10h_plus", "Понад 10 годин"),
        ]),
    ]),
    ScaleSpec(ScaleFamily.CONSTRAINTS, "financial_capacity", "Фінансова спроможність", MappingStatus.MNP_ONLY, items=[
        ItemSpec("financial_capacity", "У мене є фінансова можливість пройти перенавчання, якщо це знадобиться",
                 ResponseType.BOOLEAN, reverse_exempt=True),
    ]),
    ScaleSpec(ScaleFamily.CONSTRAINTS, "family_logistics", "Сімейні/логістичні обмеження", MappingStatus.MNP_ONLY, items=[
        ItemSpec("family_logistics", "Наскільки сімейні чи логістичні обставини обмежують ваш вибір графіка/місця роботи?",
                 ResponseType.SINGLE_CHOICE, reverse_exempt=True, options=[
            ItemOptionSpec("none", "Не обмежують"),
            ItemOptionSpec("moderate", "Помірно обмежують"),
            ItemOptionSpec("significant", "Суттєво обмежують"),
        ]),
    ]),
    ScaleSpec(ScaleFamily.CONSTRAINTS, "functional", "Функціональні обмеження", MappingStatus.MNP_ONLY, items=[
        ItemSpec("functional", "Чи є у вас обмеження за станом здоров'я, що впливають на вибір виду діяльності?",
                 ResponseType.SINGLE_CHOICE, reverse_exempt=True, options=[
            ItemOptionSpec("none", "Немає"),
            ItemOptionSpec("some", "Є, помірні"),
            ItemOptionSpec("significant", "Є, суттєві"),
        ]),
    ]),
]

# ---------------------------------------------------------------------------
# G. Experience/Skills -- 4 structured items, MNP_ONLY
# ---------------------------------------------------------------------------

_KNOWN_SKILLS_OPTIONS = [
    ItemOptionSpec("digital_literacy", "Комп'ютерна грамотність"),
    ItemOptionSpec("sales_negotiation", "Продажі й переговори"),
    ItemOptionSpec("project_management", "Управління проєктами"),
    ItemOptionSpec("customer_service", "Робота з клієнтами"),
    ItemOptionSpec("manual_technical", "Ручна/технічна робота"),
    ItemOptionSpec("data_analysis", "Аналіз даних"),
    ItemOptionSpec("creative_skills", "Творчі навички (дизайн, текст, відео)"),
    ItemOptionSpec("teaching", "Викладання/навчання інших"),
    ItemOptionSpec("team_leadership", "Керівництво командою"),
    ItemOptionSpec("foreign_languages", "Іноземні мови на робочому рівні"),
]

_EXPERIENCE = [
    ScaleSpec(ScaleFamily.EXPERIENCE, "employment_status", "Статус зайнятості", MappingStatus.MNP_ONLY, items=[
        ItemSpec("employment_status", "Який ваш поточний статус зайнятості?", ResponseType.SINGLE_CHOICE, reverse_exempt=True, options=[
            ItemOptionSpec("employed_full_time", "Працюю повний день"),
            ItemOptionSpec("employed_part_time", "Працюю неповний день"),
            ItemOptionSpec("unemployed", "Не працюю"),
            ItemOptionSpec("student", "Навчаюсь"),
            ItemOptionSpec("self_employed", "ФОП/самозайнятий(-а)"),
            ItemOptionSpec("on_leave", "У відпустці (декрет тощо)"),
        ]),
    ]),
    ScaleSpec(ScaleFamily.EXPERIENCE, "years_of_experience", "Досвід роботи", MappingStatus.MNP_ONLY, items=[
        ItemSpec("years_experience", "Скільки років загального досвіду роботи ви маєте?", ResponseType.SINGLE_CHOICE, reverse_exempt=True, options=[
            ItemOptionSpec("none", "Немає досвіду"),
            ItemOptionSpec("less_1", "Менше 1 року"),
            ItemOptionSpec("1_3", "1–3 роки"),
            ItemOptionSpec("3_5", "3–5 років"),
            ItemOptionSpec("5_10", "5–10 років"),
            ItemOptionSpec("10_plus", "Понад 10 років"),
        ]),
    ]),
    ScaleSpec(ScaleFamily.EXPERIENCE, "current_field", "Поточна сфера діяльності", MappingStatus.MNP_ONLY, items=[
        ItemSpec("current_field", "У якій сфері ви зараз працюєте або навчаєтесь (якщо застосовно)?",
                 ResponseType.SINGLE_CHOICE, reverse_exempt=True,
                 options=_CAREER_DOMAIN_OPTIONS + [ItemOptionSpec("not_applicable", "Не працюю і не навчаюсь")]),
    ]),
    ScaleSpec(ScaleFamily.EXPERIENCE, "known_skills", "Наявні навички", MappingStatus.MNP_ONLY, items=[
        ItemSpec("known_skills", "Які з наведених навичок ви маєте? (можна обрати кілька)",
                 ResponseType.MULTI_CHOICE, reverse_exempt=True, options=_KNOWN_SKILLS_OPTIONS),
    ]),
]

_SECTIONS: list[tuple[str, str, list[ScaleSpec]]] = [
    ("riasec", "Інтереси (RIASEC)", _RIASEC),
    ("work_style", "Стиль роботи", _WORK_STYLE),
    ("work_values", "Робочі цінності", _WORK_VALUES),
    ("work_environment", "Робоче середовище", _WORK_ENVIRONMENT),
    ("goals", "Цілі", _GOALS),
    ("constraints", "Обмеження", _CONSTRAINTS),
    ("experience", "Досвід і навички", _EXPERIENCE),
]


async def seed_alpha_long_form(session: AsyncSession) -> AssessmentDefinition:
    """Idempotent seed of the Matching V1 Alpha Long Form. Returns the
    existing definition unchanged if it already exists; otherwise creates
    it, its sections, its scales, its items, and (for choice items) their
    options, all in one call."""

    existing = await session.execute(
        select(AssessmentDefinition).where(AssessmentDefinition.assessment_version == ASSESSMENT_VERSION)
    )
    definition = existing.scalar_one_or_none()
    if definition is not None:
        return definition

    definition = AssessmentDefinition(
        assessment_version=ASSESSMENT_VERSION,
        mode=AssessmentMode.BASIC_STRUCTURED,
        methodology_version=METHODOLOGY_VERSION,
        title_uk="МОЖУ: Матчинг V1 — Альфа (довга форма)",
        description_uk="Структурований, повністю детермінований тест без участі ШІ (BASIC_STRUCTURED).",
        is_active=True,
    )
    session.add(definition)
    await session.flush()

    scale_cache: dict[tuple[ScaleFamily, str], AssessmentScale] = {}
    display_order = 0

    for section_index, (section_key, section_title, scale_specs) in enumerate(_SECTIONS):
        section = AssessmentSection(
            definition_id=definition.id, section_key=section_key, title_uk=section_title, display_order=section_index
        )
        session.add(section)
        await session.flush()

        for scale_spec in scale_specs:
            matching_usage = compute_matching_usage(scale_spec.mapping_status)
            provisional = (
                scale_spec.provisional_override
                if scale_spec.provisional_override is not None
                else scale_spec.mapping_status != MappingStatus.DIRECT
            )
            scale = AssessmentScale(
                scale_family=scale_spec.scale_family,
                scale_key=scale_spec.scale_key,
                label_uk=scale_spec.label_uk,
                mapping_status=scale_spec.mapping_status,
                matching_usage=matching_usage,
                source_system=scale_spec.source_system,
                source_element_id=scale_spec.source_element_id,
                source_element_name=scale_spec.source_element_name,
                source_version=scale_spec.source_version,
                transformation_version=scale_spec.transformation_version,
                provisional=provisional,
                methodology_version=METHODOLOGY_VERSION,
            )
            session.add(scale)
            await session.flush()
            scale_cache[(scale_spec.scale_family, scale_spec.scale_key)] = scale

            for item_spec in scale_spec.items:
                item = AssessmentItem(
                    definition_id=definition.id,
                    section_id=section.id,
                    scale_id=scale.id,
                    item_key=f"{section_key}_{scale_spec.scale_key}_{item_spec.key_suffix}",
                    scale_family=scale_spec.scale_family,
                    scale_key=scale_spec.scale_key,
                    subscale_key=None,
                    question_uk=item_spec.question_uk,
                    response_type=item_spec.response_type,
                    reverse_scored=item_spec.reverse_scored,
                    reverse_exempt=item_spec.reverse_exempt,
                    weight=1.0,
                    display_order=display_order,
                    required=True,
                    active=True,
                    profile_usage=True,
                    matching_usage=matching_usage,
                    source_reference=f"{SOURCE_DOC} / {MAPPING_DOC}",
                    methodology_version=METHODOLOGY_VERSION,
                )
                session.add(item)
                await session.flush()
                display_order += 1

                for option_index, option_spec in enumerate(item_spec.options):
                    session.add(
                        AssessmentItemOption(
                            item_id=item.id,
                            option_key=option_spec.key,
                            label_uk=option_spec.label_uk,
                            display_order=option_index,
                        )
                    )

    await session.flush()
    return definition
