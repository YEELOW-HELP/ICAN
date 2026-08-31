# MNP_CAREER_PROFILE_SCHEMA_V1

**Продукт:** МОЖУ: Мій Напрям  
**Версия:** 1.0  
**Статус:** Draft for Founder Approval  
**Дата:** 2026-08-29  
**Зависимости:** MNP_METHODOLOGY_V1, MNP_DATA_MODEL_V1, MNP_SKILL_SCHEMA_V1

## 1. Цель

Career Profile — стандартизированный цифровой паспорт профессии, с которым Matching Engine сравнивает Career Card человека.

`PERSON PROFILE ↔ CAREER PROFILE`

Career Profile описывает не вакансию и не красивую статью о профессии, а структурированную модель:
- что человек делает;
- что должен уметь и знать;
- какой опыт/образование/credentials нужны;
- в какой среде работает;
- какие входные барьеры существуют;
- что происходит с профессией на украинском рынке;
- какие переходы к ней реалистичны.

## 2. Founder decisions incorporated

- V1 = 50 активных профессий.
- Career KB — отдельный управляемый модуль.
- Профессии можно добавлять, обновлять, архивировать.
- Review ориентировочно ежемесячный.
- MNP Career ID — собственный.
- UK + EN canonical names.
- ESCO/O*NET используются как open foundation/mappings.
- Lightcast не используется.
- Numeric Match Score пользователю не показывается.
- Career Profile и Market Snapshot разделены.

## 3. Career Identity

Обязательные поля:

- `id`: MNP_CAREER_ID
- `canonical_name_uk`
- `canonical_name_en`
- `description_short_uk`
- `career_family_id`
- `status`: DRAFT | ACTIVE | ARCHIVED
- `catalog_priority`
- `career_profile_version`
- `published_at`
- `reviewed_at`
- `next_review_at`

Optional:
- description_long_uk
- canonical_name_variants
- icon/media refs
- editorial notes

## 4. Career Alias

Для нормализации рынка и CV:

- career_id
- alias
- language
- source
- alias_type
- confidence
- status

Примеры:
`Менеджер з продажу`
`Sales Manager`
`B2B Sales Manager`
`Менеджер по роботі з клієнтами`

Alias не создаёт новую Career автоматически.

## 5. Career Family

Career Family группирует профессии по близкой функциональной природе.

Примеры V1:
- Sales & Business Development
- Customer Success & Service
- Operations
- Project & Product
- Finance
- HR & Recruiting
- Marketing & Communications
- Data & Analytics
- IT & Digital
- Engineering & Technical
- Logistics & Supply Chain
- Healthcare
- Administration
- Skilled Trades / Production

Family используется для навигации и transition logic, но не определяет match сама по себе.

## 6. Career Summary

Для UI:
- что делает специалист;
- типичные задачи;
- где работает;
- кому подходит переход;
- entry routes;
- перспективы.

Summary — editorial layer. Matching Engine не должен зависеть от marketing text.

## 7. Tasks

`CareerTask`:
- career_id
- task_code
- title_uk
- title_en optional
- description
- importance
- frequency optional
- source
- source_version
- confidence

Tasks помогают:
- Experience Transfer;
- объяснению профессии;
- сравнению прошлого опыта с target career.

## 8. Skills

`CareerSkillRequirement`:
- career_id
- MNP_SKILL_ID
- importance
- required_level: BASIC | WORKING | STRONG
- requirement_type:
  MUST_HAVE | HIGH_VALUE | DIFFERENTIATOR | OPTIONAL
- source
- source_version
- confidence
- valid_from / valid_to

Skill requirements — центральная часть matching.

## 9. Knowledge

`CareerKnowledgeRequirement`:
- career_id
- knowledge_id
- importance
- required_level
- requirement_type
- source
- confidence

Knowledge не смешивается со Skill.

## 10. Abilities

Abilities описывают более общие способности, если они реально нужны для профессии.

Примеры:
- oral comprehension;
- numerical reasoning;
- problem sensitivity;
- spatial orientation.

Источник V1 преимущественно O*NET.

Abilities не должны превращаться в псевдопсихологический тест. В V1 они secondary signal и не являются hard gate без доказанной необходимости.

## 11. Work Activities

Стандартизированные виды деятельности:
- communicating with customers;
- analyzing data;
- managing people;
- operating equipment;
- planning;
- documenting;
- selling;
- teaching;
- designing;
- troubleshooting.

Используются для Experience Transfer и Preference Fit.

## 12. Work Context

Параметры среды:
- remote/on-site potential;
- customer contact;
- teamwork;
- autonomy;
- routine;
- pace;
- physical activity;
- travel;
- schedule;
- responsibility for others;
- work environment.

