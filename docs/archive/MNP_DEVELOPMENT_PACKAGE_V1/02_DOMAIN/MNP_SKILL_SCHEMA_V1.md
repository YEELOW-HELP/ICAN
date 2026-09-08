# MNP_SKILL_SCHEMA_V1

**Продукт:** МОЖУ: Мій Напрям  
**Версия:** 1.0  
**Статус:** Draft for Founder Approval  
**Дата:** 2026-08-29  
**Зависимости:** MNP_METHODOLOGY_V1, MNP_DATA_MODEL_V1

## 1. Цель
Создать собственную Skill Taxonomy MNP, которая позволяет одинаково описывать навыки человека и требования профессии.

`PERSON SKILLS ↔ MNP SKILL ↔ CAREER SKILL REQUIREMENTS`

MNP Skill — не строка из CV и не внешний ESCO/O*NET ID. Это собственная canonical entity.

## 2. Founder decisions incorporated
- 3 уровня proficiency: `BASIC / WORKING / STRONG`;
- Career Card — долгосрочная master-card + versioned snapshots;
- без CV Career Capital собирается адаптивной анкетой;
- Career KB редактируют ADMIN/EDITOR с audit log;
- CV может храниться до удаления пользователем; retention уточняется в Privacy spec;
- Career Card редактируется пользователем в кабинете;
- Career/Skill имеют UK + EN canonical names;
- Lightcast не используется.

## 3. Skill entity

Обязательные поля:
- `id`: MNP_SKILL_ID
- `canonical_name_en`
- `canonical_name_uk`
- `skill_type`
- `status`: DRAFT | ACTIVE | ARCHIVED
- `description`
- `taxonomy_version`
- `created_at`
- `updated_at`

Дополнительно:
- parent_skill_id optional
- skill_family_id optional
- notes_internal optional

## 4. Skill Types V1
Предлагается не смешивать всё под одним типом.

1. `TECHNICAL` — профессиональные/технические навыки.
2. `TOOL` — владение инструментом/ПО/оборудованием.
3. `FUNCTIONAL` — переносимые рабочие функции.
4. `MANAGEMENT` — управление людьми/процессами/ресурсами.
5. `COMMUNICATION` — переговоры, презентации, stakeholder/customer interaction.
6. `DIGITAL` — общие цифровые навыки.
7. `LANGUAGE` не хранится как Skill — отдельная сущность.
8. `KNOWLEDGE` не хранится как Skill — отдельная сущность.

Пример:
- Power BI → TOOL
- Data visualization → TECHNICAL
- Project planning → FUNCTIONAL
- Team leadership → MANAGEMENT
- Negotiation → COMMUNICATION

## 5. Skill proficiency

### BASIC
Человек знаком с навыком и способен выполнять простые задачи с инструкцией/поддержкой.

### WORKING
Способен самостоятельно использовать навык в типичных рабочих задачах.

### STRONG
Уверенно использует навык в сложных задачах, способен принимать решения, улучшать практику или помогать другим.

Это не сертификат компетентности. Уровень всегда рассматривается вместе с Evidence Strength.

## 6. PersonSkill

- `career_card_id`
- `skill_id`
- `proficiency_level`
- `evidence_strength`
- `confidence`
- `years_used` optional
- `last_used_at` optional
- `source_type`
- `created_at`
- `updated_at`

Один Skill может иметь несколько Evidence records.

## 7. Evidence sources
- CV explicit
- CV inferred from responsibilities
- questionnaire
- education
- certificate
- portfolio/project
- achievement
- test
- human review

Тип evidence:
`CLAIMED | INFERRED | VERIFIED`.

## 8. Skill extraction rule

Resume Parser:
1. извлекает raw phrase;
2. нормализует;
3. ищет exact alias;
4. ищет normalized alias;
5. применяет deterministic mapping rules;
6. присваивает MNP_SKILL_ID;
7. сохраняет raw evidence;
8. рассчитывает confidence.

Low-confidence phrase не должна автоматически становиться VERIFIED skill.

## 9. Aliases

`SkillAlias`:
- skill_id
- alias
- language
- alias_type
- source
- status
- confidence optional

Типы:
- EXACT_SYNONYM
- ABBREVIATION
- COMMON_VARIANT
- UKRAINIAN_MARKET_TERM
- ENGLISH_MARKET_TERM
- TOOL_VARIANT

Пример:
`Microsoft Excel` → aliases: Excel, MS Excel, Microsoft Office Excel.

## 10. External mappings

`SkillExternalMapping`:
- skill_id
- source_system
- external_id
- external_label
- mapping_type
- confidence
- source_version

V1:
- ESCO
- O*NET where meaningful

Lightcast: **не используется**.

Mapping не меняет identity MNP Skill.

## 11. CareerSkillRequirement

Для профессии:
- career_id
- skill_id
- importance
- required_level
- requirement_type
- source
- source_version
- confidence
- valid_from
- valid_to

Requirement types:
- MUST_HAVE
- HIGH_VALUE
- DIFFERENTIATOR
- OPTIONAL

## 12. Importance

Importance — internal normalized parameter matching engine.

В V1 не показываем пользователю псевдоточность внешних чисел.

