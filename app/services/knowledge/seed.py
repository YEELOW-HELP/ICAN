"""Curated V1 seed for the Career Knowledge Base (brief §15/§26).

32 real, well-known professions -- 2 per `CareerDomain`, chosen for
structural diversity so Stage 3B's future ranking tests can detect an
obviously wrong recommendation (a desk-bound analytical role must not
score the same as manual field work). This is a **test fixture / initial
representative seed**, not a claim that the production corpus is limited
to these 32.

What is and isn't curated here, deliberately:
- `short_description`/`typical_activities`/structural characteristics/
  work context/skill relevance are curatorial, methodology-style
  judgments -- the same kind of content Stage 2 seeded into
  `TaxonomyTerm` without a citation per term. These are populated.
- `CareerRequirement` rows are all `certainty=TYPICAL_RECOMMENDATION`
  (never `HARD_FACTUAL`) and carry no `source_id` -- e.g. "a nursing
  license is typically required" is a reasonable general expectation to
  surface, but this seed cites no actual per-jurisdiction legal source,
  so it is never asserted as a verified fact (brief §9). The service
  layer (`careers.add_career_requirement`) would reject a `HARD_FACTUAL`
  entry without a source anyway -- this seed simply never attempts one.
- No `CareerFact` rows exist for salary, demand, growth, vacancy counts,
  or any other market-sensitive field anywhere in this seed (brief §20)
  -- omitted entirely rather than populated with a plausible-looking
  invented number.
"""

from __future__ import annotations

import uuid

from app.db.models_knowledge import (
    CareerDomain,
    IndoorOutdoor,
    KnowledgeBaseVersion,
    RelationType,
    RequirementCategory,
    RequirementCertainty,
    SkillRequirementType,
    TravelRequirement,
    WorkSetting,
)
from app.services.knowledge import careers as careers_service
from app.services.knowledge.skills import ensure_skills_taxonomy, get_skill_term_by_key
from app.services.knowledge.versioning import (
    create_draft_version,
    get_current_knowledge_version,
    list_knowledge_versions,
    publish_version,
)

REQUIRED = SkillRequirementType.REQUIRED
PREFERRED = SkillRequirementType.PREFERRED
USEFUL = SkillRequirementType.USEFUL
TYPICAL = RequirementCertainty.TYPICAL_RECOMMENDATION

