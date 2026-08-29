# MNP_EVIDENCE_AND_CONFIDENCE_MODEL_V1

**Продукт:** МОЖУ: Мій Напрям  
**Версия:** 1.0  
**Статус:** Draft for Founder Approval  
**Дата:** 2026-08-29  
**Зависимости:** MNP_METHODOLOGY_V1, MNP_DATA_MODEL_V1, MNP_SKILL_SCHEMA_V1, MNP_CAREER_PROFILE_SCHEMA_V1

## 1. Цель

Разделить три разных понятия:

1. **FACT** — что система знает о человеке/профессии/рынке.
2. **EVIDENCE** — на основании чего это известно.
3. **CONFIDENCE** — насколько системе можно доверять этому конкретному выводу.

Ключевое правило:

`MATCH ≠ CONFIDENCE`

Высокий Career Fit при слабых данных должен отображаться как потенциально интересный, но менее уверенный результат.

## 2. Почему это критично для MNP

Founder decision: после parsing CV нет обязательного confirmation screen.

Следовательно, система обязана:
- не выдавать inference за подтверждённый факт;
- хранить источник каждого важного утверждения;
- учитывать качество исходных данных;
- не делать сильных market claims при слабой/устаревшей статистике;
- объяснять recommendation через evidence.

## 3. Evidence Types

### CLAIMED
Человек явно сообщил информацию.

Примеры:
- указал Excel в CV;
- отметил навык в анкете;
- указал опыт управления.

### INFERRED
Система вывела факт из наблюдаемых данных.

Пример:
«руководил командой из 8 сотрудников» → возможный Team Management.

Inference сохраняет исходный fragment/source.

### VERIFIED
Есть более сильное подтверждение:
- сертификат;
- credential;
- portfolio/project;
- measurable achievement;
- structured test;
- consultant verification;
- иной проверяемый источник.

VERIFIED не означает абсолютную истину; это более сильный evidence class.

## 4. Evidence Object

- id
- entity_type
- entity_id
- evidence_type
- source_type
- source_ref
- excerpt optional
- document_id optional
- created_at
- strength_internal
- parser_confidence optional
- verified_at optional
- verified_by optional

## 5. Source Types

Person:
- CV
- QUESTIONNAIRE
- USER_EDIT
- CERTIFICATE
- PORTFOLIO
- PROJECT
- ACHIEVEMENT
- TEST
- HUMAN_REVIEW

Career:
- ESCO
- O_NET
- UA_LEGAL
- UA_CLASSIFIER
- UA_MARKET
- MNP_EDITORIAL

Market:
- APPROVED_JOB_BOARD
- PUBLIC_STATISTICS
- EMPLOYMENT_SERVICE
- PARTNER_DATA
- MNP_RESEARCH

Lightcast отсутствует в V1.

## 6. Confidence Bands

Внутренне допускается числовой score, но UI использует bands:

- HIGH
- MEDIUM
- LOW
- INSUFFICIENT

Пользователю numeric confidence в V1 не показываем.

## 7. Person Data Confidence

Зависит от:
- explicitness;
- source quality;
- parser certainty;
- evidence quantity;
- evidence consistency;
- recency where relevant.

Пример:
CV: «Excel» → CLAIMED, medium/high confidence.
CV: «создавал финансовые модели в Excel 5 лет» → CLAIMED + contextual evidence, higher confidence.
Система вывела Power BI только из слова «BI reporting» → INFERRED, lower confidence.

## 8. Proficiency Confidence

`Proficiency Level` и `Confidence` независимы.

Возможны:
- STRONG + LOW confidence;
- WORKING + HIGH confidence.

Это предотвращает ложную точность.

## 9. Career Requirement Confidence

Каждое требование профессии имеет:
- source;
- source version;
- geography where relevant;
- confidence;
- review date.

Если ESCO/O*NET говорит одно, а украинский рынок показывает другое, система не обязана слепо копировать внешний источник.

## 10. Market Confidence

Зависит от:
- source quality;
- sample size;
- freshness;
- geographic relevance;
- agreement between sources;
- data completeness.

Статусы:
- MARKET_CONFIDENCE_HIGH
- MARKET_CONFIDENCE_MEDIUM
- MARKET_CONFIDENCE_LOW
- MARKET_DATA_LIMITED

## 11. Freshness

Для market data freshness обязательна.

Для core occupational facts freshness менее критична.

Не используем один TTL для всех данных.

Примерная политика:
- вакансии/зарплаты: frequent snapshots;
- tools/technologies: periodic review;
- legal requirements: event/source-driven review;
- core tasks/skills: slower review.

Точные сроки — в ETL/Market specs.

## 12. Conflict Handling

Если evidence конфликтует:
1. не перезаписывать тихо старое значение;
2. сохранить оба источника;
3. применить source priority/context;
4. снизить confidence при нерешённом конфликте;
5. при необходимости отправить в review queue.

## 13. User Edit

Пользователь может редактировать Career Card позже.

USER_EDIT считается CLAIMED evidence, а не автоматически VERIFIED.

История изменений сохраняется.

## 14. Multiple Evidence

Один Skill может иметь:
- CV evidence;
- achievement evidence;
- certificate;
- user edit.

Несколько независимых согласующихся evidence повышают confidence, но не должны механически суммироваться без ограничения.

## 15. Negative Evidence

Отсутствие skill в CV ≠ доказательство отсутствия skill.

Поэтому:
- `NOT_FOUND` не равно `NO_SKILL`;
- gap может быть `UNKNOWN`, если данных недостаточно.

Это особенно важно для коротких CV.

## 16. Unknown State

