# MNP_DATA_MODEL_V1

**Продукт:** МОЖУ: Мій Напрям  
**Версия:** 1.0  
**Статус:** Draft for Founder Approval  
**Дата:** 2026-08-29

## 1. Назначение
Логическая модель данных для цепочки:
`Input → Career Card → Person Profile ↔ Career Profile → Match → Gap → Route → Opportunity`.

V1: adult-first; CV optional; BASIC без LLM; 50 активных профессий; Career KB — отдельный управляемый модуль; Lightcast не используется.

## 2. Принципы
- собственные MNP IDs;
- external taxonomies только mappings;
- raw / normalized / derived data разделены;
- evidence и confidence обязательны для выводов;
- market data всегда source+date;
- профессии добавляются/архивируются без изменения matching engine;
- архивирование не ломает исторические результаты;
- confirmation screen после CV parsing отсутствует;
- Lightcast отсутствует из V1.

## 3. Core entities
`User`, `AssessmentSession`, `SourceDocument`, `CareerCard`,
`Experience`, `Achievement`, `Education`, `Skill`, `PersonSkill`,
`Knowledge`, `PersonKnowledge`, `Credential`, `Language`, `Evidence`,
`CareerGoal`, `IncomeTarget`, `PreferenceProfile`, `WorkValue`, `Constraint`, `LearningCapacity`,
`Career`, `CareerAlias`, `CareerSkillRequirement`, `CareerKnowledgeRequirement`,
`CareerRequirement`, `CareerAttribute`, `CareerRelation`, `ExternalMapping`,
`MarketSnapshot`, `SalarySnapshot`,
`MatchRun`, `CareerMatch`, `MatchComponent`, `FeasibilityFinding`, `PersonalGap`,
`CareerRoute`, `RouteStep`, `LearningOpportunity`, `Opportunity`.

## 4. AssessmentSession
- id
- user_id
- started_at / completed_at
- entry_mode: RESUME | MANUAL
- status
- methodology_version
- career_kb_version
- market_snapshot_version
- reset_from_session_id optional

Reset создаёт новую сессию, не перезаписывая историю.

## 5. SourceDocument
- id
- user_id
- assessment_session_id
- document_type
- filename / mime_type / file_size / storage_ref
- text_extraction_status
- parser_version
- created_at

Acceptance baseline: PDF с текстовым слоем, DOCX, TXT. Архитектура допускает другие text-extractable formats. OCR/scanned docs — последующий модуль.

## 6. CareerCard
- id
- user_id
- assessment_session_id
- version
- source_mode: RESUME | MANUAL | MIXED
- completeness_score_internal
- confidence_score_internal
- created_at / updated_at

Career Card = Career Capital + Career Intent.

## 7. Experience
- id / career_card_id
- company_name
- raw_job_title
- normalized_career_id optional
- industry_raw / industry_normalized_id optional
- start_date / end_date / is_current / duration_months
- seniority
- responsibilities_raw
- management_scope / team_size
- tools_raw
- source_type / confidence

## 8. Skill
Canonical:
- id = MNP_SKILL_ID
- canonical_name
- name_uk / name_en
- skill_type
- status ACTIVE | ARCHIVED
- taxonomy_version
- created_at / updated_at

### PersonSkill
- career_card_id / skill_id
- proficiency_level: BASIC | WORKING | STRONG
- evidence_strength
- years_used / last_used_at optional
- confidence
- source_type

## 9. Evidence
- id / career_card_id
- evidence_type: CLAIMED | INFERRED | VERIFIED
- source_type
- source_ref / excerpt optional
- strength / confidence
- created_at

Отсутствие confirmation screen не превращает inferred data в verified.

## 10. Knowledge / Education / Credentials / Languages
Knowledge и PersonKnowledge хранятся отдельно от Skill.

Education:
level, field, institution, qualification, country, years, recognition, evidence, confidence.

Credential:
type, name, issuer, dates, country, status, evidence.

Language:
language_code, overall/speaking/reading/writing/certified levels, evidence, confidence.

## 11. Career Intent
### CareerGoal
goal_type, priority, time_horizon.

### IncomeTarget
current_income optional; target_income; currency; period.

### PreferenceProfile
work objects, autonomy, teamwork, customer interaction, routine/novelty, leadership, physical activity, remote preference.

### WorkValue
value + priority rank.

### Constraint
type, value, severity PREFERENCE | STRONG | HARD, source, active.

### LearningCapacity
hours/week, max months, budget, willingness for credential, willingness for lower entry role.

## 12. Career
- id = MNP_CAREER_ID
- canonical_name
- name_uk / name_en
- description_short
- career_family_id
- status: DRAFT | ACTIVE | ARCHIVED
- catalog_priority
- published_at / reviewed_at / next_review_at
- career_profile_version

V1: 50 ACTIVE careers.

## 13. Career Catalog Management
Отдельный admin/editor module:
add, edit, activate, archive, restore, update mappings/requirements, schedule review.

Плановый review — ориентировочно ежемесячно.
Архивированные профессии исключаются из новых default runs, но остаются для исторической воспроизводимости.

## 14. Career requirements
### CareerSkillRequirement
career_id, skill_id, importance, required_level,
requirement_type MUST_HAVE | HIGH_VALUE | DIFFERENTIATOR | OPTIONAL,
source/version/confidence/validity.

### CareerKnowledgeRequirement
аналогично для knowledge.