# Each entry: code, uk/en titles, domain, description, activities,
# characteristics (0.0-1.0), work context, skills [(skill_key, req_type)],
# requirements [(category, description, jurisdiction)] -- all TYPICAL_RECOMMENDATION.
_CAREERS = [
    dict(
        code="software_developer", title_uk="Розробник програмного забезпечення", title_en="Software Developer",
        domain=CareerDomain.TECHNOLOGY,
        short_description="Проєктує, пише та підтримує програмний код для застосунків і систем.",
        typical_activities="Написання коду, тестування, налагодження, код-рев'ю, робота в команді за Agile-процесом.",
        characteristics=dict(works_with_people=0.3, works_with_data=0.7, works_with_technology=0.95, creative_component=0.6, analytical_component=0.9, autonomy_level=0.7, structure_routine_level=0.5),
        work_context=dict(setting=WorkSetting.MIXED, indoor_outdoor=IndoorOutdoor.INDOOR, travel_required=TravelRequirement.NONE, shift_work=False, physical_intensity=0.05, teamwork_level=0.6, customer_interaction_level=0.2, client_facing=False, repetitive_vs_varied=0.6, schedule_predictability=0.7, responsibility_level=0.6, stress_level=0.5),
        skills=[("programming", REQUIRED), ("problem_solving", REQUIRED), ("database_management", PREFERRED), ("teamwork", PREFERRED)],
        requirements=[(RequirementCategory.EDUCATION, "Диплом з комп'ютерних наук або еквівалентний практичний досвід зазвичай очікується.", None)],
    ),
    dict(
        code="it_support_specialist", title_uk="Спеціаліст технічної підтримки", title_en="IT Support Specialist",
        domain=CareerDomain.TECHNOLOGY,
        short_description="Допомагає користувачам вирішувати технічні проблеми з обладнанням і програмним забезпеченням.",
        typical_activities="Діагностика несправностей, консультування користувачів, налаштування техніки, ведення заявок.",
        characteristics=dict(works_with_people=0.6, works_with_data=0.4, works_with_technology=0.9, creative_component=0.2, analytical_component=0.6, autonomy_level=0.5, structure_routine_level=0.6),
        work_context=dict(setting=WorkSetting.OFFICE, indoor_outdoor=IndoorOutdoor.INDOOR, travel_required=TravelRequirement.OCCASIONAL, shift_work=False, physical_intensity=0.15, teamwork_level=0.5, customer_interaction_level=0.8, client_facing=True, repetitive_vs_varied=0.5, schedule_predictability=0.7, responsibility_level=0.4, stress_level=0.5),
        skills=[("it_troubleshooting", REQUIRED), ("communication", REQUIRED), ("customer_service_skill", PREFERRED)],
        requirements=[],
    ),
    dict(
        code="registered_nurse", title_uk="Медична сестра/медичний брат", title_en="Registered Nurse",
        domain=CareerDomain.HEALTHCARE,
        short_description="Надає догляд за пацієнтами, виконує медичні призначення та підтримує лікувальний процес.",
        typical_activities="Моніторинг стану пацієнтів, введення ліків, асистування лікарям, ведення медичної документації.",
        characteristics=dict(works_with_people=0.95, works_with_data=0.4, works_with_technology=0.4, creative_component=0.1, analytical_component=0.5, autonomy_level=0.4, structure_routine_level=0.4),
        work_context=dict(setting=WorkSetting.FIELD, indoor_outdoor=IndoorOutdoor.INDOOR, travel_required=TravelRequirement.NONE, shift_work=True, physical_intensity=0.6, teamwork_level=0.7, customer_interaction_level=0.9, client_facing=True, repetitive_vs_varied=0.5, schedule_predictability=0.4, responsibility_level=0.9, stress_level=0.8),
        skills=[("nursing_care", REQUIRED), ("communication", REQUIRED), ("attention_to_detail", REQUIRED)],
        requirements=[(RequirementCategory.EDUCATION, "Медична освіта (молодший спеціаліст/бакалавр сестринської справи) типово очікується.", "UA"), (RequirementCategory.LICENSE, "Професійна сертифікація/допуск до медичної практики типово потрібні.", "UA")],
    ),
    dict(
        code="pharmacist", title_uk="Фармацевт", title_en="Pharmacist",
        domain=CareerDomain.HEALTHCARE,
        short_description="Консультує щодо ліків, відпускає препарати та контролює їх правильне застосування.",
        typical_activities="Консультування клієнтів, перевірка рецептів, контроль запасів ліків, відпуск препаратів.",
        characteristics=dict(works_with_people=0.75, works_with_data=0.6, works_with_technology=0.4, creative_component=0.1, analytical_component=0.7, autonomy_level=0.5, structure_routine_level=0.4),
        work_context=dict(setting=WorkSetting.OFFICE, indoor_outdoor=IndoorOutdoor.INDOOR, travel_required=TravelRequirement.NONE, shift_work=True, physical_intensity=0.2, teamwork_level=0.4, customer_interaction_level=0.9, client_facing=True, repetitive_vs_varied=0.4, schedule_predictability=0.6, responsibility_level=0.85, stress_level=0.5),
        skills=[("pharmacology_knowledge", REQUIRED), ("communication", REQUIRED), ("attention_to_detail", REQUIRED)],
        requirements=[(RequirementCategory.EDUCATION, "Фармацевтична освіта типово очікується.", "UA"), (RequirementCategory.LICENSE, "Професійна ліцензія типово потрібна для практики.", "UA")],
    ),
    dict(
        code="civil_engineer", title_uk="Інженер-будівельник", title_en="Civil Engineer",
        domain=CareerDomain.ENGINEERING,
        short_description="Проєктує та контролює будівництво споруд, доріг та інфраструктурних об'єктів.",
        typical_activities="Розробка проєктної документації, розрахунки конструкцій, нагляд за будівництвом.",
        characteristics=dict(works_with_people=0.4, works_with_data=0.7, works_with_technology=0.7, creative_component=0.4, analytical_component=0.9, autonomy_level=0.6, structure_routine_level=0.4),
        work_context=dict(setting=WorkSetting.MIXED, indoor_outdoor=IndoorOutdoor.BOTH, travel_required=TravelRequirement.OCCASIONAL, shift_work=False, physical_intensity=0.3, teamwork_level=0.6, customer_interaction_level=0.4, client_facing=False, repetitive_vs_varied=0.5, schedule_predictability=0.6, responsibility_level=0.85, stress_level=0.6),
        skills=[("structural_analysis", REQUIRED), ("cad_design", REQUIRED), ("project_management", PREFERRED)],
        requirements=[(RequirementCategory.EDUCATION, "Інженерна освіта у будівельній галузі типово очікується.", "UA")],
    ),
    dict(
        code="mechanical_engineer", title_uk="Інженер-механік", title_en="Mechanical Engineer",
        domain=CareerDomain.ENGINEERING,
        short_description="Проєктує, аналізує та вдосконалює механічні системи й обладнання.",
        typical_activities="CAD-моделювання, розрахунки, тестування прототипів, супровід виробництва.",
        characteristics=dict(works_with_people=0.3, works_with_data=0.6, works_with_technology=0.85, creative_component=0.5, analytical_component=0.9, autonomy_level=0.6, structure_routine_level=0.4),
        work_context=dict(setting=WorkSetting.MIXED, indoor_outdoor=IndoorOutdoor.INDOOR, travel_required=TravelRequirement.OCCASIONAL, shift_work=False, physical_intensity=0.3, teamwork_level=0.5, customer_interaction_level=0.2, client_facing=False, repetitive_vs_varied=0.5, schedule_predictability=0.6, responsibility_level=0.7, stress_level=0.5),
        skills=[("cad_design", REQUIRED), ("problem_solving", REQUIRED), ("structural_analysis", PREFERRED)],
        requirements=[(RequirementCategory.EDUCATION, "Технічна/інженерна освіта типово очікується.", "UA")],
    ),
    dict(
        code="truck_driver", title_uk="Водій вантажівки", title_en="Truck Driver",
        domain=CareerDomain.LOGISTICS_TRANSPORT,
        short_description="Керує вантажним транспортом, перевозить вантажі на дальні або місцеві відстані.",
        typical_activities="Керування транспортом, перевірка вантажу, ведення дорожньої документації, дотримання маршруту.",
        characteristics=dict(works_with_people=0.2, works_with_data=0.1, works_with_technology=0.3, creative_component=0.05, analytical_component=0.2, autonomy_level=0.85, structure_routine_level=0.5),
        work_context=dict(setting=WorkSetting.FIELD, indoor_outdoor=IndoorOutdoor.BOTH, travel_required=TravelRequirement.FREQUENT, shift_work=True, physical_intensity=0.5, teamwork_level=0.15, customer_interaction_level=0.2, client_facing=False, repetitive_vs_varied=0.4, schedule_predictability=0.5, responsibility_level=0.7, stress_level=0.5),
        skills=[("vehicle_operation", REQUIRED), ("physical_stamina", PREFERRED)],
        requirements=[(RequirementCategory.LICENSE, "Відповідна категорія водійського посвідчення типово потрібна.", "UA"), (RequirementCategory.PHYSICAL_ENVIRONMENTAL, "Тривале перебування за кермом, можливі нічні зміни.", None)],
    ),
    dict(
        code="logistics_coordinator", title_uk="Логістичний координатор", title_en="Logistics Coordinator",
        domain=CareerDomain.LOGISTICS_TRANSPORT,
        short_description="Планує та координує переміщення вантажів, взаємодіє з перевізниками і складами.",
        typical_activities="Планування маршрутів, координація з перевізниками, відстеження поставок, документообіг.",
        characteristics=dict(works_with_people=0.6, works_with_data=0.7, works_with_technology=0.5, creative_component=0.2, analytical_component=0.6, autonomy_level=0.5, structure_routine_level=0.5),
        work_context=dict(setting=WorkSetting.OFFICE, indoor_outdoor=IndoorOutdoor.INDOOR, travel_required=TravelRequirement.NONE, shift_work=False, physical_intensity=0.1, teamwork_level=0.6, customer_interaction_level=0.6, client_facing=True, repetitive_vs_varied=0.5, schedule_predictability=0.6, responsibility_level=0.65, stress_level=0.6),
        skills=[("logistics_planning", REQUIRED), ("inventory_management", PREFERRED), ("communication", REQUIRED)],
        requirements=[],
    ),
    dict(
        code="electrician", title_uk="Електрик", title_en="Electrician",
        domain=CareerDomain.SKILLED_TRADES,
        short_description="Монтує, обслуговує та ремонтує електричні системи й обладнання.",
        typical_activities="Прокладання проводки, діагностика несправностей, підключення обладнання, дотримання техніки безпеки.",
        characteristics=dict(works_with_people=0.25, works_with_data=0.1, works_with_technology=0.6, creative_component=0.15, analytical_component=0.5, autonomy_level=0.6, structure_routine_level=0.4),
        work_context=dict(setting=WorkSetting.FIELD, indoor_outdoor=IndoorOutdoor.BOTH, travel_required=TravelRequirement.OCCASIONAL, shift_work=False, physical_intensity=0.7, teamwork_level=0.3, customer_interaction_level=0.4, client_facing=True, repetitive_vs_varied=0.5, schedule_predictability=0.5, responsibility_level=0.7, stress_level=0.5),
        skills=[("electrical_systems", REQUIRED), ("attention_to_detail", REQUIRED), ("physical_stamina", PREFERRED)],
        requirements=[(RequirementCategory.CERTIFICATION, "Кваліфікаційний допуск з електробезпеки типово потрібен.", "UA"), (RequirementCategory.PHYSICAL_ENVIRONMENTAL, "Робота на висоті або в обмеженому просторі можлива.", None)],
    ),
    dict(
        code="plumber", title_uk="Сантехнік", title_en="Plumber",
        domain=CareerDomain.SKILLED_TRADES,
        short_description="Монтує та ремонтує системи водопостачання, опалення та каналізації.",
        typical_activities="Встановлення труб і арматури, усунення протікань, обслуговування систем опалення.",
        characteristics=dict(works_with_people=0.3, works_with_data=0.05, works_with_technology=0.4, creative_component=0.1, analytical_component=0.4, autonomy_level=0.65, structure_routine_level=0.4),
        work_context=dict(setting=WorkSetting.FIELD, indoor_outdoor=IndoorOutdoor.BOTH, travel_required=TravelRequirement.OCCASIONAL, shift_work=False, physical_intensity=0.75, teamwork_level=0.25, customer_interaction_level=0.5, client_facing=True, repetitive_vs_varied=0.5, schedule_predictability=0.5, responsibility_level=0.6, stress_level=0.5),
        skills=[("plumbing_systems", REQUIRED), ("physical_stamina", PREFERRED), ("problem_solving", PREFERRED)],
        requirements=[(RequirementCategory.PHYSICAL_ENVIRONMENTAL, "Робота в обмеженому просторі, контакт з водою можливі.", None)],
    ),
    dict(
        code="sales_manager", title_uk="Менеджер з продажів", title_en="Sales Manager",
        domain=CareerDomain.SALES,
        short_description="Керує процесом продажів, розвиває клієнтську базу та досягає планових показників.",
        typical_activities="Переговори з клієнтами, укладання угод, розвиток команди продажів, аналіз показників.",
        characteristics=dict(works_with_people=0.9, works_with_data=0.5, works_with_technology=0.3, creative_component=0.3, analytical_component=0.5, autonomy_level=0.6, structure_routine_level=0.5),
        work_context=dict(setting=WorkSetting.MIXED, indoor_outdoor=IndoorOutdoor.INDOOR, travel_required=TravelRequirement.OCCASIONAL, shift_work=False, physical_intensity=0.1, teamwork_level=0.6, customer_interaction_level=0.95, client_facing=True, repetitive_vs_varied=0.6, schedule_predictability=0.4, responsibility_level=0.7, stress_level=0.75),
        skills=[("sales_technique", REQUIRED), ("leadership", PREFERRED), ("communication", REQUIRED)],
        requirements=[],
    ),
    dict(
        code="retail_sales_associate", title_uk="Продавець-консультант", title_en="Retail Sales Associate",
        domain=CareerDomain.SALES,
        short_description="Консультує покупців у торговому залі та здійснює продаж товарів.",
        typical_activities="Консультування клієнтів, викладка товару, оформлення продажу, робота з касою.",
        characteristics=dict(works_with_people=0.85, works_with_data=0.1, works_with_technology=0.2, creative_component=0.15, analytical_component=0.2, autonomy_level=0.3, structure_routine_level=0.5),
        work_context=dict(setting=WorkSetting.FIELD, indoor_outdoor=IndoorOutdoor.INDOOR, travel_required=TravelRequirement.NONE, shift_work=True, physical_intensity=0.4, teamwork_level=0.5, customer_interaction_level=0.95, client_facing=True, repetitive_vs_varied=0.4, schedule_predictability=0.5, responsibility_level=0.4, stress_level=0.5),
        skills=[("customer_service_skill", REQUIRED), ("sales_technique", PREFERRED), ("communication", REQUIRED)],
        requirements=[],
    ),
    dict(
        code="customer_service_representative", title_uk="Спеціаліст з обслуговування клієнтів", title_en="Customer Service Representative",
        domain=CareerDomain.CUSTOMER_SERVICE,
        short_description="Відповідає на запити клієнтів та вирішує їхні проблеми через різні канали зв'язку.",
        typical_activities="Обробка звернень, консультування, ведення записів у CRM, ескалація складних випадків.",
        characteristics=dict(works_with_people=0.9, works_with_data=0.3, works_with_technology=0.4, creative_component=0.15, analytical_component=0.3, autonomy_level=0.3, structure_routine_level=0.6),
        work_context=dict(setting=WorkSetting.OFFICE, indoor_outdoor=IndoorOutdoor.INDOOR, travel_required=TravelRequirement.NONE, shift_work=True, physical_intensity=0.1, teamwork_level=0.4, customer_interaction_level=0.95, client_facing=True, repetitive_vs_varied=0.35, schedule_predictability=0.5, responsibility_level=0.4, stress_level=0.6),
        skills=[("customer_service_skill", REQUIRED), ("communication", REQUIRED)],
        requirements=[],
    ),
    dict(
        code="call_center_operator", title_uk="Оператор кол-центру", title_en="Call Center Operator",
        domain=CareerDomain.CUSTOMER_SERVICE,
        short_description="Обробляє вхідні та вихідні дзвінки за встановленими скриптами й процедурами.",
        typical_activities="Прийом дзвінків, консультування за скриптом, фіксація результатів у системі.",
        characteristics=dict(works_with_people=0.85, works_with_data=0.2, works_with_technology=0.4, creative_component=0.1, analytical_component=0.2, autonomy_level=0.2, structure_routine_level=0.7),
        work_context=dict(setting=WorkSetting.OFFICE, indoor_outdoor=IndoorOutdoor.INDOOR, travel_required=TravelRequirement.NONE, shift_work=True, physical_intensity=0.05, teamwork_level=0.3, customer_interaction_level=0.9, client_facing=True, repetitive_vs_varied=0.2, schedule_predictability=0.6, responsibility_level=0.3, stress_level=0.65),
        skills=[("communication", REQUIRED), ("customer_service_skill", REQUIRED)],
        requirements=[],
    ),
    dict(
        code="operations_manager", title_uk="Операційний менеджер", title_en="Operations Manager",
        domain=CareerDomain.MANAGEMENT,
        short_description="Керує щоденними операційними процесами компанії або підрозділу.",
        typical_activities="Планування процесів, контроль показників, координація команд, оптимізація витрат.",
        characteristics=dict(works_with_people=0.75, works_with_data=0.7, works_with_technology=0.4, creative_component=0.3, analytical_component=0.75, autonomy_level=0.7, structure_routine_level=0.5),
        work_context=dict(setting=WorkSetting.OFFICE, indoor_outdoor=IndoorOutdoor.INDOOR, travel_required=TravelRequirement.OCCASIONAL, shift_work=False, physical_intensity=0.1, teamwork_level=0.6, customer_interaction_level=0.4, client_facing=False, repetitive_vs_varied=0.6, schedule_predictability=0.5, responsibility_level=0.9, stress_level=0.75),
        skills=[("leadership", REQUIRED), ("project_management", REQUIRED)],
        requirements=[],
    ),
    dict(
        code="project_manager", title_uk="Проєктний менеджер", title_en="Project Manager",
        domain=CareerDomain.MANAGEMENT,
        short_description="Планує, координує та контролює виконання проєктів у визначені терміни й бюджет.",
        typical_activities="Планування етапів, координація команди, контроль ризиків, звітність перед стейкхолдерами.",
        characteristics=dict(works_with_people=0.8, works_with_data=0.6, works_with_technology=0.4, creative_component=0.3, analytical_component=0.65, autonomy_level=0.65, structure_routine_level=0.5),
        work_context=dict(setting=WorkSetting.MIXED, indoor_outdoor=IndoorOutdoor.INDOOR, travel_required=TravelRequirement.OCCASIONAL, shift_work=False, physical_intensity=0.05, teamwork_level=0.75, customer_interaction_level=0.5, client_facing=True, repetitive_vs_varied=0.6, schedule_predictability=0.4, responsibility_level=0.85, stress_level=0.7),
        skills=[("project_management", REQUIRED), ("leadership", PREFERRED), ("communication", REQUIRED)],
        requirements=[],
    ),
    dict(
        code="accountant", title_uk="Бухгалтер", title_en="Accountant",
        domain=CareerDomain.FINANCE,
        short_description="Веде фінансовий облік підприємства, готує звітність та контролює платежі.",
        typical_activities="Ведення бухгалтерських записів, підготовка звітів, розрахунок податків, звірка платежів.",
        characteristics=dict(works_with_people=0.3, works_with_data=0.9, works_with_technology=0.5, creative_component=0.05, analytical_component=0.85, autonomy_level=0.5, structure_routine_level=0.3),
        work_context=dict(setting=WorkSetting.OFFICE, indoor_outdoor=IndoorOutdoor.INDOOR, travel_required=TravelRequirement.NONE, shift_work=False, physical_intensity=0.05, teamwork_level=0.35, customer_interaction_level=0.2, client_facing=False, repetitive_vs_varied=0.3, schedule_predictability=0.7, responsibility_level=0.85, stress_level=0.6),
        skills=[("accounting_principles", REQUIRED), ("attention_to_detail", REQUIRED)],
        requirements=[(RequirementCategory.EDUCATION, "Освіта у сфері обліку/фінансів типово очікується.", "UA")],
    ),
    dict(
        code="financial_analyst", title_uk="Фінансовий аналітик", title_en="Financial Analyst",
        domain=CareerDomain.FINANCE,
        short_description="Аналізує фінансові показники та готує рекомендації для управлінських рішень.",
        typical_activities="Побудова фінансових моделей, аналіз звітності, підготовка презентацій для керівництва.",
        characteristics=dict(works_with_people=0.4, works_with_data=0.95, works_with_technology=0.5, creative_component=0.2, analytical_component=0.95, autonomy_level=0.6, structure_routine_level=0.4),
        work_context=dict(setting=WorkSetting.OFFICE, indoor_outdoor=IndoorOutdoor.INDOOR, travel_required=TravelRequirement.NONE, shift_work=False, physical_intensity=0.05, teamwork_level=0.4, customer_interaction_level=0.2, client_facing=False, repetitive_vs_varied=0.5, schedule_predictability=0.6, responsibility_level=0.75, stress_level=0.65),
        skills=[("financial_analysis", REQUIRED), ("attention_to_detail", PREFERRED)],
        requirements=[(RequirementCategory.EDUCATION, "Освіта у сфері фінансів/економіки типово очікується.", "UA")],
    ),
    dict(
        code="school_teacher", title_uk="Вчитель", title_en="School Teacher",
        domain=CareerDomain.EDUCATION,
        short_description="Навчає учнів за визначеною програмою, оцінює їхній прогрес.",
        typical_activities="Проведення уроків, підготовка матеріалів, оцінювання, спілкування з батьками.",
        characteristics=dict(works_with_people=0.9, works_with_data=0.2, works_with_technology=0.3, creative_component=0.5, analytical_component=0.4, autonomy_level=0.6, structure_routine_level=0.4),
        work_context=dict(setting=WorkSetting.OFFICE, indoor_outdoor=IndoorOutdoor.INDOOR, travel_required=TravelRequirement.NONE, shift_work=False, physical_intensity=0.2, teamwork_level=0.5, customer_interaction_level=0.85, client_facing=True, repetitive_vs_varied=0.5, schedule_predictability=0.7, responsibility_level=0.8, stress_level=0.65),
        skills=[("teaching_pedagogy", REQUIRED), ("communication", REQUIRED), ("curriculum_design", PREFERRED)],
        requirements=[(RequirementCategory.EDUCATION, "Педагогічна освіта типово очікується.", "UA")],
    ),
    dict(
        code="corporate_trainer", title_uk="Корпоративний тренер", title_en="Corporate Trainer",
        domain=CareerDomain.EDUCATION,
        short_description="Розробляє та проводить навчальні програми для співробітників компанії.",
        typical_activities="Розробка навчальних матеріалів, проведення тренінгів, оцінка ефективності навчання.",
        characteristics=dict(works_with_people=0.85, works_with_data=0.3, works_with_technology=0.3, creative_component=0.55, analytical_component=0.4, autonomy_level=0.65, structure_routine_level=0.5),
        work_context=dict(setting=WorkSetting.MIXED, indoor_outdoor=IndoorOutdoor.INDOOR, travel_required=TravelRequirement.OCCASIONAL, shift_work=False, physical_intensity=0.15, teamwork_level=0.5, customer_interaction_level=0.8, client_facing=True, repetitive_vs_varied=0.55, schedule_predictability=0.6, responsibility_level=0.6, stress_level=0.5),
        skills=[("teaching_pedagogy", REQUIRED), ("curriculum_design", REQUIRED), ("communication", REQUIRED)],
        requirements=[],
    ),
    dict(
        code="graphic_designer", title_uk="Графічний дизайнер", title_en="Graphic Designer",
        domain=CareerDomain.CREATIVE,
        short_description="Створює візуальні матеріали для брендів, друку та цифрових каналів.",
        typical_activities="Розробка макетів, робота з клієнтським брифом, підготовка файлів до друку/публікації.",
        characteristics=dict(works_with_people=0.4, works_with_data=0.2, works_with_technology=0.6, creative_component=0.95, analytical_component=0.3, autonomy_level=0.75, structure_routine_level=0.6),
        work_context=dict(setting=WorkSetting.REMOTE, indoor_outdoor=IndoorOutdoor.INDOOR, travel_required=TravelRequirement.NONE, shift_work=False, physical_intensity=0.05, teamwork_level=0.4, customer_interaction_level=0.5, client_facing=True, repetitive_vs_varied=0.7, schedule_predictability=0.5, responsibility_level=0.5, stress_level=0.5),
        skills=[("graphic_design_tools", REQUIRED), ("content_writing", USEFUL)],
        requirements=[(RequirementCategory.PORTFOLIO, "Портфоліо робіт типово очікується роботодавцями.", None)],
    ),
    dict(
        code="video_editor", title_uk="Відеомонтажер", title_en="Video Editor",
        domain=CareerDomain.CREATIVE,
        short_description="Монтує відеоматеріали для реклами, соціальних мереж або медіа.",
        typical_activities="Монтаж відео, кольорокорекція, звукове оформлення, підготовка до публікації.",
        characteristics=dict(works_with_people=0.3, works_with_data=0.2, works_with_technology=0.7, creative_component=0.9, analytical_component=0.3, autonomy_level=0.75, structure_routine_level=0.6),
        work_context=dict(setting=WorkSetting.REMOTE, indoor_outdoor=IndoorOutdoor.INDOOR, travel_required=TravelRequirement.NONE, shift_work=False, physical_intensity=0.05, teamwork_level=0.3, customer_interaction_level=0.3, client_facing=False, repetitive_vs_varied=0.6, schedule_predictability=0.5, responsibility_level=0.4, stress_level=0.5),
        skills=[("video_editing_tools", REQUIRED)],
        requirements=[(RequirementCategory.PORTFOLIO, "Портфоліо робіт типово очікується роботодавцями.", None)],
    ),
    dict(
        code="marketing_specialist", title_uk="Маркетолог", title_en="Marketing Specialist",
        domain=CareerDomain.MARKETING,
        short_description="Розробляє та реалізує маркетингові кампанії для просування продуктів чи послуг.",
        typical_activities="Планування кампаній, аналіз ринку, координація з рекламними каналами, звітність.",
        characteristics=dict(works_with_people=0.6, works_with_data=0.6, works_with_technology=0.5, creative_component=0.6, analytical_component=0.6, autonomy_level=0.6, structure_routine_level=0.55),
        work_context=dict(setting=WorkSetting.MIXED, indoor_outdoor=IndoorOutdoor.INDOOR, travel_required=TravelRequirement.NONE, shift_work=False, physical_intensity=0.05, teamwork_level=0.55, customer_interaction_level=0.4, client_facing=False, repetitive_vs_varied=0.6, schedule_predictability=0.5, responsibility_level=0.6, stress_level=0.55),
        skills=[("social_media_management", PREFERRED), ("content_writing", PREFERRED), ("communication", REQUIRED)],
        requirements=[],
    ),
    dict(
        code="social_media_manager", title_uk="Менеджер із соціальних мереж", title_en="Social Media Manager",
        domain=CareerDomain.MARKETING,
        short_description="Веде акаунти бренду в соціальних мережах, планує контент і взаємодіє з аудиторією.",
        typical_activities="Планування контент-плану, публікація постів, аналітика залучення, комунікація з підписниками.",
        characteristics=dict(works_with_people=0.6, works_with_data=0.4, works_with_technology=0.55, creative_component=0.7, analytical_component=0.4, autonomy_level=0.7, structure_routine_level=0.55),
        work_context=dict(setting=WorkSetting.REMOTE, indoor_outdoor=IndoorOutdoor.INDOOR, travel_required=TravelRequirement.NONE, shift_work=False, physical_intensity=0.05, teamwork_level=0.4, customer_interaction_level=0.6, client_facing=True, repetitive_vs_varied=0.6, schedule_predictability=0.5, responsibility_level=0.5, stress_level=0.55),
        skills=[("social_media_management", REQUIRED), ("content_writing", REQUIRED)],
        requirements=[],
    ),
    dict(
        code="social_worker", title_uk="Соціальний працівник", title_en="Social Worker",
        domain=CareerDomain.SOCIAL_SECTOR,
        short_description="Надає підтримку вразливим групам населення та координує соціальну допомогу.",
        typical_activities="Оцінка потреб клієнтів, ведення справ, взаємодія з соціальними службами, кризове консультування.",
        characteristics=dict(works_with_people=0.95, works_with_data=0.3, works_with_technology=0.2, creative_component=0.2, analytical_component=0.4, autonomy_level=0.5, structure_routine_level=0.4),
        work_context=dict(setting=WorkSetting.FIELD, indoor_outdoor=IndoorOutdoor.BOTH, travel_required=TravelRequirement.OCCASIONAL, shift_work=False, physical_intensity=0.25, teamwork_level=0.6, customer_interaction_level=0.9, client_facing=True, repetitive_vs_varied=0.5, schedule_predictability=0.4, responsibility_level=0.85, stress_level=0.8),
        skills=[("social_work_practice", REQUIRED), ("community_engagement", PREFERRED), ("communication", REQUIRED)],
        requirements=[(RequirementCategory.EDUCATION, "Освіта у сфері соціальної роботи типово очікується.", "UA")],
    ),
    dict(
        code="community_outreach_coordinator", title_uk="Координатор громадських програм", title_en="Community Outreach Coordinator",
        domain=CareerDomain.SOCIAL_SECTOR,
        short_description="Організовує програми та заходи для взаємодії з місцевою громадою.",
        typical_activities="Планування заходів, залучення партнерів, координація волонтерів, звітність перед донорами.",
        characteristics=dict(works_with_people=0.9, works_with_data=0.3, works_with_technology=0.2, creative_component=0.4, analytical_component=0.3, autonomy_level=0.6, structure_routine_level=0.55),
        work_context=dict(setting=WorkSetting.MIXED, indoor_outdoor=IndoorOutdoor.BOTH, travel_required=TravelRequirement.OCCASIONAL, shift_work=False, physical_intensity=0.2, teamwork_level=0.65, customer_interaction_level=0.85, client_facing=True, repetitive_vs_varied=0.6, schedule_predictability=0.5, responsibility_level=0.6, stress_level=0.55),
        skills=[("community_engagement", REQUIRED), ("communication", REQUIRED)],
        requirements=[],
    ),
    dict(
        code="administrative_assistant", title_uk="Адміністративний асистент", title_en="Administrative Assistant",
        domain=CareerDomain.ADMINISTRATION,
        short_description="Забезпечує адміністративну підтримку офісу та керівництва.",
        typical_activities="Ведення документообігу, планування зустрічей, відповіді на запити, організація офісних процесів.",
        characteristics=dict(works_with_people=0.6, works_with_data=0.5, works_with_technology=0.4, creative_component=0.1, analytical_component=0.3, autonomy_level=0.4, structure_routine_level=0.6),
        work_context=dict(setting=WorkSetting.OFFICE, indoor_outdoor=IndoorOutdoor.INDOOR, travel_required=TravelRequirement.NONE, shift_work=False, physical_intensity=0.05, teamwork_level=0.5, customer_interaction_level=0.5, client_facing=False, repetitive_vs_varied=0.4, schedule_predictability=0.7, responsibility_level=0.5, stress_level=0.45),
        skills=[("administrative_organization", REQUIRED), ("office_software", REQUIRED)],
        requirements=[],
    ),
    dict(
        code="office_manager", title_uk="Офіс-менеджер", title_en="Office Manager",
        domain=CareerDomain.ADMINISTRATION,
        short_description="Керує адміністративними процесами та ресурсами офісу.",
        typical_activities="Координація постачальників, контроль бюджету офісу, організація заходів, підтримка персоналу.",
        characteristics=dict(works_with_people=0.7, works_with_data=0.5, works_with_technology=0.4, creative_component=0.2, analytical_component=0.4, autonomy_level=0.6, structure_routine_level=0.55),
        work_context=dict(setting=WorkSetting.OFFICE, indoor_outdoor=IndoorOutdoor.INDOOR, travel_required=TravelRequirement.NONE, shift_work=False, physical_intensity=0.05, teamwork_level=0.55, customer_interaction_level=0.5, client_facing=False, repetitive_vs_varied=0.5, schedule_predictability=0.65, responsibility_level=0.65, stress_level=0.5),
        skills=[("administrative_organization", REQUIRED), ("leadership", USEFUL)],
        requirements=[],
    ),
    dict(
        code="hotel_receptionist", title_uk="Адміністратор готелю", title_en="Hotel Receptionist",
        domain=CareerDomain.HOSPITALITY_SERVICE,
        short_description="Зустрічає гостей готелю, здійснює заселення/виселення та вирішує запити гостей.",
        typical_activities="Реєстрація гостей, обробка бронювань, консультування щодо послуг готелю.",
        characteristics=dict(works_with_people=0.9, works_with_data=0.3, works_with_technology=0.3, creative_component=0.1, analytical_component=0.2, autonomy_level=0.3, structure_routine_level=0.6),
        work_context=dict(setting=WorkSetting.OFFICE, indoor_outdoor=IndoorOutdoor.INDOOR, travel_required=TravelRequirement.NONE, shift_work=True, physical_intensity=0.2, teamwork_level=0.5, customer_interaction_level=0.95, client_facing=True, repetitive_vs_varied=0.4, schedule_predictability=0.5, responsibility_level=0.5, stress_level=0.55),
        skills=[("hospitality_service_skill", REQUIRED), ("communication", REQUIRED)],
        requirements=[],
    ),
    dict(
        code="chef_cook", title_uk="Кухар", title_en="Chef / Cook",
        domain=CareerDomain.HOSPITALITY_SERVICE,
        short_description="Готує страви за рецептурою в закладах харчування.",
        typical_activities="Приготування страв, контроль якості продуктів, дотримання санітарних норм, робота в команді кухні.",
        characteristics=dict(works_with_people=0.4, works_with_data=0.1, works_with_technology=0.2, creative_component=0.6, analytical_component=0.2, autonomy_level=0.4, structure_routine_level=0.5),
        work_context=dict(setting=WorkSetting.FIELD, indoor_outdoor=IndoorOutdoor.INDOOR, travel_required=TravelRequirement.NONE, shift_work=True, physical_intensity=0.75, teamwork_level=0.7, customer_interaction_level=0.15, client_facing=False, repetitive_vs_varied=0.5, schedule_predictability=0.4, responsibility_level=0.6, stress_level=0.75),
        skills=[("culinary_skills", REQUIRED), ("teamwork", PREFERRED)],
        requirements=[(RequirementCategory.PHYSICAL_ENVIRONMENTAL, "Тривале перебування на ногах, робота в умовах спеки на кухні.", None)],
    ),
    dict(
        code="production_line_operator", title_uk="Оператор виробничої лінії", title_en="Production Line Operator",
        domain=CareerDomain.MANUFACTURING,
        short_description="Обслуговує обладнання виробничої лінії та контролює процес виробництва.",
        typical_activities="Керування обладнанням, контроль якості продукції, усунення дрібних несправностей.",
        characteristics=dict(works_with_people=0.3, works_with_data=0.1, works_with_technology=0.5, creative_component=0.05, analytical_component=0.25, autonomy_level=0.3, structure_routine_level=0.2),
        work_context=dict(setting=WorkSetting.FIELD, indoor_outdoor=IndoorOutdoor.INDOOR, travel_required=TravelRequirement.NONE, shift_work=True, physical_intensity=0.7, teamwork_level=0.5, customer_interaction_level=0.05, client_facing=False, repetitive_vs_varied=0.15, schedule_predictability=0.6, responsibility_level=0.5, stress_level=0.5),
        skills=[("manufacturing_operations", REQUIRED), ("attention_to_detail", PREFERRED)],
        requirements=[(RequirementCategory.PHYSICAL_ENVIRONMENTAL, "Тривале перебування на ногах, робота з виробничим обладнанням.", None)],
    ),
    dict(
        code="quality_control_inspector", title_uk="Інспектор з контролю якості", title_en="Quality Control Inspector",
        domain=CareerDomain.MANUFACTURING,
        short_description="Перевіряє відповідність продукції встановленим стандартам якості.",
        typical_activities="Візуальний і вимірювальний контроль продукції, ведення протоколів невідповідностей.",
        characteristics=dict(works_with_people=0.3, works_with_data=0.4, works_with_technology=0.4, creative_component=0.05, analytical_component=0.6, autonomy_level=0.4, structure_routine_level=0.25),
        work_context=dict(setting=WorkSetting.FIELD, indoor_outdoor=IndoorOutdoor.INDOOR, travel_required=TravelRequirement.NONE, shift_work=True, physical_intensity=0.4, teamwork_level=0.4, customer_interaction_level=0.1, client_facing=False, repetitive_vs_varied=0.3, schedule_predictability=0.65, responsibility_level=0.7, stress_level=0.5),
        skills=[("quality_control_inspection", REQUIRED), ("attention_to_detail", REQUIRED)],
        requirements=[],
    ),
]

