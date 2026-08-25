# Current → Target Migration Map (ICAN 1.1 → Product System v3.1)

Sprint 0, Part 2 (Issue #12). This document is **analysis and planning only**:
no production code, Alembic migration, or schema change is included in this
change. It exists so the Tech Lead / Founder / Methodology Lead can make
informed sequencing decisions before any of this is built.

> Reconciled by the Founder Architecture Review
> (`docs/engineering/13_FOUNDER_ARCHITECTURE_REVIEW.md`), which specified
> `AuthIdentity`, hardened `Consent`, added the versioned Taxonomy
> architecture, `ClientAssignment`, `InterviewMessage`, field-level
> `Goal`/`Constraint`/`Experience`, `Language`/`UserLanguage`, renamed the
> roadmap `Task` to `RoadmapTask`, and added `AuditLog`/`AiTrace` to
> `docs/architecture/02_ERD.md`. Every place below that previously said a
> target entity "isn't defined" or "has no ERD node" has been updated —
> the entities now have field-level specs, but **none of them are
> implemented as schema/migrations yet**. Spec existing is not the same as
> migration risk going away; see the updated Part C.

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

**Target v3.1 entity:** `USER` — but the target `USER` is channel-agnostic (UUID PK, email/phone/locale/timezone/deleted_at, no `telegram_id` field), scoped to a `TENANT` via `MEMBERSHIP`. Telegram becomes an auth channel, not the identity itself. `AUTH_IDENTITY` is now a fully specified ERD entity (Founder Architecture Review): `id`, `user_id` FK, `provider`, `provider_subject`, `provider_username`, `verified_at`, `last_seen_at`, `revoked_at`, `created_at`, `UNIQUE(provider, provider_subject)` — a Telegram id becomes one `AUTH_IDENTITY` row (`provider="telegram"`, `provider_subject=<telegram_id>`), never the `USER` identity itself.

**Decision:** ADAPT — and this is the highest-blast-radius migration in the system (see Part C, #1).

**Required future migration:**
- Add new canonical `User` (UUID PK) + `AuthIdentity` tables per the now-fixed ERD shape, additive — do **not** change the existing `users.id` int PK in place.
- Backfill one canonical `User` + one `AuthIdentity` (`provider="telegram"`, `provider_subject=<telegram_id>`) row per existing bot `User`; keep a bridge column (e.g. nullable `canonical_user_id`) on the legacy table so both sides stay joinable during the transition.
- Only after every consumer reads the canonical id: deprecate the legacy table.

**Compatibility risks:** every current consumer keys off `User.id`/`telegram_id` directly and by-value (`app/bot/handlers.py`, `app/services/profile_service.py`, `app/services/admin_service.py`, `app/services/crm/bridge.py`, and effectively every test in the suite). A big-bang PK swap would break all of it simultaneously. The spec being finalized does not reduce this — it only removes the ambiguity about *what* to build.

**Data-loss risk:** LOW for the additive-adapter approach. HIGH if anyone attempts an in-place PK-type migration instead — explicitly do not do that.

**Dependencies:** blocks `Profile`, `Message`, `ProfileEditLog`, `Client.telegram_user_id` — effectively everything downstream.

---

### 2. `Profile` (`app/db/models.py`)

**Current purpose:** single mutable row per bot `User` holding the AI-extracted screening facts. Overwritten turn by turn as the conversation progresses; `confirmed` flips once the candidate accepts the summary.

**Current fields:** `name`, `country`, `city`, `status`, `education`, `total_experience`, `previous_positions` (JSON list), `skills`/`languages` (JSON list of free strings), `desired_role`, `desired_min_income`, `desired_currency`, `employment_format`, `work_format`, `schedule`, `constraints`, `other_notes`, `extra_facts` (JSON), `confirmed`.

**Target v3.1 entity:** `POTENTIAL_PROFILE` + `PROFILE_CLAIM` (versioned, per-dimension `score`/`confidence`, evidence-linked via `EVIDENCE`) — a genuinely different write pattern: claims accumulate and version, they are not overwritten in place.

**Decision:** REPLACE (architecturally), not a field rename.

**Required future migration:**
- Blocked on Taxonomy v1's actual content. The versioning **architecture** now exists (`TAXONOMY`/`TAXONOMY_VERSION`/`TAXONOMY_TERM`, Founder Architecture Review) and `PROFILE_CLAIM.taxonomy_version_id` gives the concrete traceability link — but Taxonomy v1's own `dimension`/`label` vocabulary is still not designed (debt register Item 11) — there is nothing to migrate `Profile` fields *into* yet.
- Do **not** retroactively fabricate `EVIDENCE` rows with `confidence=1.0` for historical `Profile` data just to make old rows fit the new shape — that would misrepresent unverified legacy facts as evidence-graded ones.
- Practical bridge: keep `Profile` as the bot's live write target for now; once `InterviewSession`/`ANSWER` exist, *new* conversations can additionally emit `EVIDENCE`/`PROFILE_CLAIM`, without migrating historical `Profile` rows at all.
- `skills`/`languages` are free-text lists with no canonical ids — resolving `skills` against a `SKILL` taxonomy (see #9) is a separate, nontrivial normalization project. `languages` now has a concrete target (`LANGUAGE`/`USER_LANGUAGE`, see #9) instead of no entity at all.

**Compatibility risks:** `app/bot/profile_card.py`, the admin dashboard, and `app/services/crm/bridge.py` all read `Profile` as a flat object with direct attribute access — none of that code works unmodified against a list of scored claim rows.

**Data-loss risk:** MEDIUM — free-text fields (e.g. a skills string like "трохи Excel, більше нічого") don't cleanly become a scored claim; recommend a Methodology review pass on a sample before trusting any bulk claim generation.

**Dependencies:** #1 (canonical User), Taxonomy v1 content (architecture decided and specified, dimension/label content still open — debt register Item 11), AI Gateway's Evidence Extractor / Profile Synthesizer (don't exist yet).

---

### 3. `Message` (`app/db/models.py`)

**Current purpose:** full USER/ASSISTANT transcript — doubles as the AI's rolling context window (`history_window`) and permanent audit log (`GET /users/{telegram_id}/messages`).

**Current fields:** `user_id`, `role` (enum), `content` (text), `created_at`.

**Target v3.1 entity:** `INTERVIEW_MESSAGE` (`session_id`, `role`, `content`, `sequence`, `created_at` — Founder Architecture Review) is now the direct target for raw conversational transcript, distinct from `ANSWER` (`session_id`, `question_id`, `answer_text`), which assumes a fixed/adaptive question bank driving one discrete answer at a time. The current agent is fully conversational (asks whatever it wants, not from a question bank), so `Message` maps to `INTERVIEW_MESSAGE`, not `ANSWER` — this is no longer a gap, it was resolved by adding a second, distinct entity rather than forcing one mapping to do both jobs.

**Decision:** ADAPT once `InterviewSession`/`InterviewMessage` exist; REUSE as-is until then.

**Required future migration:** none immediate. Once `InterviewSession` exists, new sessions write `INTERVIEW_MESSAGE` directly for the raw transcript; a real question bank (Interview Orchestrator) would additionally let some turns produce a structured `ANSWER` alongside it. Retention/redaction policy for `INTERVIEW_MESSAGE` is not defined by this document — that's Consent/Privacy scope.

**Compatibility/data-loss risk:** low — nothing forces a change soon.

**Dependencies:** `InterviewSession` (#1-adjacent); Interview Orchestrator (AI System doc component #1) only needed for `ANSWER`, not for `INTERVIEW_MESSAGE`.

---

### 4. `AdminUser` (`app/db/models.py`)

**Current purpose:** staff auth (ADMIN / MANAGER / CAREER_CONSULTANT), JWT+bcrypt login. Referenced by `Client.manager_id`/`consultant_id`, `Task.assignee_id`, `Call.employee_id`, `TimelineEvent.actor_id`, `ClientFile.uploaded_by_id`, `CareerConsultation.consultant_id`.

**Target v3.1 entity:** splits in two depending on role. ADMIN/MANAGER → internal staff `MEMBERSHIP` + role within a `TENANT` (no multi-tenancy exists today at all). CAREER_CONSULTANT → `GUIDE_PROFILE`, a first-class, monetizable role (`level`, `certification_status`, owns `CLIENT_RELATIONSHIP`/`GUIDE_SESSION`/`COMMISSION`) — much richer than today's flat `consultant_id` FK. MANAGER's operational-assignment role specifically now also maps onto `CLIENT_ASSIGNMENT` (see #6).

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

**Target v3.1 entity:** `AUDIT_LOG` — now a fully specified ERD entity (Founder Architecture Review): `id`, `actor_user_id` (nullable), `tenant_id`, `entity_type`, `entity_id`, `action`, `before_snapshot`/`after_snapshot` (nullable JSON), `occurred_at`. Append-only by design (`02_ERD.md` database rule #8). This was previously named only in prose (`01_SYSTEM_ARCHITECTURE.md` §3) with no ERD node at all — that gap is now closed at the spec level.

**Decision:** ADAPT — a real target now exists to adapt to (previously REUSE, since there was nothing concrete to adapt to).

**Required future migration:** map `ProfileEditLog` rows onto `AUDIT_LOG` shape (`entity_type="profile"`, `action="update"`, `before_snapshot`/`after_snapshot` from `old_value`/`new_value`) once `AUDIT_LOG` is implemented. Blocked on `AdminUser`/canonical User work for `actor_user_id`, and on resolving `ProfileEditLog.edited_by`'s string-not-FK gap (see #4) first — a string actor can't cleanly become a UUID `actor_user_id`.

**Compatibility/data-loss risk:** low. **Dependencies:** #1 (canonical User) and #4 (`ProfileEditLog.edited_by` FK cleanup) before this can actually migrate; the ERD gap itself is resolved.

---

### 6. `Client` (`app/db/models_crm.py`)

**Current purpose:** canonical CRM record for a person the team works with, any channel; 7-stage pipeline status; ownership via `manager_id`/`consultant_id`; soft-delete.

**Current fields/relationships:** identity/contact block, `source_channel`, `telegram_user_id` FK → `users.id`, `manager_id`/`consultant_id` FK → `admin_users.id`, `status` (enum), `priority`, `is_deleted`, timestamps; 1:1 → `ClientProfile`, 1:N → `WorkExperience`/`ClientSkill`/`ClientLanguage`, 1:1 → `CareerConsultation`.

**Target v3.1 entity:** splits across **three** places: identity/contact fields belong on canonical `USER`; `status`/`consultant_id`/`priority` belong on `CLIENT_RELATIONSHIP` (`client_user_id` ↔ `guide_id`, with its own `stage`/`status`); `manager_id` belongs on `CLIENT_ASSIGNMENT` — now a fully specified ERD entity (Founder Architecture Review): `id`, `client_user_id`, `assignee_user_id`, `tenant_id`, `assignment_type` (`MANAGER`/`COORDINATOR`, extensible), `status`, `valid_from`, `valid_to` (nullable), `assigned_by_user_id`, `created_at`. Multiple historical rows per `client_user_id` can represent assignment history — something today's single mutable `manager_id` FK cannot do.

**Decision:** REPLACE (split), the **highest-risk single migration in this document** — see Part C, #2.

**Required future migration:**
- Merge `Client` contact/identity fields into canonical `USER`, deduplicating against the bot-side `User`/`AuthIdentity` migration (#1) — a `Client` linked via `telegram_user_id` and its corresponding bot `User` are the same human and must resolve to exactly one canonical `USER`.
- Move `status`/`consultant_id`/`priority` into a new `CLIENT_RELATIONSHIP` row.
- `ClientStatus`'s 7 stages need an explicit mapping onto `CLIENT_RELATIONSHIP.stage` — not yet defined.
- Move `manager_id` into `CLIENT_ASSIGNMENT` (`assignment_type="MANAGER"`) now that its schema exists. Until implemented, `manager_id`'s current semantics are preserved unchanged — this is now a fully specified, purely implementation-scoped migration, not an open design question.

**Compatibility risks:** HIGH — every CRM endpoint, RBAC scoping, the bot→CRM bridge, and 40+ existing tests assume `Client` is one row with one `consultant_id` (and, separately, one `manager_id`).

**Data-loss risk:** MEDIUM — no field is deleted, but "one client, one consultant/manager at a time" becomes historical (multiple `CLIENT_RELATIONSHIP`/`CLIENT_ASSIGNMENT` rows over time); backfilling "current" vs "historical" from today's single mutable FKs needs deliberate design, not a script.

**Dependencies:** #1 (canonical User), #4 (`GUIDE_PROFILE`), `TENANT` (for `CLIENT_ASSIGNMENT.tenant_id`), `ClientStatus`→`stage` taxonomy.

---

### 7. `ClientProfile` (`app/db/models_crm.py`)

**Current purpose:** the CRM's detailed profile — employment situation (Block C), education (Block F), career target (Block H), hard constraints (Block I), practical constraints (Block J). Richer and more structured than the bot's `Profile`; consultant-verified.

**Target v3.1 entity:** primarily `GOAL` + `CONSTRAINT` + `EXPERIENCE` — now fully field-specified (Founder Architecture Review; previously only bounded-context names). `primary_target`/`alternative_targets` anticipate `CAREER` once the Career Graph exists.

**Decision:** ADAPT — this is the richest, most human-verified structured data in the whole system and should not be discarded or silently replaced; the field-by-field decomposition can now actually be planned against a concrete target shape.

**Required future migration:** same blocking dependency as `Profile` (#2) — Taxonomy v1's content (architecture decided and specified, content still open) — plus mapping each `ClientProfile` field onto `GOAL`/`CONSTRAINT`/`EXPERIENCE`'s now-defined columns (e.g. `search_reasons`/`readiness_to_start` → `GOAL`; `constraints`/`constraints_comment`/`critical_constraint` → `CONSTRAINT`; nothing currently maps to `EXPERIENCE` here, that's `WorkExperience`, see #8).

**Compatibility risks:** `critical_constraint` (a hard-block flag consultants set) now maps directly onto `CONSTRAINT.is_hard` (Founder Architecture Review, explicitly required to gate scenario/recommendation generation server-side per `01_SYSTEM_ARCHITECTURE.md` §8 and `02_ERD.md` database rule #9) — preserving this exact semantic through the migration is now a defined requirement, not just a risk to watch for.

**Data-loss risk:** LOW if migrated deliberately; HIGH if deprioritized while consultants keep entering data here and a parallel v3.1 flow is built without a sync path — that creates two divergent sources of truth.

**Dependencies:** Taxonomy v1 content (architecture specified, content open).

---

### 8. `WorkExperience` / 9. `ClientSkill` / 10. `ClientLanguage` (`app/db/models_crm.py`)

**Current purpose:** repeatable per-client blocks — jobs held, skills, languages.

**Target v3.1 entity:** `WorkExperience` → `EXPERIENCE` (now field-specified: `title`, `organization`, `start_period`, `end_period`, `description`). `ClientSkill` → `USER_SKILL` (joins to a first-class `SKILL` taxonomy — Skills is one of the Taxonomy v1 categories per Decision 2, but its content doesn't exist yet; today `skill_name` is a free string with no canonical id). `ClientLanguage` → `LANGUAGE`/`USER_LANGUAGE` — now a fully specified ERD entity pair (Founder Architecture Review), not the "no ERD entity at all" gap this used to be.

**Decision:** `WorkExperience` — ADAPT (clean, low-risk; field names line up closely with `EXPERIENCE`'s now-defined columns). `ClientSkill` — ADAPT, blocked on designing the Skills portion of Taxonomy v1 and a name-matching pass (real standalone work). `ClientLanguage` — ADAPT (a real target now exists: `LANGUAGE`/`USER_LANGUAGE`, with `proficiency_level` and `evidence_source` mirroring what `ClientLanguage.level`/`can_work_in_it` already capture) — previously REUSE, since there was nothing to migrate to.

**Required future migration:** skill-name canonicalization is the concrete blocking task for `ClientSkill` — nontrivial matching/normalization work, not a migration script. `ClientLanguage` needs a `LANGUAGE` reference table seeded (language codes/names) and a mapping from `ClientLanguage.level`/`can_work_in_it` onto `USER_LANGUAGE.proficiency_level`/`evidence_source` — much more mechanical than the skill-matching problem.

**Compatibility risk:** low for `WorkExperience` and `ClientLanguage`; medium for `ClientSkill` (fuzzy matching can misclassify).

**Data-loss risk:** low across all three if nothing is deleted prematurely.

**Dependencies:** Taxonomy v1's Skills content (architecture specified, content open) for `ClientSkill`; none blocking for `WorkExperience`/`ClientLanguage` beyond normal implementation sequencing.

---

### 11. `CareerConsultation` (`app/db/models_crm.py`)

**Current purpose:** single consultant-authored conclusion per client (target role, strengths, skill gaps, search strategy, realistic-expectations flag) — today's human-only stand-in for what v3.1's `SCENARIO`/`DIRECTION_DECISION` pipeline is meant to eventually assist.

**Target v3.1 entity:** blends `GUIDE_SESSION`+`GUIDE_NOTE` (a guide's session output) with `DIRECTION_DECISION` (a chosen direction + rationale) — but structurally this is one mutable row per client, not the target's repeatable, timestamped, one-row-per-session model. `GUIDE_NOTE` itself still has no field-level ERD definition — unaffected by this review.

**Decision:** ADAPT — valuable, human-verified content worth preserving (e.g. as an initial `DirectionDecision.rationale` or `GuideNote`), but the grain mismatch (one-per-client vs one-per-session) needs an explicit decision, not an automatic mapping.

**Compatibility risk:** MEDIUM — `primary_target`/`alternative_targets` here already duplicate the same fields on `ClientProfile` (a pre-existing internal duplication in ICAN 1.1 itself, unrelated to v3.1, worth cleaning up regardless).

**Data-loss risk:** low if preserved as legacy reference.

**Dependencies:** `GUIDE_SESSION`/`GUIDE_NOTE`/`DIRECTION_DECISION` must exist first; `GUIDE_NOTE`'s own field-level spec is still open (not part of this review).

---

### 12. `ClientFile` (`app/db/models_crm.py`)

**Current purpose:** uploaded documents (CV, cover letter, certificates, diploma, portfolio), pluggable storage backend (`app/services/crm/storage.py`), current-CV flag, soft-delete.

**Target v3.1 entity:** **still no document/file domain entity anywhere in `02_ERD.md`** — object storage is named only at the infra level (`01_SYSTEM_ARCHITECTURE.md` §7), never as a domain entity with metadata rows. Not addressed by the Founder Architecture Review — remains open.

**Decision:** REUSE as-is until the target ERD defines a Document entity.

**Required future migration:** infra swap only (local filesystem → S3-compatible), already anticipated by the existing storage abstraction — low effort, not urgent.

**Compatibility/data-loss risk:** low. **Dependencies:** none blocking; flag the ERD gap (see Part D, #2 — still open).

---

### 13. `Call` (`app/db/models_crm.py`)

**Current purpose:** call log (direction, duration, employee, recording URL, notes); `phonet_call_id` implies a Phonet telephony integration.

**Target v3.1 entity:** no direct match — closest is `GUIDE_SESSION`, but that entity only carries `starts_at`/`status` in the ERD, no call-specific fields. Not addressed by the Founder Architecture Review — remains open.

**Decision:** REUSE as-is short-term; ADAPT into a generalized Session/Interaction concept once Guide OS's session model actually grows to cover call-shaped interactions.

**Compatibility/data-loss risk:** low; nothing forces a change soon.

**Dependencies:** `GUIDE_SESSION`'s field-level spec needs to grow, or a sibling entity needs adding — an open target-design question, not decided here.

---

### 14. `Task` (`app/db/models_crm.py`)

**Current purpose:** staff-facing reminder/to-do tied to a client (call back, send document, clarify data) — internal CRM workflow tooling.

**Target v3.1 entity:** the target entity is now named `ROADMAP_TASK` specifically to remove the collision this section originally flagged (`ROADMAP` → `MILESTONE` → `ROADMAP_TASK` → `TASK_EVIDENCE`, Founder Architecture Review) — a *candidate-facing* roadmap execution step a job-seeker completes as part of their 90-day plan. CRM's `Task` still has nothing to do with that; the rename resolves the naming collision, not a mapping between the two.

**Decision:** DO NOT map to v3.1 `ROADMAP_TASK` — still a category error, now just harder to make by accident since the names no longer collide. Treat CRM `Task` as its own ongoing Guide-OS-internal concept (REUSE for now; still no ERD entity for it).

**Compatibility/data-loss risk:** none from migration itself. The Founder Architecture Review resolved this by renaming the *target* entity, explicitly choosing **not** to rename the existing, in-production CRM table (`Task`/`tasks`) as part of an architecture-only step — that stays a separate, deliberately deferred decision for whenever this area is actually touched.

**Dependencies:** none blocking.

---

### 15. `TimelineEvent` (`app/db/models_crm.py`)

**Current purpose:** unified per-client audit/activity feed (created/status_changed/assigned/call/file_uploaded/…) with actor + before/after value.

**Target v3.1 entity:** same situation as `ProfileEditLog` (#5) — `AUDIT_LOG` is now fully specified.

**Decision:** ADAPT — same upgrade from REUSE as #5, for the same reason.

**Compatibility/data-loss risk:** low. **Dependencies:** #1 (canonical User) for `actor_user_id`; `TimelineEvent.actor_id` is already a real FK to `AdminUser` (unlike `ProfileEditLog.edited_by`), so this migration is comparatively cleaner than #5's.

---

## Part B — Target v3.1 entities with no current equivalent

Grouped by bounded context (`01_SYSTEM_ARCHITECTURE.md` §3). None of these exist in ICAN 1.1 today — this is genuinely new territory, not a migration. Several now have full field-level specs (Founder Architecture Review) even though nothing has been implemented:

- **Identity/Tenancy:** `TENANT`, `MEMBERSHIP`, `AUTH_IDENTITY` (now field-specified), `CONSENT` (now hardened — versioned, purpose-specific, traceable to `granted_by_user_id`/`source`, withdrawable, and capable of future minor/guardian consent without redesigning `USER`) — still **no consent tracking implementation exists** today, worth flagging given this handles real candidates' personal data.
- **Discovery:** `INTERVIEW_SESSION`, `ANSWER`, `INTERVIEW_MESSAGE` (new, Founder Architecture Review — the raw-transcript entity `Message` now maps onto) — no DB-backed session state machine exists; today's state is an in-memory aiogram FSM plus `User.screening_state`. The in-memory FSM is a confirmed architecture weakness (doesn't survive process restarts) independent of, and not yet proven to explain, the still-unresolved production button-cascade bug noted in the Part 1 risk list — see `11_TECHNICAL_DEBT_REGISTER.md` Item 4 for why those two are tracked separately.
- **Taxonomy (new bounded context):** `TAXONOMY`, `TAXONOMY_VERSION`, `TAXONOMY_TERM` (Founder Architecture Review) — the versioning architecture now exists; Taxonomy v1's actual content does not.
- **Potential/Evidence:** `EVIDENCE`, `PROFILE_CLAIM` (now with `taxonomy_version_id`), `GOAL`, `CONSTRAINT` (now with `is_hard`), `EXPERIENCE`, `SKILL`, `USER_SKILL`, `LANGUAGE`, `USER_LANGUAGE` (new, Founder Architecture Review).
- **Career Intelligence:** `CAREER`, `CAREER_SKILL`, `CAREER_EDGE`, `MARKET_SIGNAL` — no career knowledge graph exists.
- **Decision:** `SCENARIO`, `SCENARIO_SCORE`, `DIRECTION_DECISION` — no scenario/recommendation engine exists.
- **Execution:** `ROADMAP`, `ROADMAP_VERSION`, `MILESTONE`, `ROADMAP_TASK` (renamed from `TASK`, Founder Architecture Review), `TASK_EVIDENCE`.
- **Opportunity:** `OPPORTUNITY`, `OPPORTUNITY_SKILL`, `OPPORTUNITY_MATCH`, `APPLICATION` — no job/vacancy matching exists today.
- **Guide OS:** `GUIDE_PROFILE`, `CLIENT_RELATIONSHIP`, `CLIENT_ASSIGNMENT` (new, Founder Architecture Review — see #6), `GUIDE_SESSION`, `GUIDE_NOTE` — today's `AdminUser` + `Client.consultant_id`/`manager_id` is a much thinner stand-in (see #4, #6).
- **Outcome:** `OUTCOME_EVENT` — no longitudinal outcome tracking.
- **Growth/Billing:** `PAYMENT`, `COMMISSION`, `REFERRAL`, `ATTRIBUTION` — zero monetization infra; correctly out of scope until R2 per `docs/product/05_RELEASE_PLAN.md`.
- **Platform:** `AUDIT_LOG`, `AI_TRACE` (both new, Founder Architecture Review) — no implementation exists; `AI_TRACE`'s data is currently structured-logged by `app/ai_gateway.py`, not persisted.

---

## Part C — Highest-risk migrations

Ranked by combined blast radius × how undefined the target still is. The Founder Architecture Review closed several *specification* gaps below — none of it reduces the *implementation* blast radius, which is what this ranking is actually about:

1. **User/AuthIdentity canonicalization (#1).** Touches every foreign key in the system. `AuthIdentity`'s shape is now fully defined in `02_ERD.md` (Founder Architecture Review) — the ambiguity that used to compound this risk is gone, but the migration's blast radius (every FK in the system) is unchanged. Must land before almost anything else on this list.
2. **`Client` split into `USER` + `CLIENT_RELATIONSHIP` + `CLIENT_ASSIGNMENT` (#6).** Highest application-code blast radius (every CRM endpoint, RBAC scoping, the bot→CRM bridge, 40+ tests). `manager_id`'s destination is now fully specified (`CLIENT_ASSIGNMENT`, Founder Architecture Review) — this used to be an open product gap, now it's purely an implementation task, but still the second-highest blast radius in the system.
3. **`Profile`/`ClientProfile` → `PotentialProfile`/`ProfileClaim`/`Evidence`/`Goal`/`Constraint`/`Experience` (#2, #7).** The target entities are now field-specified, and `CONSTRAINT.is_hard` gives `critical_constraint` a concrete destination — but Taxonomy v1's actual content still doesn't exist, so `PROFILE_CLAIM.dimension`/`.label` still have nothing to migrate `Profile` fields into. Lossy by nature for free-text fields; risk of misrepresenting unverified legacy data as evidence-graded if rushed.
4. **`ClientSkill` → `SKILL`/`USER_SKILL` (#9).** Requires designing the Skills portion of Taxonomy v1 plus fuzzy-matching free-text skill names — a standalone data project, not a migration script. (`ClientLanguage` → `LANGUAGE`/`USER_LANGUAGE` no longer belongs on this list — it dropped from "no target exists" to a comparatively mechanical ADAPT once the entity pair was specified.)
5. **In-memory FSM → `InterviewSession`/`Answer`/`InterviewMessage`.** Architecturally necessary on its own merits (the current FSM doesn't survive process restarts), and may eliminate one class of state-related failures — but this must not be presented as a proven fix for the known, unresolved production button-cascade bug until that bug is reproduced, diagnosed, and verified against the new implementation (see `11_TECHNICAL_DEBT_REGISTER.md` Item 4). `InterviewMessage` (Founder Architecture Review) now gives raw transcript a real destination alongside `Answer`, but the rewrite of the bot's entire state-handling logic is unchanged in scope.

---

## Part D — Contradictions between the target ERD and the actual ICAN 1.1 code

Contradictions closed by the Founder Architecture Review are marked **RESOLVED** — the underlying implementation gap is not closed, only the documentation contradiction that used to sit on top of it.

1. **RESOLVED.** `01_SYSTEM_ARCHITECTURE.md` §3 named `AuditLog` as a Platform-context entity while `02_ERD.md` never defined it, even though ICAN 1.1 already has two working tables (`ProfileEditLog`, `TimelineEvent`) implementing exactly this concept. `AUDIT_LOG` now has a full field-level definition in `02_ERD.md`.
2. **Still open.** The ERD has no Document/File entity at all, while ICAN 1.1 already has a fully working `ClientFile` + pluggable storage abstraction covering exactly that. Not addressed by this review.
3. **RESOLVED.** `CLIENT_RELATIONSHIP` in the ERD only modeled client↔guide, with nowhere for the CRM's working, actively-used `manager_id` role to go. `CLIENT_ASSIGNMENT` now exists as a fully specified, separate entity for exactly that.
4. **RESOLVED.** Target `TASK` (roadmap execution step, candidate-facing) and current `Task` (CRM staff reminder, internal) shared a name despite being unrelated concepts. The target entity is now named `ROADMAP_TASK`; the CRM table is deliberately left unrenamed by this architecture-only step.
5. **Still open (not a spec gap).** `02_ERD.md`'s database rule #2 ("every changing recommendation object has a version or immutable history record") is still at odds with the *current* `Profile`/`ClientProfile` tables, which are mutated in place with no history — this is about current code, not the target spec, so nothing in this review changes it. Part 1 froze this exact behavior as the regression baseline, correctly, per "evolution not rewrite."
6. **RESOLVED.** No language taxonomy entity existed anywhere in `02_ERD.md`, even though ICAN 1.1 already tracks language + proficiency + work-eligibility as first-class repeatable data (`ClientLanguage`). `LANGUAGE`/`USER_LANGUAGE` now exist.
7. **RESOLVED.** `09_MIGRATION_AND_TEAM_OWNERSHIP.md` Step 2 said "keep current Telegram IDs for compatibility" via an "AuthIdentity" structure that `02_ERD.md` never actually defined. `AUTH_IDENTITY` now has a full field-level definition, confirmed by the Founder Architecture Review rather than inferred.

---

## Migration strategy summary

- **Evolution, not rewrite** (per `09_MIGRATION_AND_TEAM_OWNERSHIP.md`): every migration above is additive/adapter-based. Nothing gets deleted until the new flow is verified and reads have switched over.
- **Sequencing is dependency-constrained, not arbitrary:** canonical User/AuthIdentity (#1) has to land first since nearly everything else FKs to a user — and its target shape is now fully specified, removing one prior source of implementation ambiguity. Consent/InterviewSession/InterviewMessage comes next (also addresses the in-memory-FSM weakness — see debt register Item 15; not a proven fix for the still-unresolved cascade bug itself, Item 4). AI Gateway wrapping (Part 4 of Sprint 0) already landed and doesn't require schema changes. Evidence/ProfileClaim/Goal/Constraint/Experience is blocked on Taxonomy v1's actual content, not on architecture anymore. Career/Scenario/Roadmap is greenfield (no legacy data to migrate, but also no urgency ahead of R0/R1 per the release plan). Guide OS evolution of the CRM (the `manager_id` portion of the `Client` split) now has a fully specified `CLIENT_ASSIGNMENT` target — implementation is the only remaining blocker. Billing/Referral is correctly out of scope until R2.
- **The two Founder/Product decisions from Sprint 0 (recorded in `11_TECHNICAL_DEBT_REGISTER.md`) have now been further hardened into concrete ERD specifications by the Founder Architecture Review** (`docs/engineering/13_FOUNDER_ARCHITECTURE_REVIEW.md`):
  1. **Taxonomies are versioned, starting at Taxonomy v1** — now a specified architecture (`TAXONOMY`/`TAXONOMY_VERSION`/`TAXONOMY_TERM`, `PROFILE_CLAIM.taxonomy_version_id`). What's still open is designing Taxonomy v1's actual dimensions/content (debt register Item 11).
  2. **Manager and Guide are separate concepts** — now a specified architecture (`CLIENT_ASSIGNMENT`, distinct from `CLIENT_RELATIONSHIP`). What's still open is implementing it as an actual migration (debt register Item 12).
- Several other spec gaps this document previously flagged as blockers are now closed the same way: `AuthIdentity` (#1), `AuditLog` (#5, #15), raw transcript (#3), language taxonomy (#8/9/10), and `GOAL`/`CONSTRAINT`/`EXPERIENCE` field-level definitions (#7) all now have concrete ERD shapes. **None of this has been implemented as schema or migrations** — every dependency in this document that previously read "needs to be added to the ERD" should now be read as "needs to be implemented," a different and generally smaller kind of open work.
- Still genuinely open, not touched by the Founder Architecture Review: Document/File entity (Part D #2), `GUIDE_SESSION`/`GUIDE_NOTE` field-level depth for `Call`/`CareerConsultation` (#13, #11), and Taxonomy v1's actual content (Items 11 above).