Work Context сравнивается с PreferenceProfile пользователя.

## 13. Work Styles

В V1 допускаются как secondary attributes:
- attention to detail;
- dependability;
- initiative;
- adaptability;
- persistence;
- cooperation.

Не строим отдельный personality test вокруг Work Styles.

## 14. Interests

RIASEC/interest data можно хранить как дополнительный атрибут Career Profile, если доступен из O*NET/другого разрешённого источника.

Для adult V1 Interest Fit:
- secondary signal;
- не заменяет Career Capital;
- не блокирует профессию;
- может использоваться в сценарии «Новий напрям».

## 15. Education Requirement

`CareerRequirement`:
category = EDUCATION.

Храним:
- minimum level;
- preferred level;
- field;
- country/context;
- hardness;
- alternative route;
- source;
- validity.

Критично отличать:
`legally required` от `commonly preferred`.

## 16. Experience Requirement

- minimum experience;
- preferred experience;
- relevant functions;
- seniority;
- management experience optional;
- hardness;
- source.

Количество лет не должно быть единственным критерием.

## 17. Credentials / Legal Requirements

- required credential/license;
- issuing authority/context;
- mandatory/optional;
- country;
- validity;
- renewal requirements optional;
- source.

Legal mandatory requirement может стать HARD BLOCKER.

## 18. Language Requirement

- language
- minimum level
- preferred level
- hardness
- country/region
- source

Для Украины требования должны по возможности основываться на реальном рынке, а не автоматически переноситься из O*NET/ESCO.

## 19. Tools & Technology

Инструменты привязываются к MNP Skills типа TOOL/DIGITAL.

Для каждой профессии:
- tool/technology;
- importance;
- prevalence optional;
- source;
- snapshot/review date.

Быстро меняющиеся tools требуют более частого refresh.

## 20. Entry Routes

Career Profile хранит возможные способы входа:
- DIRECT
- ADJACENT_TRANSFER
- SHORT_UPSKILL
- CERTIFICATION
- INTERNSHIP
- FORMAL_RETRAINING

Это общая информация профессии. Персональный маршрут строится Route Engine.

## 21. Career Levels

Если профессия имеет понятную progression ladder:
- ENTRY
- MIDDLE
- SENIOR
- LEAD
- MANAGER / HEAD

Не все careers обязаны иметь все уровни.

V1 может описывать target role как canonical career + level, если это существенно влияет на требования и зарплату.

## 22. Career Relations

`CareerRelation`:
- from_career
- to_career
- relation_type
- strength
- source

Types:
- PROGRESSION
- ADJACENT
- RELATED
- SAME_FAMILY
- COMMON_TRANSITION

Это career-to-career prior, а не персональная рекомендация.

## 23. Market Layer — отдельный объект

Career Profile содержит ссылки на MarketSnapshot, но не хранит текущую зарплату как постоянный атрибут.

`Career ↔ MarketSnapshot(country, region, date)`

Market facts:
- vacancy volume;
- salary;
- demand trend;
- competition proxy;
- remote share;
- entry-level availability;
- geography;
- employers.

## 24. Ukraine-first market profile

Для каждой из 50 профессий V1 желательно иметь:
- распространённые украинские job titles;
- количество/диапазон вакансий;
- salary distribution;
- регионы спроса;
- remote availability;
- common requirements;
- common tools;
- common experience requirements;
- major employer types;
- freshness date.

Источники и legal access rules фиксируются отдельно в DATA-002.

## 25. External mappings

Career может иметь:
- ESCO occupation ID
- ISCO code
- O*NET occupation mapping
- Ukrainian classifier mapping

Mapping types:
EXACT | CLOSE | BROAD | NARROW.

Нельзя автоматически считать две профессии идентичными только из-за crosswalk.

Lightcast отсутствует.

## 26. Career Profile completeness

Internal completeness dimensions:
- identity
- skills
- knowledge
- tasks
- activities
- context
- requirements
- mappings
- market data

Career не переводится в ACTIVE, если отсутствует минимально необходимый набор для matching.

## 27. Minimum publish gate V1

Для ACTIVE career обязательно:
1. MNP Career ID.
2. UK/EN names.
3. Career Family.
4. Short description.
5. Top tasks.
6. MUST_HAVE/HIGH_VALUE skills.
7. Knowledge where relevant.
8. Education/credential/legal requirements.
9. Work Context minimum set.
10. At least one source for core requirements.
11. Ukrainian aliases.
12. Market status/data-quality marker.

