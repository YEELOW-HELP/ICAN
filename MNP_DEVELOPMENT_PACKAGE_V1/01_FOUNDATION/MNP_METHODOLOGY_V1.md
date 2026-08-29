# MNP_METHODOLOGY_V1

**Продукт:** МОЖУ: Мій Напрям  
**Версия:** 1.0  
**Статус:** Founder Definition / Source of Truth  
**Дата:** 2026-08-29

## 0. Назначение

Документ фиксирует методологический фундамент продукта: как из резюме и минимального набора ответов формируется Career Card, как человек сравнивается с Career Universe, как считаются Fit, Feasibility, Transition Distance, Skill Gap, Market Attractiveness и Income Upside, какие внешние данные используем и что остаётся Core IP MNP.

## 1. Главная задача

MNP отвечает не только «какая профессия мне подходит?», а:

> **Какие карьерные переходы доступны именно мне с учётом моего опыта, навыков, целей, ограничений и реального рынка труда — и какой следующий шаг наиболее рационален?**

MNP — Personal Career Navigation System, а не классический personality/career test.

## 2. Базовая модель

### PERSON
Что человек делал, умеет, знает, может доказать, хочет, готов изменить и что ограничивает его выбор.

### CAREER
Что профессия требует, использует, предполагает, требует для входа и даёт на рынке.

Обе стороны приводятся к сопоставимым измерениям:

`PERSON PROFILE ↔ CAREER PROFILE`

## 3. Полный pipeline

`RESUME`
→ `RESUME PARSER`
→ `CAREER CARD v0`
→ `USER VERIFICATION`
→ `MINIMAL QUESTIONNAIRE`
→ `CAREER CARD v1`
→ `PERSON PROFILE`
→ `CAREER UNIVERSE`
→ `HARD FEASIBILITY FILTER`
→ `PERSON ↔ CAREER MATCHING`
→ `ALL AVAILABLE CAREERS`
→ `RANKING`
→ `TOP CAREER TRANSITIONS`
→ `PERSON → CAREER GAP`
→ `MARKET VALIDATION`
→ `LEARNING / PROOF GAP`
→ `REAL OPPORTUNITIES`
→ `CAREER ROUTE`

## 4. Resume First

Первый шаг взрослого пользователя — загрузить резюме. Система не просит повторно вводить то, что уже можно извлечь.

### V1 rule
Базовый Resume Parser работает **без LLM-токенов**:
- text extraction;
- regex;
- section detection;
- occupation dictionaries;
- skill dictionaries;
- ESCO/O*NET mappings;
- confidence scoring;
- user confirmation для low-confidence полей.

LLM/CV enrichment — только optional/PRO feature flag.

## 5. Career Card

Career Card = **Career Capital + Career Intent**.

### Career Capital
- Experience
- Skills
- Knowledge
- Education
- Credentials
- Languages
- Achievements
- Seniority
- Management Capital
- Domain Capital
- Functional Capital
- Technical Capital
- Evidence Strength

### Career Intent
- Career goal
- Target income
- Time horizon
- Transition appetite
- Work preferences
- Work values
- Constraints
- Learning capacity
- Location
- Work format

## 6. Experience

Для каждого периода:
- company
- raw_job_title
- normalized_career_id
- industry
- start_date / end_date
- duration
- seniority
- responsibilities
- achievements
- management_scope
- team_size
- tools
- evidence
- confidence

## 7. Skills

Skill — самостоятельная сущность:

- `MNP_SKILL_ID`
- canonical_name
- ua_name / en_name
- aliases
- skill_type
- ESCO_mapping
- O_NET_mapping
- Lightcast_mapping_optional
- evidence[]
- confidence
- years_used
- last_used
- proficiency

Ни ESCO, ни O*NET, ни Lightcast не являются primary key внутри MNP.

## 8. Skill Evidence

Типы:
- `CLAIMED` — пользователь указал;
- `INFERRED` — следует из опыта;
- `VERIFIED` — подтверждено сертификатом, тестом, портфолио, проектом, результатом или консультантом.

Evidence влияет на confidence и Skill Fit.

## 9. Knowledge / Education / Credentials / Languages

Knowledge хранится отдельно от skills.

Education:
- level
- field
- institution
- qualification
- graduation_year
- country
- recognition
- evidence

Credentials:
- certifications
- professional licenses
- regulated-profession permissions
- driving licence
- safety permits
- other formal credentials

Languages:
- language
- speaking
- reading
- writing
- certified_level
- evidence

## 10. Career Capital Vector

Из Career Card формируется:
- Functional Capital
- Domain Capital
- Management Capital
- Technical Capital
- Social Capital
- Credential Capital
- Evidence Strength

## 11. Minimal Questionnaire

Принцип: **Do not ask what we already know.**