Система должна поддерживать:
- KNOWN_PRESENT
- KNOWN_ABSENT
- UNKNOWN

Нельзя автоматически превращать UNKNOWN в ABSENT.

## 17. Match Confidence

Confidence конкретной CareerMatch зависит минимум от:
- Career Card completeness;
- relevant person evidence coverage;
- Career Profile completeness;
- requirement confidence;
- market confidence;
- mapping confidence.

Высокий overall fit с низкой coverage → lower recommendation confidence.

## 18. Recommendation Confidence

Каждая recommendation получает internal band:
- HIGH
- MEDIUM
- LOW

INSUFFICIENT может исключить career из featured TOP-3, но не обязательно из полного каталога.

## 19. Confidence vs Ranking

Confidence не должен просто становиться ещё одним Fit factor.

Предлагаем:
1. посчитать Fit/Feasibility;
2. отдельно посчитать Confidence;
3. использовать Confidence как quality gate/tie-breaker/display qualifier.

Так система не будет считать «мало данных» равным «плохая профессия».

## 20. Hard Blocker Evidence

Для `BLOCKED` требуется повышенный стандарт доказательности.

Например:
«для профессии юридически необходима лицензия» должно иметь authoritative source.

Слабый inference не может создавать hard blocker.

## 21. Explanation Contract

Пользовательский вывод должен позволять ответить:
- почему система это считает;
- какие данные пользователя использованы;
- какие требования профессии использованы;
- насколько свежи market data;
- чего система не знает.

Пример:
**Сильна сторона: управління командою**
Основание: опыт руководства командой, указанный в CV.

Не показываем internal confidence decimals.

## 22. Missing Data Behavior

Если данных мало:
- не заставляем проходить confirmation step;
- не выдумываем;
- снижаем confidence;
- можем предложить позже дополнить Career Card;
- сохраняем результат с маркировкой ограниченности.

## 23. Evidence Provenance

Для derived facts:
`Derived Fact → Evidence → Source → Version/Date`

Для market:
`Market Claim → Snapshot → Source → Date → Geography`

Для career:
`Requirement → Source → Version → Review Date`

## 24. Auditability

Должна существовать возможность восстановить:
- какие входные данные были;
- какой parser/version;
- какой Career KB;
- какой market snapshot;
- какой matching engine;
- какие evidence использованы.

Это необходимо для debugging и Golden Dataset.

## 25. Privacy Principle

Evidence может содержать персональные фрагменты CV.

Поэтому:
- не дублировать full CV text без необходимости;
- хранить минимально достаточный excerpt/ref;
- access control;
- deletion cascade/retention будут определены в Privacy spec.

## 26. User-facing confidence

В V1 не создаём сложную шкалу доверия на каждом элементе.

Используем confidence для:
- качества recommendation;
- предупреждений;
- limited-data labels;
- предложения дополнить данные.

Примеры:
- `Даних достатньо`
- `Потрібно більше інформації`
- `Обмежені дані про ринок`

## 27. Career activation quality gate

Career может стать ACTIVE только при достаточном confidence core requirements.

`MARKET_DATA_LIMITED` допустим отдельно.

Core profile low confidence → DRAFT.

## 28. Golden Dataset

Golden personas должны содержать:
- input facts;
- expected evidence classification;
- expected unknowns;
- expected hard blockers;
- expected confidence bands.

Мы тестируем не только ranking, но и способность системы **не делать вывод**, когда данных недостаточно.

## 29. Explicit non-goals
- пользовательские confidence проценты;
- LLM как judge истины;
- assumption = fact;
- отсутствие в CV = отсутствие навыка;
- слабый источник = hard blocker;
- stale market data без маркировки;
- Lightcast.

## 30. Acceptance Criteria
1. Каждый important derived person fact имеет evidence.
2. CLAIMED/INFERRED/VERIFIED различаются.
3. UNKNOWN существует как полноценное состояние.
4. Proficiency отделён от confidence.
5. Match отделён от confidence.
6. Hard blockers требуют strong evidence.
7. Market claims имеют source/date/geography.
8. Conflict не уничтожает provenance.
9. User edits сохраняют историю.
10. MatchRun воспроизводим.
11. Low data не превращается автоматически в low fit.
12. Система может честно сказать «данных недостаточно».

## 31. Founder Questions

### EC-FQ-001 — Показывать ли пользователю Confidence?
**Рекомендация:** не как отдельный score. Только понятные предупреждения/labels при ограниченных данных.

### EC-FQ-002 — UNKNOWN
Утверждаем правило: отсутствие информации ≠ отсутствие навыка/опыта?
**Рекомендация:** обязательно да.

### EC-FQ-003 — Hard blocker
Требовать authoritative/high-confidence evidence для BLOCKED?
**Рекомендация:** да.

### EC-FQ-004 — User edit
Редактирование пользователем = CLAIMED, не VERIFIED?
**Рекомендация:** да.

### EC-FQ-005 — Featured TOP-3
Если Career Fit высокий, но Confidence LOW — показывать в TOP-3?
**Рекомендация:** по умолчанию нет; оставить в каталоге с пометкой, пока данных недостаточно.

### EC-FQ-006 — Дополнительные вопросы
Если confidence критически низкий, можно ли задать 1–3 contextual questions после первичного результата?
**Рекомендация:** в V1 не блокировать результат; предложить optional уточнение после результата. Это сохраняет ранее утверждённый UX «сразу результат».

### EC-FQ-007 — Evidence в кабинете
Показывать пользователю происхождение ключевых skills/experience?
**Рекомендация:** да в простом виде; это повышает прозрачность и позволяет исправлять Career Card без отдельного confirmation flow.