Рекомендуемая внутренняя шкала:
- 1 LOW
- 2 MEDIUM
- 3 HIGH
- 4 CRITICAL

## 13. Skill gap

Для каждого CareerSkillRequirement:

`PersonSkill vs CareerSkillRequirement`

Результат:
- MATCH
- PARTIAL_GAP
- FULL_GAP
- UNKNOWN

После этого определяется действие:
- LEARN
- PRACTICE
- PROVE
- REFRAME

CERTIFY применяется через Credential Gap, если формальное подтверждение действительно требуется.

## 14. Recency

Skill не исчезает только потому, что давно не использовался.

Но `last_used_at` может уменьшать confidence/relevance для быстро меняющихся technical/tool skills.

Правила decay должны быть отдельными и не применяться одинаково ко всем навыкам.

## 15. Years of experience

`years_used` — supporting signal, но не прямой эквивалент proficiency.

10 лет ≠ автоматически STRONG.
1 год ≠ автоматически BASIC.

## 16. Skill families

Skill Family нужна для:
- навигации;
- аналитики;
- transferability;
- related skill discovery.

Примеры:
- Sales
- Customer Service
- Project Management
- Data & Analytics
- Software
- Finance
- Operations
- Marketing
- Healthcare
- Engineering

Skill Family не заменяет конкретные skills.

## 17. Transferability

Навык может быть:
- HIGH_TRANSFER
- DOMAIN_DEPENDENT
- CAREER_SPECIFIC

Это свойство помогает Experience Transfer, но не является абсолютным: transferability зависит от target career.

## 18. Skill provenance

Для каждого canonical skill и mapping фиксируем:
- source
- source_version
- created_by
- reviewed_by optional
- created_at
- updated_at

Изменения taxonomy — через versioning + audit log.

## 19. Admin workflow

ADMIN/EDITOR может:
- создать skill;
- добавить aliases;
- объединить duplicate candidates;
- archive;
- изменить family/type;
- добавить external mapping;
- проверить ambiguous mapping.

Удаление используемого Skill запрещено: только ARCHIVED / merge with migration.

## 20. Initial Skill DB

Skill DB не создаётся вручную «с нуля» по одному навыку.

Pipeline:
1. импорт разрешённых ESCO/O*NET данных;
2. normalization;
3. deduplication;
4. UK/EN lexical layer;
5. отбор skills, необходимых первым 50 профессиям;
6. украинские market aliases;
7. editorial review;
8. publish taxonomy v1.

Цель V1 — не максимальное число skills, а качественное покрытие первых 50 careers.

## 21. User-facing representation

В Career Card:
**Ваші навички**
- Переговори — Сильний
- Управління командою — Сильний
- Excel — Робочий рівень
- Power BI — Базовий

Не показываем:
- internal IDs;
- confidence decimals;
- taxonomy mappings;
- opaque mathematical scores.

## 22. Matching contract

Matching Engine получает:
- PersonSkill[]
- CareerSkillRequirement[]

и возвращает:
- matched skills;
- partial gaps;
- missing skills;
- evidence quality;
- component score internal;
- explanation codes.

## 23. Explicit non-goals
- personality traits как skills;
- knowledge как skills;
- language как skills;
- Lightcast taxonomy;
- LLM-generated canonical skills без taxonomy review;
- бесконтрольное создание нового Skill на каждую raw phrase.

## 24. Acceptance criteria
1. Один skill имеет стабильный MNP ID.
2. UK/EN names обязательны.
3. CV aliases нормализуются в canonical skill.
4. PersonSkill имеет 3-level proficiency.
5. Evidence отделён от proficiency.
6. Skill связан с Career requirement.
7. Можно определить personalized gap.
8. External mapping не является identity.
9. Duplicate/archived skills управляются без потери истории.
10. Система работает без Lightcast.

## 25. Founder Questions

### SS-FQ-001 — Skill Types
Утверждаем предложенные 6 типов: TECHNICAL / TOOL / FUNCTIONAL / MANAGEMENT / COMMUNICATION / DIGITAL?
**Рекомендация:** да для V1.

### SS-FQ-002 — Proficiency labels UI
Internal: BASIC / WORKING / STRONG.
UI украинский:
`Базовий / Робочий / Сильний`.
**Рекомендация:** да.

### SS-FQ-003 — Кто может менять уровень skill?
Варианты: parser/system + user; только user; consultant.
**Рекомендация:** система устанавливает initial level, пользователь может редактировать; история изменения сохраняется.

### SS-FQ-004 — Автоматически добавлять неизвестный skill?
**Рекомендация:** нет. Unknown phrase → review queue / unmapped phrase. Иначе taxonomy быстро загрязнится.

### SS-FQ-005 — Skill decay
**Рекомендация:** хранить recency сейчас, но не вводить aggressive decay в V1. Вернуться после pilot data.

### SS-FQ-006 — Показывать Evidence пользователю?
**Рекомендация:** частично: «підтверджено досвідом / зазначено у CV», но без внутренних confidence numbers.

### SS-FQ-007 — Initial taxonomy scope
**Рекомендация:** импортировать широкий open foundation, но publish/quality-control в V1 прежде всего skills, необходимые 50 Career Profiles.