### CareerRequirement
category EDUCATION | EXPERIENCE | CREDENTIAL | LANGUAGE | LEGAL | OTHER,
value, hardness SOFT | HARD, source, country, validity.

### CareerAttribute
work context, work style, interest, activity, ability и др.

## 15. ExternalMapping
- entity_type
- mnp_entity_id
- source_system
- external_id / label
- mapping_type EXACT | CLOSE | BROAD | NARROW
- confidence / source_version

V1 sources: ESCO, O*NET, ISCO, Ukrainian classifier и одобренные UA sources.
**Lightcast mappings отсутствуют.**

## 16. MarketSnapshot
- career_id
- country / region optional
- snapshot_date
- source / source_version
- data_quality / sample_size optional

Child facts: vacancy_count, salary, remote_share, demand trend, entry-level availability.
Market data не является постоянным свойством Career.

## 17. MatchRun
- id
- career_card_id / assessment_session_id
- methodology_version
- matching_engine_version
- career_kb_version
- market_data_version
- created_at

## 18. CareerMatch
- match_run_id / career_id
- rank_overall
- overall_score_internal
- display_band
- feasibility_status
- transition_distance
- confidence_internal
- is_featured

Numeric score в UI V1 не показывается.

## 19. MatchComponent
Components:
SKILL_FIT, EXPERIENCE_TRANSFER, KNOWLEDGE_FIT, PREFERENCE_FIT,
VALUES_FIT, FEASIBILITY, MARKET_ATTRACTIVENESS, INCOME_POTENTIAL, TRANSITION_COST.

Поля: score_internal, band, confidence, explanation_code.

## 20. FeasibilityFinding
finding_type, severity, requirement_id,
status PASS | GAP | BLOCKER,
explanation_code, evidence_ref.

## 21. PersonalGap
gap_type SKILL | KNOWLEDGE | EXPERIENCE | CREDENTIAL | LANGUAGE | PROOF | POSITIONING;
classification MUST_HAVE | HIGH_VALUE | DIFFERENTIATOR | OPTIONAL;
action LEARN | PRACTICE | PROVE | CERTIFY | REFRAME;
priority_internal, estimated_time, estimated_cost optional.

## 22. CareerRoute
route_type SAFE | GROWTH | TRANSFORM;
status, duration, cost.

RouteStep:
order, type, title, description, target_skill optional, opportunity optional, duration, completion_rule.

## 23. LearningOpportunity / Opportunity
Learning: provider, title, URL, country, format, cost, duration, credential, last_verified.

Opportunity types:
VACANCY | INTERNSHIP | PROJECT | TRAINING | GRANT | PROGRAM | MENTORSHIP.
Храним provider, title, career mapping, location/remote, URL, dates, status.

## 24. Key relationships
User 1—N AssessmentSession  
AssessmentSession 1—N SourceDocument  
AssessmentSession 1—1 CareerCard  
CareerCard 1—N Experience/Education/PersonSkill/...  
PersonSkill N—1 Skill  
Career 1—N CareerSkillRequirement N—1 Skill  
Career 1—N CareerRequirement  
Career 1—N MarketSnapshot  
CareerCard 1—N MatchRun  
MatchRun 1—N CareerMatch  
CareerMatch 1—N MatchComponent/PersonalGap/CareerRoute  
CareerRoute 1—N RouteStep

## 25. Explicit non-goals V1
- Lightcast;
- LLM ranking;
- mandatory personality test;
- guaranteed OCR;
- hardcoded permanent career list;
- user-facing pseudo-probability such as «87% chance».

## 26. Acceptance Criteria
Модель должна позволять:
1. создать Career Card с CV и без CV;
2. хранить 3-level skill proficiency;
3. хранить evidence/confidence;
4. описать Career независимо от external taxonomy;
5. добавлять/архивировать Career без изменения engine;
6. связать Person Skill ↔ Career Skill;
7. хранить hard requirements;
8. хранить dated market snapshots;
9. сохранить multidimensional Match;
10. сохранить personalized Gap и Route;
11. воспроизвести исторический MatchRun;
12. работать без Lightcast.

## 27. Founder Questions для FINAL
**DM-FQ-001.** Internal skill levels оставить `BASIC / WORKING / STRONG`? Рекомендация: да; UI labels позже.

**DM-FQ-002.** Career Card: одна живая master-card + versioned snapshots или отдельная карточка на каждое прохождение? Рекомендация: master-card + snapshots — это основа долгосрочной работы с клиентом.

**DM-FQ-003.** Без CV вопросы об опыте/образовании обязательны? Рекомендация: да, но адаптивно и только минимально необходимые.

**DM-FQ-004.** Кто управляет 50 профессиями? Рекомендация: ADMIN/EDITOR + audit log; после editorial policy Founder не утверждает каждую ежемесячную правку.

**DM-FQ-005.** Храним original CV после parsing? Рекомендация: да до удаления пользователем/аккаунта; retention окончательно фиксируем в GDPR/Privacy spec.

**DM-FQ-006.** Можно ли позже редактировать Career Card в кабинете? Рекомендация: да. Это не confirmation step, а постоянная функция профиля.

**DM-FQ-007.** Хранить `uk` + `en` названия Career/Skill уже в V1? Рекомендация: да: UK для продукта, EN для mappings/data interoperability.

## 28. После Founder Approval
Следующие документы:
1. `MNP_SKILL_SCHEMA_V1.md`
2. `MNP_CAREER_PROFILE_SCHEMA_V1.md`
3. `MNP_EVIDENCE_AND_CONFIDENCE_MODEL_V1.md`