Не обязательно для первого publish:
- perfect long article;
- exhaustive tools;
- every O*NET attribute;
- learning providers;
- vacancies.

## 28. Career Profile source priority

Предлагаемая логика:
1. Ukrainian legal/regulatory sources — legal requirements.
2. Ukrainian market evidence — actual UA demand/requirements.
3. ESCO — occupation/skill structure.
4. O*NET — rich occupational attributes/tasks/context.
5. MNP editorial normalization.

При конфликте источник выбирается по типу факта и географии, а не по единой глобальной иерархии.

## 29. Versioning

Изменение Career Profile создаёт новую version/revision metadata.

Исторический MatchRun сохраняет:
- career_profile_version;
- career_kb_version;
- market_data_version.

Это позволяет воспроизводить старый результат.

## 30. Archive policy

ARCHIVED:
- не участвует в новых default matching runs;
- остаётся доступной историческим MatchRun;
- mappings/aliases не удаляются;
- может быть restored.

Причины:
- профессия устарела;
- merged;
- слишком узкая;
- недостаточно данных;
- заменена другой canonical Career.

## 31. Admin/editor workflow

DRAFT
→ data import
→ normalization
→ editorial review
→ validation
→ ACTIVE
→ scheduled review
→ update/archive.

Все изменения:
- actor;
- timestamp;
- reason;
- before/after;
- source update.

## 32. Career Profile → Matching contract

Matching Engine получает immutable snapshot:
- career identity;
- skills;
- knowledge;
- activities/context;
- requirements;
- relations;
- market snapshot ref.

Engine не должен читать marketing/editorial text для расчёта score.

## 33. User-facing Career Card

Для профессии показываем:
- Назва
- Що робить
- Чому вам підходить
- Що у вас уже є
- Чого бракує
- Чи можете почати зараз
- Зарплата
- Попит
- Скільки часу до переходу
- Що зробити далі

Это строится из structured Career Profile + Person Match + Market + Route.

## 34. Explicit non-goals V1
- Lightcast.
- Автоматически созданные LLM-профессии.
- 1000 плохо нормализованных профессий ради размера каталога.
- Текущая зарплата как static Career field.
- Personality type как основа Career Profile.
- Одна внешняя taxonomy как source of truth.

## 35. Acceptance criteria
Career Profile считается пригодным, если:
1. имеет собственный MNP ID;
2. существует независимо от ESCO/O*NET;
3. имеет UK/EN identity;
4. связан с MNP Skills;
5. содержит requirements для feasibility;
6. содержит context для preferences;
7. позволяет Experience Transfer;
8. market data отделена и датирована;
9. добавление/архивирование не меняет engine;
10. исторический match воспроизводим;
11. Lightcast не требуется;
12. пользовательский результат можно объяснить structured evidence.

## 36. Founder Questions

### CP-FQ-001 — Career granularity
Что считать отдельной профессией?
Пример: Sales Manager, B2B Sales Manager, Key Account Manager.
**Рекомендация:** отдельная Career только если существенно отличаются задачи/skills/entry requirements/market route. Иначе canonical Career + aliases/specializations.

### CP-FQ-002 — Career Levels
Разделять Junior/Middle/Senior на разные профессии?
**Рекомендация:** нет. Career + level/profile variant. Иначе каталог раздуется и transitions исказятся.

### CP-FQ-003 — RIASEC
Хранить RIASEC для профессии?
**Рекомендация:** да как secondary attribute, особенно для «Новий напрям», но не делать обязательным core matching factor adult V1.

### CP-FQ-004 — Abilities
Использовать O*NET Abilities в V1?
**Рекомендация:** хранить, но не делать сильным ranking factor до validation.

### CP-FQ-005 — Career articles
Должна ли каждая из 50 профессий иметь полноценную SEO/media статью до запуска?
**Рекомендация:** нет. Structured Profile обязателен; long-form content развивается параллельно.

### CP-FQ-006 — Publish quality
Можно ли ACTIVE career без украинского market data?
**Рекомендация:** временно да, если стоит `MARKET_DATA_LIMITED`; но такие профессии не должны получать уверенные Market/Income выводы.

### CP-FQ-007 — Monthly updates
Обновлять всю профессию ежемесячно?
**Рекомендация:** нет. Market snapshots — чаще/ежемесячно; core occupational profile — по изменениям/квартально или при source update.

### CP-FQ-008 — Первые 50 профессий
Отбирать по популярности Work.ua?
**Рекомендация:** не только. Формула отбора должна учитывать: vacancy volume + salary opportunity + transferability + retraining feasibility + strategic relevance для целевых взрослых групп MNP.