# (from_code, to_code, relation_type) -- a small, illustrative set, not a full graph.
_RELATIONS = [
    ("it_support_specialist", "software_developer", RelationType.TRANSITION_POSSIBLE_TO),
    ("retail_sales_associate", "sales_manager", RelationType.PROGRESSION_TO),
    ("sales_manager", "operations_manager", RelationType.PROGRESSION_TO),
    ("accountant", "financial_analyst", RelationType.PROGRESSION_TO),
    ("customer_service_representative", "call_center_operator", RelationType.RELATED_TO),
    ("electrician", "plumber", RelationType.ADJACENT_TO),
    ("civil_engineer", "mechanical_engineer", RelationType.RELATED_TO),
    ("administrative_assistant", "office_manager", RelationType.PROGRESSION_TO),
    ("marketing_specialist", "social_media_manager", RelationType.ADJACENT_TO),
    ("project_manager", "operations_manager", RelationType.RELATED_TO),
    ("school_teacher", "corporate_trainer", RelationType.TRANSITION_POSSIBLE_TO),
    ("graphic_designer", "video_editor", RelationType.ADJACENT_TO),
]

SEED_SOURCE_NOTES = (
    "Stage 3A initial curated seed (docs/engineering/16_..._KNOWLEDGE_BASE_IMPLEMENTATION.md). "
    "Structural/classification fields only -- no market-sensitive data included."
)