Минимально нужно получить:
1. Career goal
2. Target income
3. Time horizon
4. Willingness to change career
5. Preferred work objects: people / data / technology / things / ideas
6. Work environment preferences
7. TOP work values
8. Location / target region
9. Remote / hybrid / onsite
10. Learning time available
11. Learning budget
12. Willingness to obtain new qualification/license
13. Willingness to accept lower initial position/income
14. Excluded careers/activities
15. Relevant practical constraints

Это сбор decision variables, а не психологический тест.

## 12. Full Person Profile

После CV + questionnaire:
- Career history
- Experience
- Skills
- Knowledge
- Education
- Credentials
- Languages
- Career capital
- Achievements
- Goals
- Income target
- Preferences
- Values
- Constraints
- Learning capacity
- Transition appetite
- Location
- Work format

## 13. Career Universe

Engine оценивает весь поддерживаемый Career Universe, а не только заранее выбранный shortlist.

MVP: 50–100 хорошо нормализованных профессий. Далее 150 → 300–500 → расширение.

## 14. Career Profile

Для каждой профессии:
- Identity
- Skills
- Knowledge
- Abilities
- Activities
- Tasks
- Work Styles
- Work Context
- Interests
- Education requirements
- Experience requirements
- Credentials
- Language requirements
- Entry barriers
- Career family
- Related careers
- Market data

Каждая профессия получает `MNP_CAREER_ID`.

Mappings:
ESCO, O*NET, ISCO, Класифікатор професій України, Lightcast LOT optional, Work.ua, Robota.ua, ДСЗ.

## 15. Data Modules

Логические модули:
1. Career DB
2. Skill DB
3. Career ↔ Skill DB
4. Requirements DB
5. Career Attributes DB
6. Transition DB
7. Market DB
8. Learning DB
9. Opportunity DB

Физически это может быть одна БД.

## 16. Источники

### ESCO
- occupations
- skills/competences
- occupation↔skill relations
- hierarchy
- labels/aliases
- ISCO mappings

### O*NET
- Skills
- Knowledge
- Abilities
- Tasks
- Work Activities
- Work Context
- Work Styles
- Interests
- Education
- Experience
- Training
- Related Occupations
- Technology Skills

### Ukraine
- Класифікатор професій
- ДСЗ
- Work.ua
- robota.ua

### Lightcast
Не critical dependency. Возможные роли:
- richer skill taxonomy
- Classification API
- global benchmarks
- validation/calibration
- emerging skills
- tech/digital enrichment

## 17. Matching Philosophy

Не использовать один непрозрачный «% подходит».

Каждая профессия получает Match Vector:
- Skill Fit
- Experience Transfer
- Knowledge Fit
- Preference Fit
- Values Fit
- Feasibility
- Market Attractiveness
- Income Potential
- Transition Cost
- Confidence

Агрегированный score допустим только для ranking.

## 18. Hard Feasibility Filter

До ranking проверяются hard blockers:
- обязательный диплом;
- лицензия;
- недостижимый срок;
- обязательный язык;
- физический/географический hard constraint;
- mandatory credential.

Статусы:
- `READY_NOW`
- `NEAR_READY`
- `REACHABLE`
- `LONG_TRANSITION`
- `BLOCKED`

## 19. Skill Fit

Концептуально:

`SkillFit = Σ(career_skill_importance × user_skill_level × evidence_strength) / Σ(career_skill_importance)`

Точные шкалы и веса фиксируются отдельно.

## 20. Experience Transfer

Сравниваются:
- functions
- responsibilities
- industries
- management
- stakeholders
- tools
- complexity
- seniority

Experience Transfer — отдельная метрика, не часть Skill Fit.

## 21. Knowledge / Preference / Values Fit

### Knowledge Fit
`required knowledge ↔ user knowledge`

### Preference Fit
Сравнение предпочтений с work context/activities:
- autonomy
- teamwork
- customer interaction
- pace
- routine/novelty
- leadership
- physical environment
- remote/on-site

### Values Fit
- income
- stability
- autonomy
- growth
- recognition
- social impact
- creativity
- work-life balance
- learning

## 22. Market Attractiveness

Market Score описывает профессию на конкретном рынке и в конкретную дату:
- demand
- vacancy volume
- demand trend
- salary
- competition
- remote availability
- regional availability
- entry-level availability

Любой market fact должен иметь country, region, snapshot_date, source.

## 23. Income Potential

`Target Career Expected Income – Current/Expected User Income`

Отдельно учитывать:
- short-term
- medium-term
- temporary downside
- upside after gap closure

## 24. Transition Cost

- Time Cost
- Learning Cost
- Financial Cost
- Experience Gap
- Credential Gap
- Risk

## 25. Overall Career Score

Концептуально:

`Overall Career Score = Skill Fit + Experience Transfer + Knowledge Fit + Preference Fit + Values Fit + Feasibility + Market Attractiveness + Income Potential - Transition Cost`

**Weights не утверждены в Methodology v1.**

Они калибруются через:
- Golden Dataset
- expert review
- pilot
- observed outcomes

## 26. Ranking Modes

