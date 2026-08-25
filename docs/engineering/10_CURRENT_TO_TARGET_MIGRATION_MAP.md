# Current → Target Migration Map (ICAN 1.1 → Product System v3.1)

Sprint 0, Part 2 (Issue #12). This document is **analysis and planning only**:
no production code, Alembic migration, or schema change is included in this
change. It exists so the Tech Lead / Founder / Methodology Lead can make
informed sequencing decisions before any of this is built.

Sources read to produce this map: `app/db/models.py`, `app/db/models_crm.py`
(current schema, as of commit `0bfac28`), `docs/architecture/02_ERD.md`
(target schema), `docs/architecture/01_SYSTEM_ARCHITECTURE.md`,
`docs/architecture/04_AI_SYSTEM.md`, `docs/engineering/09_MIGRATION_AND_TEAM_OWNERSHIP.md`.

## How to read this

Each current table gets one of four decisions:

| Decision | Meaning |
|---|---|
| **REUSE** | Keep as-is; no target entity exists yet, or the current shape is already fine. |
| **ADAPT** | A real target entity exists; getting there needs a deliberate, non-mechanical migration (new tables, backfill, dual-write, or a taxonomy that doesn't exist yet). |
| **DEPRECATE** | Superseded once the target entity is live; keep read-only as legacy reference, don't write to it anymore. |
| **REPLACE** | The current model and target model are different enough (different grain, different write pattern) that this is closer to a rewrite than a migration. |

Nothing here is scheduled — sequencing and "future migration" notes describe
*what would need to happen*, not a committed plan.

---

## Part A — Current entities mapped to target

### 1. `User` (`app/db/models.py`)

**Current purpose:** Telegram-bot-identified candidate. Primary key for the bot's own domain (`Profile`, `Message`) and the join point CRM uses to link a bot conversation to a `Client`.

**Current fields/relationships:** `id` (int PK), `telegram_id` (bigint, unique), `telegram_username`, `phone`, `email`, `screening_state` (enum: not_started/in_progress/paused/awaiting_confirmation/confirmed), `is_blocked`, `last_active_at`, timestamps. 1:1 → `Profile`, 1:N → `Message`. Also the FK target of `Client.telegram_user_id` (confusingly named — it stores `User.id`, not the raw Telegram id).

**Target v3.1 entity:** `USER` — but the target `USER` is channel-agnostic (UUID PK, email/phone/locale/timezone/deleted_at, no `telegram_id` field), scoped to a `TENANT` via `MEMBERSHIP`. Telegram becomes an auth channel, not the identity itself — implied by `09_MIGRATION_AND_TEAM_OWNERSHIP.md` Step 2 ("canonical User/AuthIdentity") but **`AuthIdentity` is never actually defined in `02_ERD.md`** — its shape has to be inferred.

**Decision:** ADAPT — and this is the highest-blast-radius migration in the system (see Part C, #1).

**Required future migration:**
- Add a new canonical `User` (UUID PK) + `AuthIdentity` (`provider="telegram"`, `provider_user_id`) table, additive — do **not** change the existing `users.id` int PK in place.
- Backfill one canonical `User` + one `AuthIdentity` row per existing bot `User`; keep a bridge column (e.g. nullable `canonical_user_id`) on the legacy table so both sides stay joinable during the transition.
- Only after every consumer reads the canonical id: deprecate the legacy table.

**Compatibility risks:** every current consumer keys off `User.id`/`telegram_id` directly and by-value (`app/bot/handlers.py`, `app/services/profile_service.py`, `app/services/admin_service.py`, `app/services/crm/bridge.py`, and effectively every test in the suite). A big-bang PK swap would break all of it simultaneously.

**Data-loss risk:** LOW for the additive-adapter approach. HIGH if anyone attempts an in-place PK-type migration instead — explicitly do not do that.

**Dependencies:** blocks `Profile`, `Message`, `ProfileEditLog`, `Client.telegram_user_id` — effectively everything downstream.

---

### 2. `Profile` (`app/db/models.py`)

**Current purpose:** single mutable row per bot `User` holding the AI-extracted screening facts. Overwritten turn by turn as the conversation progresses; `confirmed` flips once the candidate accepts the summary.

**Current fields:** `name`, `country`, `city`, `status`, `education`, `total_experience`, `previous_positions` (JSON list), `skills`/`languages` (JSON list of free strings), `desired_role`, `desired_min_income`, `desired_currency`, `employment_format`, `work_format`, `schedule`, `constraints`, `other_notes`, `extra_facts` (JSON), `confirmed`.

**Target v3.1 entity:** `POTENTIAL_PROFILE` + `PROFILE_CLAIM` (versioned, per-dimension `score`/`confidence`, evidence-linked via `EVIDENCE`) — a genuinely different write pattern: claims accumulate and version, they are not overwritten in place.

**Decision:** REPLACE (architecturally), not a field rename.

**Required future migration:**
- Blocked on the Methodology Lead freezing the claim taxonomy (`09_MIGRATION_AND_TEAM_OWNERSHIP.md` assigns this to Sprint 0 but it has not happened yet, as far as this repo shows) — there is no `dimension`/`label` vocabulary to migrate `Profile` fields *into*.
- Do **not** retroactively fabricate `EVIDENCE` rows with `confidence=1.0` for historical `Profile` data just to make old rows fit the new shape — that would misrepresent unverified legacy facts as evidence-graded ones.
- Practical bridge: keep `Profile` as the bot's live write target for now; once `InterviewSession`/`ANSWER` exist, *new* conversations can additionally emit `EVIDENCE`/`PROFILE_CLAIM`, without migrating historical `Profile` rows at all.
- `skills`/`languages` are free-text lists with no canonical ids — resolving them against a `SKILL` taxonomy (see #9) is a separate, nontrivial normalization project, not a migration script.

**Compatibility risks:** `app/bot/profile_card.py`, the admin dashboard, and `app/services/crm/bridge.py` all read `Profile` as a flat object with direct attribute access — none of that code works unmodified against a list of scored claim rows.

**Data-loss risk:** MEDIUM — free-text fields (e.g. a skills string like "трохи Excel, більше нічого") don't cleanly become a scored claim; recommend a Methodology review pass on a sample before trusting any bulk claim generation.

**Dependencies:** #1 (canonical User), Methodology taxonomy freeze, AI Gateway's Evidence Extractor / Profile Synthesizer (don't exist yet).

---

### 3. `Message` (`app/db/models.py`)

**Current purpose:** full USER/ASSISTANT transcript — doubles as the AI's rolling context window (`history_window`) and permanent audit log (`GET /users/{telegram_id}/messages`).

**Current fields:** `user_id`, `role` (enum), `content` (text), `created_at`.

**Target v3.1 entity:** closest is `ANSWER` (`session_id`, `question_id`, `answer_text`) — but `ANSWER` assumes a fixed/adaptive question bank driving one discrete answer at a time. The current agent is fully conversational (asks whatever it wants, not from a question bank), so there is no clean 1:1 mapping. **`02_ERD.md` has no "raw transcript" entity at all** — a gap.

**Decision:** ADAPT for new sessions once an Interview Orchestrator exists; REUSE as-is until then. Do not force free-form `Message` content into `ANSWER.question_id`.

**Required future migration:** none immediate. Once a real question bank exists, new sessions write `ANSWER` directly; raw conversational transcript likely needs its own (currently undefined) audit entity alongside it.

**Compatibility/data-loss risk:** low — nothing forces a change soon.

**Dependencies:** Interview Orchestrator (AI System doc component #1) must exist first.

---

### 4. `AdminUser` (`app/db/models.py`)

**Current purpose:** staff auth (ADMIN / MANAGER / CAREER_CONSULTANT), JWT+bcrypt login. Referenced by `Client.manager_id`/`consultant_id`, `Task.assignee_id`, `Call.employee_id`, `TimelineEvent.actor_id`, `ClientFile.uploaded_by_id`, `CareerConsultation.consultant_id`.

**Target v3.1 entity:** splits in two depending on role. ADMIN/MANAGER → internal staff `MEMBERSHIP` + role within a `TENANT` (no multi-tenancy exists today at all). CAREER_CONSULTANT → `GUIDE_PROFILE`, a first-class, monetizable role (`level`, `certification_status`, owns `CLIENT_RELATIONSHIP`/`GUIDE_SESSION`/`COMMISSION`) — much richer than today's flat `consultant_id` FK.

**Decision:** ADAPT (split).

**Required future migration:**
- Introduce `TENANT`/`MEMBERSHIP` (does not exist — every current query implicitly assumes a single tenant).
- For each `AdminUser` with `role=CAREER_CONSULTANT`, create a `GuideProfile` once that table exists.
- Separately noted: `ProfileEditLog.edited_by` is a **plain string, not an FK to `AdminUser`** — a pre-existing data-quality gap independent of v3.1, worth cleaning up before any audit-log migration relies on it.

**Compatibility risks:** current RBAC (`_require_roles`, `_ensure_visible` in `app/api/crm.py`) is role-string-based; v3.1's model is tenant+membership-scoped — a structurally different authorization model, not a rename.

**Data-loss risk:** LOW for `AdminUser` itself; MEDIUM for `ProfileEditLog.edited_by` (unstable string identity, not a real FK).

**Dependencies:** `TENANT`/`MEMBERSHIP`, `GUIDE_PROFILE` must exist first.

---

### 5. `ProfileEditLog` (`app/db/models.py`)

**Current purpose:** per-field audit trail for manual admin-dashboard edits (`old_value`/`new_value`/`edited_by`/`edited_at`).

**Target v3.1 entity:** `01_SYSTEM_ARCHITECTURE.md` §3 names `AuditLog` as a Platform-context entity, but **`02_ERD.md` never defines it** — no fields, no ERD node. See contradiction #1 in Part D.

**Decision:** REUSE as-is; there is nothing concrete to adapt to yet.

**Required future migration:** none until `AuditLog` gets an actual schema in the ERD.

**Compatibility/data-loss risk:** low. **Dependencies:** ERD needs an `AuditLog` definition (a documentation task, not an engineering one).

---

### 6. `Client` (`app/db/models_crm.py`)

**Current purpose:** canonical CRM record for a person the team works with, any channel; 7-stage pipeline status; ownership via `manager_id`/`consultant_id`; soft-delete.

**Current fields/relationships:** identity/contact block, `source_channel`, `telegram_user_id` FK → `users.id`, `manager_id`/`consultant_id` FK → `admin_users.id`, `status` (enum), `priority`, `is_deleted`, timestamps; 1:1 → `ClientProfile`, 1:N → `WorkExperience`/`ClientSkill`/`ClientLanguage`, 1:1 → `CareerConsultation`.

**Target v3.1 entity:** splits across **two** target entities: identity/contact fields belong on canonical `USER` (a candidate *is* the v3.1 platform user, not a separate shadow record); `status`/`manager_id`/`consultant_id`/`priority` belong on `CLIENT_RELATIONSHIP` (`client_user_id` ↔ `guide_id`, with its own `stage`/`status`) — a user↔guide *relationship* is explicitly its own row in the target model, which today's single mutable `consultant_id` FK cannot represent (e.g. no history of past consultants).

**Decision:** REPLACE (split), the **highest-risk single migration in this document** — see Part C, #2.

**Required future migration:**
- Merge `Client` contact/identity fields into canonical `USER`, deduplicating against the bot-side `User`/`AuthIdentity` migration (#1) — a `Client` linked via `telegram_user_id` and its corresponding bot `User` are the same human and must resolve to exactly one canonical `USER`.
- Move `status`/`manager_id`/`consultant_id`/`priority` into a new `CLIENT_RELATIONSHIP` row.
- `ClientStatus`'s 7 stages need an explicit mapping onto `CLIENT_RELATIONSHIP.stage` — not yet defined by Product/Methodology.
- **Open gap, no target equivalent:** `manager_id` (an ADMIN/MANAGER, not a Guide) has nowhere to go in `CLIENT_RELATIONSHIP`, which only models client↔guide. Today a `Client` can carry both a manager *and* a consultant simultaneously (`assign-manager` vs `assign-consultant` endpoints, both actively used) — this needs an explicit product decision before it can migrate.

**Compatibility risks:** HIGH — every CRM endpoint, RBAC scoping, the bot→CRM bridge, and 40+ existing tests assume `Client` is one row with one `consultant_id`.

**Data-loss risk:** MEDIUM — no field is deleted, but "one client, one consultant at a time" would need to become historical (multiple `CLIENT_RELATIONSHIP` rows over time); backfilling "current" vs "historical" from today's single mutable FK needs a product decision, not a script.

**Dependencies:** #1 (canonical User), #4 (`GUIDE_PROFILE`), Product decision on `manager_id`, `ClientStatus`→`stage` taxonomy.

---

### 7. `ClientProfile` (`app/db/models_crm.py`)

**Current purpose:** the CRM's detailed profile — employment situation (Block C), education (Block F), career target (Block H), hard constraints (Block I), practical constraints (Block J). Richer and more structured than the bot's `Profile`; consultant-verified.

**Target v3.1 entity:** primarily `GOAL` + `CONSTRAINT` + `EXPERIENCE` (Potential bounded context — named in `01_SYSTEM_ARCHITECTURE.md` §3 but **not present in `02_ERD.md`'s field-level model at all**, another spec gap). `primary_target`/`alternative_targets` anticipate `CAREER` once the Career Graph exists.

**Decision:** ADAPT — this is the richest, most human-verified structured data in the whole system and should not be discarded or silently replaced; needs a deliberate field-by-field decomposition once `GOAL`/`CONSTRAINT`/`EXPERIENCE` are actually specified.

**Required future migration:** same blocking dependency as `Profile` (#2) — Methodology taxonomy — plus `GOAL`/`CONSTRAINT`/`EXPERIENCE` need field-level design (currently just bounded-context names).

**Compatibility risks:** `critical_constraint` (a hard-block flag consultants set) is exactly the kind of thing `01_SYSTEM_ARCHITECTURE.md` §8 means by "hard constraints cannot be overridden by an LLM" — this safety property must be preserved with equivalent semantics wherever `CONSTRAINT` ends up modeled, not silently dropped.

**Data-loss risk:** LOW if migrated deliberately; HIGH if deprioritized while consultants keep entering data here and a parallel v3.1 flow is built without a sync path — that creates two divergent sources of truth.

**Dependencies:** `GOAL`/`CONSTRAINT`/`EXPERIENCE` need to be added to the ERD; Methodology taxonomy.

---

### 8. `WorkExperience` / 9. `ClientSkill` / 10. `ClientLanguage` (`app/db/models_crm.py`)

**Current purpose:** repeatable per-client blocks — jobs held, skills, languages.

**Target v3.1 entity:** `WorkExperience` → `EXPERIENCE`. `ClientSkill` → `USER_SKILL` (joins to a first-class `SKILL` taxonomy — doesn't exist; today `skill_name` is a free string with no canonical id). `ClientLanguage` → **no ERD entity at all** — languages are not mentioned anywhere in `02_ERD.md`.

**Decision:** `WorkExperience` — ADAPT (clean, low-risk, the row shape is already close to a generic experience record). `ClientSkill` — ADAPT, blocked on building/buying a `SKILL` taxonomy and a name-matching pass (real standalone work). `ClientLanguage` — REUSE as-is; there's nothing to migrate to yet.

**Required future migration:** skill-name canonicalization is the concrete blocking task for `ClientSkill` — nontrivial matching/normalization work, not a migration script.

**Compatibility risk:** low for `WorkExperience`; medium for `ClientSkill` (fuzzy matching can misclassify); unknown for `ClientLanguage` (no target to compare against).

**Data-loss risk:** low across all three if nothing is deleted prematurely.

**Dependencies:** `SKILL` taxonomy (new); ERD needs a language entity defined.

---

### 11. `CareerConsultation` (`app/db/models_crm.py`)

**Current purpose:** single consultant-authored conclusion per client (target role, strengths, skill gaps, search strategy, realistic-expectations flag) — today's human-only stand-in for what v3.1's `SCENARIO`/`DIRECTION_DECISION` pipeline is meant to eventually assist.

**Target v3.1 entity:** blends `GUIDE_SESSION`+`GUIDE_NOTE` (a guide's session output) with `DIRECTION_DECISION` (a chosen direction + rationale) — but structurally this is one mutable row per client, not the target's repeatable, timestamped, one-row-per-session model.

**Decision:** ADAPT — valuable, human-verified content worth preserving (e.g. as an initial `DirectionDecision.rationale` or `GuideNote`), but the grain mismatch (one-per-client vs one-per-session) needs an explicit decision, not an automatic mapping.

**Compatibility risk:** MEDIUM — `primary_target`/`alternative_targets` here already duplicate the same fields on `ClientProfile` (a pre-existing internal duplication in ICAN 1.1 itself, unrelated to v3.1, worth cleaning up regardless).

**Data-loss risk:** low if preserved as legacy reference.

**Dependencies:** `GUIDE_SESSION`/`GUIDE_NOTE`/`DIRECTION_DECISION` must exist first.

---

### 12. `ClientFile` (`app/db/models_crm.py`)

**Current purpose:** uploaded documents (CV, cover letter, certificates, diploma, portfolio), pluggable storage backend (`app/services/crm/storage.py`), current-CV flag, soft-delete.

**Target v3.1 entity:** **no document/file domain entity anywhere in `02_ERD.md`** — object storage is named only at the infra level (`01_SYSTEM_ARCHITECTURE.md` §7), never as a domain entity with metadata rows.

**Decision:** REUSE as-is until the target ERD defines a Document entity.

**Required future migration:** infra swap only (local filesystem → S3-compatible), already anticipated by the existing storage abstraction — low effort, not urgent.

**Compatibility/data-loss risk:** low. **Dependencies:** none blocking; flag the ERD gap.

---

### 13. `Call` (`app/db/models_crm.py`)

**Current purpose:** call log (direction, duration, employee, recording URL, notes); `phonet_call_id` implies a Phonet telephony integration.

**Target v3.1 entity:** no direct match — closest is `GUIDE_SESSION`, but that entity only carries `starts_at`/`status` in the ERD, no call-specific fields.

**Decision:** REUSE as-is short-term; ADAPT into a generalized Session/Interaction concept once Guide OS's session model actually grows to cover call-shaped interactions.

**Compatibility/data-loss risk:** low; nothing forces a change soon.

**Dependencies:** `GUIDE_SESSION`'s field-level spec needs to grow, or a sibling entity needs adding — an open target-design question, not decided here.

---

### 14. `Task` (`app/db/models_crm.py`)

**Current purpose:** staff-facing reminder/to-do tied to a client (call back, send document, clarify data) — internal CRM workflow tooling.

**Target v3.1 entity:** **name collision, not a match.** The target `TASK` (`ROADMAP` → `MILESTONE` → `TASK` → `TASK_EVIDENCE`) is a *candidate-facing* roadmap execution step a job-seeker completes as part of their 90-day plan. CRM's `Task` has nothing to do with that.

**Decision:** DO NOT map to v3.1 `TASK` — that would be a category error. Treat as its own ongoing Guide-OS-internal concept (REUSE for now; no ERD entity for it either).

**Compatibility/data-loss risk:** none from migration itself — but the *name collision* is itself a risk (easy to misread `Task` in code/docs later and assume it's the roadmap one). Recommend renaming the table (`Task`/`tasks` → e.g. `StaffTask`/`staff_tasks`) whenever this area is next touched, to remove the ambiguity. Not doing it now — out of scope for analysis-only Part 2.

**Dependencies:** none blocking; naming-collision flag for future work.

---

### 15. `TimelineEvent` (`app/db/models_crm.py`)

**Current purpose:** unified per-client audit/activity feed (created/status_changed/assigned/call/file_uploaded/…) with actor + before/after value.

**Target v3.1 entity:** same situation as `ProfileEditLog` (#5) — closest match is the undefined `AuditLog`.

**Decision:** REUSE as-is; same ERD-gap flag as #5.

**Compatibility/data-loss risk:** low. **Dependencies:** `AuditLog` needs a real definition in the ERD.

---

## Part B — Target v3.1 entities with no current equivalent

Grouped by bounded context (`01_SYSTEM_ARCHITECTURE.md` §3). None of these exist in ICAN 1.1 today — this is genuinely new territory, not a migration:

- **Identity/Tenancy:** `TENANT`, `MEMBERSHIP`, `CONSENT` — no multi-tenancy and **no consent tracking at all** today, worth flagging given this handles real candidates' personal data.
- **Discovery:** `INTERVIEW_SESSION`, `ANSWER` — no DB-backed session state machine exists; today's state is an in-memory aiogram FSM plus `User.screening_state`. The in-memory FSM is a confirmed architecture weakness (doesn't survive process restarts) independent of, and not yet proven to explain, the still-unresolved production button-cascade bug noted in the Part 1 risk list — see `11_TECHNICAL_DEBT_REGISTER.md` Item 4 for why those two are tracked separately.
- **Potential/Evidence:** `EVIDENCE`, `PROFILE_CLAIM`, `GOAL`, `CONSTRAINT` (as a first-class row, distinct from `ClientProfile`'s JSON blob), `EXPERIENCE` (as a first-class row), `SKILL`, `USER_SKILL`.
- **Career Intelligence:** `CAREER`, `CAREER_SKILL`, `CAREER_EDGE`, `MARKET_SIGNAL` — no career knowledge graph exists.
- **Decision:** `SCENARIO`, `SCENARIO_SCORE`, `DIRECTION_DECISION` — no scenario/recommendation engine exists.
- **Execution:** `ROADMAP`, `ROADMAP_VERSION`, `MILESTONE`, `TASK` (roadmap sense), `TASK_EVIDENCE`.
- **Opportunity:** `OPPORTUNITY`, `OPPORTUNITY_SKILL`, `OPPORTUNITY_MATCH`, `APPLICATION` — no job/vacancy matching exists today.
- **Guide OS:** `GUIDE_PROFILE`, `CLIENT_RELATIONSHIP`, `GUIDE_SESSION`, `GUIDE_NOTE` — today's `AdminUser` + `Client.consultant_id` is a much thinner stand-in (see #4, #6).
- **Outcome:** `OUTCOME_EVENT` — no longitudinal outcome tracking.
- **Growth/Billing:** `PAYMENT`, `COMMISSION`, `REFERRAL`, `ATTRIBUTION` — zero monetization infra; correctly out of scope until R2 per `docs/product/05_RELEASE_PLAN.md`.

---

## Part C — Highest-risk migrations

Ranked by combined blast radius × how undefined the target still is:

1. **User/AuthIdentity canonicalization (#1).** Touches every foreign key in the system. `AuthIdentity`'s actual shape isn't defined in `02_ERD.md` — has to be inferred from a prose instruction in `09_MIGRATION_AND_TEAM_OWNERSHIP.md`. Must land before almost anything else on this list.
2. **`Client` split into `USER` + `CLIENT_RELATIONSHIP` (#6).** Highest application-code blast radius (every CRM endpoint, RBAC scoping, the bot→CRM bridge, 40+ tests). Contains one genuinely unresolved product gap (`manager_id` has no home in the target model) that blocks a clean migration regardless of engineering effort.
3. **`Profile`/`ClientProfile` → `PotentialProfile`/`ProfileClaim`/`Evidence` (#2, #7).** Blocked on a Methodology taxonomy that doesn't exist yet; lossy by nature for free-text fields; risk of misrepresenting unverified legacy data as evidence-graded if rushed.
4. **`ClientSkill` → `SKILL`/`USER_SKILL` (#9).** Requires building or buying a skill taxonomy plus fuzzy-matching free-text skill names — a standalone data project, not a migration script.
5. **In-memory FSM → `InterviewSession`/`Answer`.** Architecturally necessary on its own merits (the current FSM doesn't survive process restarts), and may eliminate one class of state-related failures — but this must not be presented as a proven fix for the known, unresolved production button-cascade bug until that bug is reproduced, diagnosed, and verified against the new implementation (see `11_TECHNICAL_DEBT_REGISTER.md` Item 4). Either way it means rewriting the bot's entire state-handling logic, not adding a table alongside the existing one.

---

## Part D — Contradictions between the target ERD and the actual ICAN 1.1 code

1. `01_SYSTEM_ARCHITECTURE.md` §3 names `AuditLog` as a Platform-context entity, but `02_ERD.md` never defines it — meanwhile ICAN 1.1 already has two working tables (`ProfileEditLog`, `TimelineEvent`) implementing exactly this concept, with nothing concrete to map onto.
2. The ERD has no Document/File entity at all, while ICAN 1.1 already has a fully working `ClientFile` + pluggable storage abstraction covering exactly that.
3. `CLIENT_RELATIONSHIP` in the ERD only models client↔guide, but the CRM has a working, actively-used `manager_id` role (distinct from `consultant_id`, its own RBAC and assignment endpoint) with nowhere to go in the target model.
4. Target `TASK` (roadmap execution step, candidate-facing) and current `Task` (CRM staff reminder, internal) share a name but are unrelated concepts — a naming collision, not overlap; a blind field-mapping between them would corrupt data.
5. `02_ERD.md`'s database rule #2 ("every changing recommendation object has a version or immutable history record") is already at odds with the *current* `Profile`/`ClientProfile` tables, which are mutated in place with no history — not a contradiction inside the target doc, but worth the team noticing that Part 1 just froze this exact behavior as the regression baseline (correctly, per "evolution not rewrite" — just flagging it so nobody assumes the baseline already satisfies this rule).
6. No language taxonomy entity exists anywhere in `02_ERD.md` (skills get `SKILL`/`USER_SKILL`; languages don't appear at all), even though ICAN 1.1 already tracks language + proficiency + work-eligibility as first-class repeatable data (`ClientLanguage`).
7. `09_MIGRATION_AND_TEAM_OWNERSHIP.md` Step 2 says "keep current Telegram IDs for compatibility" via an "AuthIdentity" structure, but `02_ERD.md`'s entity list never defines `AuthIdentity` — its shape in this document (Part A, #1) is inferred, not sourced. Worth the Tech Lead confirming intent before anyone builds it.

---

## Migration strategy summary

- **Evolution, not rewrite** (per `09_MIGRATION_AND_TEAM_OWNERSHIP.md`): every migration above is additive/adapter-based. Nothing gets deleted until the new flow is verified and reads have switched over.
- **Sequencing is dependency-constrained, not arbitrary:** canonical User/AuthIdentity (#1) has to land first since nearly everything else FKs to a user. Consent/InterviewSession comes next (also fixes the known FSM bug). AI Gateway wrapping (Part 4 of this sprint) doesn't require schema changes and can happen in parallel. Evidence/ProfileClaim is blocked on the Methodology taxonomy freeze. Career/Scenario/Roadmap is greenfield (no legacy data to migrate, but also no urgency ahead of R0/R1 per the release plan). Guide OS evolution of the CRM is blocked on the `Client` split decision and the `manager_id` gap. Billing/Referral is correctly out of scope until R2.
- **Two upstream decisions block real progress and are not engineering tasks:**
  1. Methodology Lead's claim taxonomy freeze — assigned in Sprint 0 by `09_MIGRATION_AND_TEAM_OWNERSHIP.md`, not yet done as far as this repo shows. Blocks #2, #7, and indirectly #9.
  2. Product decision on where `manager_id` (and Client↔Manager assignment generally) fits in the target relationship model — blocks #6 cleanly resolving.
- This document does not resolve either of those; they're surfaced for the Tech Lead / Founder / Methodology Lead, per the role ownership matrix already defined in `09_MIGRATION_AND_TEAM_OWNERSHIP.md`.