async def ensure_seed_knowledge_base(session):
    """Idempotent: if any KnowledgeBaseVersion already exists, returns the
    current one without creating a duplicate. Otherwise builds and
    publishes v1 with the full curated seed."""
    existing_versions = await list_knowledge_versions(session)
    if existing_versions:
        return await get_current_knowledge_version(session)

    skills_taxonomy_version = await ensure_skills_taxonomy(session)
    draft = await create_draft_version(session, notes=SEED_SOURCE_NOTES)

    codes_to_ids: dict[str, uuid.UUID] = {}
    for entry in _CAREERS:
        career = await careers_service.create_career(
            session,
            knowledge_base_version_id=draft.id,
            code=entry["code"],
            title_uk=entry["title_uk"],
            title_en=entry["title_en"],
            domain=entry["domain"],
            short_description=entry["short_description"],
            typical_activities=entry["typical_activities"],
            **entry["characteristics"],
        )
        codes_to_ids[entry["code"]] = career.id

        await careers_service.add_career_alias(session, career_id=career.id, alias_text=entry["title_uk"], locale="uk")
        if entry["title_en"]:
            await careers_service.add_career_alias(session, career_id=career.id, alias_text=entry["title_en"], locale="en")

        await careers_service.set_career_work_context(session, career_id=career.id, **entry["work_context"])

        for skill_key, requirement_type in entry["skills"]:
            skill_term = await get_skill_term_by_key(
                session, taxonomy_version_id=skills_taxonomy_version.id, term_key=skill_key
            )
            if skill_term is None:
                continue
            await careers_service.add_career_skill(
                session, career_id=career.id, skill_term_id=skill_term.id, requirement_type=requirement_type
            )

        for category, description, jurisdiction in entry["requirements"]:
            await careers_service.add_career_requirement(
                session, career_id=career.id, category=category, description=description,
                certainty=TYPICAL, jurisdiction=jurisdiction,
            )

    for from_code, to_code, relation_type in _RELATIONS:
        await careers_service.add_career_relation(
            session, from_career_id=codes_to_ids[from_code], to_career_id=codes_to_ids[to_code],
            relation_type=relation_type,
        )

    published = await publish_version(session, draft.id)
    return published