Пользователь должен видеть несколько стратегий:
- Найкраще для мене
- Можу зараз
- Використати мій досвід
- Більше заробляти
- Швидко перейти
- Перспективні
- Новий напрям

## 27. Transition Distance

- D0 Same Career
- D1 Progression
- D2 Adjacent Career
- D3 Transferable Career
- D4 Career Change
- D5 Fundamental Retraining

## 28. Personal Skill Gap

`Target Career Requirements – Person Profile = Personal Gap`

Типы gap:
- MUST_HAVE
- HIGH_VALUE
- DIFFERENTIATOR
- OPTIONAL

Действие:
- LEARN
- PRACTICE
- PROVE
- CERTIFY
- REFRAME

## 29. Learning Priority

Концептуально:

`Learning Priority = Importance × Gap Size × Market Value × Learnability / TimeCost`

Пользователь видит 3–5 наиболее полезных gaps, а не длинный список.

## 30. Career Route

`TODAY`
→ What you already have
→ What must be reframed/proved
→ What must be learned
→ First practical evidence
→ Entry opportunity
→ Target role
→ Next career step

Возможные сценарии:
- SAFE
- GROWTH
- TRANSFORM

## 31. Evidence-First Recommendation

Каждая значимая рекомендация обязана показать:
- почему подходит;
- что совпадает;
- что переносится из опыта;
- чего не хватает;
- hard blockers;
- что на рынке;
- следующий шаг.

`Recommendation = Score + Evidence + Gap + Market + Next Action`

## 32. Confidence

Match ≠ Confidence.

**Match** — насколько профессия подходит.  
**Confidence** — насколько достаточно и качественно данных.

Confidence зависит от:
- Career Card coverage
- evidence strength
- Career KB completeness
- market data freshness
- mapping quality

## 33. Data Provenance

Каждый существенный факт:
- source
- source_version
- retrieved_at
- evidence
- confidence

## 34. Versioning

Версионируются:
- Career DB
- Skill DB
- mappings
- Career Profiles
- market snapshots
- methodology
- weights
- Golden Dataset
- recommendations

## 35. AI Policy

LLM может:
- парсить сложный free text в optional mode;
- объяснять результат;
- улучшать CV;
- вести coaching;
- формировать narrative.

LLM **не определяет final ranking**.

Source of truth — deterministic Calculation Engine.

## 36. MNP Core IP

Собственные компоненты:
1. Career Card Model
2. MNP Career IDs
3. MNP Skill IDs
4. UA lexical normalization
5. Person→Career Matching
6. Experience Transfer
7. Feasibility Engine
8. Transition Distance
9. Personal Skill Gap
10. Learning Priority
11. Career Ranking
12. Ukrainian Market Layer
13. Career Route
14. Evidence/Explanation Model
15. Opportunity Matching
16. Golden Dataset
17. Outcome Dataset

## 37. User Result

Пользователь получает Career Map, а не «результат теста».

Для каждой профессии:
- why
- fit
- feasibility
- skills
- gaps
- salary
- demand
- transition time
- opportunities
- next action

## 38. North Star

Главная метрика:

> **Доля пользователей, для которых система нашла реалистичный карьерный маршрут и после рекомендации произошло подтверждаемое карьерное действие.**

Career Action:
- learning started
- CV reframed
- application
- interview
- internship
- transition
- employment
- income growth

Конечная метрика: **Career Outcome**.

## 39. Founder Decisions v1

1. Resume-first.
2. Базовый Resume Parser без LLM-токенов.
3. Career Card = Career Capital + Career Intent.
4. Adult product не строится вокруг personality test.
5. Person и Career приводятся к общим dimensions.
6. Оценивается Career Universe.
7. Hard feasibility идёт до ranking.
8. Match multidimensional.
9. Match и Confidence разделены.
10. Skill Gap = Person→Career.
11. Transition Distance — отдельная характеристика.
12. Market Attractiveness отделена от personal fit.
13. Result = Career + Evidence + Gap + Market + Route.
14. MNP Career ID и MNP Skill ID — собственные.
15. ESCO + O*NET — базовые открытые источники.
16. Lightcast — enrichment/benchmark, но не critical dependency.
17. Ukrainian Market Layer — отдельный собственный модуль.
18. LLM не определяет ranking.
19. Все рекомендации explainable.
20. Weights утверждаются после Golden Dataset/calibration.

## 40. Следующие обязательные документы

1. `MNP_DATA_MODEL_V1.md`
2. `MNP_CAREER_PROFILE_SCHEMA_V1.md`
3. `MNP_SKILL_SCHEMA_V1.md`
4. `MNP_RESUME_PARSER_V1.md`
5. `MNP_MINIMAL_QUESTIONNAIRE_V1.md`
6. `MNP_MATCHING_MATH_V1.md`
7. `MNP_CAREER_KB_ETL_V1.md`
8. `MNP_GOLDEN_DATASET_V1.md`

Только после Founder Approval Methodology v1 и этих спецификаций matching engine считается достаточно определённым для production-реализации.
