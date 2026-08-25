# Founder Architecture Review — Product System v3.1

Documentation/architecture only. No production code, database, or Alembic
migration is included in this change. Nothing described here has been
implemented — this hardens the *target* architecture ahead of Issue #1,
it does not build it.

## Purpose

Sprint 0 (Issue #12) produced a regression baseline, a migration map, a
technical debt register, an AI Gateway, and a golden-dataset structure —
and along the way surfaced a cluster of specification gaps in the target
architecture itself: entities named in prose (`01_SYSTEM_ARCHITECTURE.md`)
that were never actually defined in the ERD (`02_ERD.md`), two Founder/
Product decisions whose *direction* was accepted but whose *schema* was
explicitly deferred, and a naming collision waiting to cause real damage if
nobody caught it before implementation. This review closes those gaps
before Issue #1 ("EPIC R0 — Assessment state machine + adaptive interview")
begins, per Mykola's instruction, working from a fresh branch off the
latest `product-system-v3.1` (which already includes all of Sprint 0,
merged via PR #13).

Read before making any change here: `docs/architecture/01_SYSTEM_ARCHITECTURE.md`,
`02_ERD.md`, `03_API_AND_EVENTS.md`, `04_AI_SYSTEM.md`,
`docs/engineering/10_CURRENT_TO_TARGET_MIGRATION_MAP.md`,
`11_TECHNICAL_DEBT_REGISTER.md`, `12_SPRINT_0_EXIT_REPORT.md`, and GitHub
Issue #1.

Constraints honored throughout: modular monolith preserved (no
microservices split proposed anywhere below); no new product features; no
change to existing ICAN 1.1 behavior; no schema or migration implemented.

---

## Decisions incorporated

### 1. Canonical User / AuthIdentity

`USER` represents a human, independent of channel. `AUTH_IDENTITY` is now a
first-class ERD entity:

```
AUTH_IDENTITY {
  uuid id PK
  uuid user_id FK
  string provider
  string provider_subject
  string provider_username   -- nullable
  datetime verified_at        -- nullable
  datetime last_seen_at       -- nullable
  datetime revoked_at         -- nullable
  datetime created_at
}
UNIQUE(provider, provider_subject)
```

Providers: `telegram`, `email`, `phone`, `google`, `apple`, .... Never store
provider secrets/tokens in `AUTH_IDENTITY`. A Telegram id is an
`AUTH_IDENTITY` identifier, not the canonical `USER` identity.

**Resolves:** debt register Item 5 (was: "AuthIdentity missing field-level
specification"), and Part D contradiction #7 in the Migration Map (was:
"`AuthIdentity`'s shape is inferred, not sourced"). **Files:**
`02_ERD.md`, `01_SYSTEM_ARCHITECTURE.md` (§3 Identity), `03_API_AND_EVENTS.md`
(Identity section note), `10_CURRENT_TO_TARGET_MIGRATION_MAP.md` (#1),
`11_TECHNICAL_DEBT_REGISTER.md` (Item 5).

### 2. Consent

`CONSENT` hardened to be versioned, purpose-specific, auditable,
withdrawable, and traceable to the actor/source that granted it — without
encoding country-specific legal rules:

```
CONSENT {
  uuid id PK
  uuid user_id FK
  uuid granted_by_user_id FK   -- usually = user_id; may differ (guardian)
  string purpose
  string policy_version
  string source
  datetime granted_at
  datetime withdrawn_at        -- nullable
}
```

`granted_by_user_id` is the specific mechanism that makes minor/guardian
consent possible later *without redesigning `USER`* — a guardian's
`user_id` grants on behalf of the minor's `user_id`, no schema change
needed when that becomes real. Every grant/withdrawal is additionally
expected to produce an `AUDIT_LOG` row. No legal advice or
country-specific rules are encoded — explicitly out of scope, per
instruction.

**Relates to:** debt register Item 13 ("no consent/privacy tracking
exists") — the *architecture* gap this decision could have left open is
now closed; the *implementation* gap (Item 13's actual finding) is
unchanged and still real. **Files:** `02_ERD.md`, `03_API_AND_EVENTS.md`
(Identity section note), `11_TECHNICAL_DEBT_REGISTER.md` (Item 13 note).

### 3. Versioned taxonomy

A generic, versioned taxonomy architecture, not one frozen taxonomy:

```
TAXONOMY { uuid id PK, string key, string name, string description }
TAXONOMY_VERSION { uuid id PK, uuid taxonomy_id FK, int version, string status, datetime published_at, datetime created_at }
TAXONOMY_TERM { uuid id PK, uuid taxonomy_version_id FK, uuid parent_term_id FK, string term_key, string label_uk, string label_en, json metadata }
```

Supports (at minimum, via one `TAXONOMY` row each): potential dimensions,
strengths/talents, interests, values, motivations, traits, work
preferences, constraints, skills, career taxonomy, evidence types, profile
claim types. `PROFILE_CLAIM.taxonomy_version_id` was added so generated
claims stay traceable to the exact version that produced them, even after
a newer version is published. **Taxonomy v1's actual content is explicitly
not defined here** — that is Methodology's work, not this review's.

**Resolves (partially):** debt register Item 11 — architecture specified,
content still open; Decision 2 from Sprint 0 Part 3 is now backed by a
concrete schema instead of just a stated direction. **Files:** `02_ERD.md`,
`01_SYSTEM_ARCHITECTURE.md` (new Taxonomy bounded context),
`10_CURRENT_TO_TARGET_MIGRATION_MAP.md` (#2, #7, #9, Part C #3),
`11_TECHNICAL_DEBT_REGISTER.md` (Item 11).

### 4. Client Assignment

`CLIENT_ASSIGNMENT` added, separate from `CLIENT_RELATIONSHIP`:

- `CLIENT_RELATIONSHIP`: `USER`/Client ↔ `GUIDE_PROFILE` only.
- `CLIENT_ASSIGNMENT`: operational ownership/coordination.

```
CLIENT_ASSIGNMENT {
  uuid id PK
  uuid client_user_id FK
  uuid assignee_user_id FK
  uuid tenant_id FK
  string assignment_type    -- MANAGER | COORDINATOR (extensible)
  string status
  datetime valid_from
  datetime valid_to          -- nullable
  uuid assigned_by_user_id FK
  datetime created_at
}
```

**Resolves:** debt register Item 12 (was: "`CLIENT_ASSIGNMENT` model not
yet specified"), and Part D contradiction #3 in the Migration Map (was:
"`CLIENT_RELATIONSHIP` ... `manager_id` ... nowhere to go"). Decision 1
from Sprint 0 Part 3 is now backed by a concrete schema. **Files:**
`02_ERD.md`, `01_SYSTEM_ARCHITECTURE.md` (§3 Guide OS),
`10_CURRENT_TO_TARGET_MIGRATION_MAP.md` (#6, Part C #2),
`11_TECHNICAL_DEBT_REGISTER.md` (Item 12).

### 5. Raw interview transcript

`ANSWER` and raw conversational transcript are different concepts.
`INTERVIEW_MESSAGE` added:

```
INTERVIEW_MESSAGE {
  uuid id PK
  uuid session_id FK
  string role
  text content
  int sequence
  datetime created_at
}
```

`ANSWER` may reference a known `question_id`; raw messages remain available
for audit/reprocessing subject to retention/privacy rules — which this
review does not define (Product/Methodology/Consent scope).

**Resolves:** debt register Item 7 (was: "Raw transcript/audit entity
missing"). **Files:** `02_ERD.md`, `01_SYSTEM_ARCHITECTURE.md` (§3
Discovery), `10_CURRENT_TO_TARGET_MIGRATION_MAP.md` (#3, Part C #5),
`11_TECHNICAL_DEBT_REGISTER.md` (Item 7).

### 6. Goal / Constraint / Experience

Field-level ERD definitions added:

```
GOAL { uuid id PK, uuid user_id FK, string goal_type, text description, string priority, uuid taxonomy_version_id FK, datetime created_at }
CONSTRAINT { uuid id PK, uuid user_id FK, string constraint_type, text description, boolean is_hard, string source, datetime created_at, datetime resolved_at }
EXPERIENCE { uuid id PK, uuid user_id FK, string title, string organization, string start_period, string end_period, text description, datetime created_at }
```

`CONSTRAINT.is_hard` is the field that makes `01_SYSTEM_ARCHITECTURE.md`
§8's rule ("hard constraints cannot be overridden by AI recommendations")
concrete and enforceable — it must be checked server-side in the Scenario
Ranker, not left as a prompt instruction.

**Resolves:** debt register Item 9 (was: "`GOAL`/`CONSTRAINT`/`EXPERIENCE`
missing field-level ERD"). **Files:** `02_ERD.md`, `01_SYSTEM_ARCHITECTURE.md`
(§3 Potential), `10_CURRENT_TO_TARGET_MIGRATION_MAP.md` (#7),
`11_TECHNICAL_DEBT_REGISTER.md` (Item 9).

### 7. Languages

`LANGUAGE`/`USER_LANGUAGE` added — normalized, not a generic `Skill`:

```
LANGUAGE { uuid id PK, string code, string name }
USER_LANGUAGE { uuid id PK, uuid user_id FK, uuid language_id FK, string proficiency_level, string evidence_source }
```

`proficiency_level` and `evidence_source` (nullable) mirror what
`ClientLanguage.level`/`can_work_in_it` already capture in ICAN 1.1 today.

**Resolves:** debt register Item 8 (was: "Language taxonomy/entity
missing"), and Part D contradiction #6 in the Migration Map. **Files:**
`02_ERD.md`, `01_SYSTEM_ARCHITECTURE.md` (§3 Potential),
`10_CURRENT_TO_TARGET_MIGRATION_MAP.md` (#2, #8/9/10),
`11_TECHNICAL_DEBT_REGISTER.md` (Item 8).

### 8. Task naming collision

The target execution-domain entity is renamed `ROADMAP_TASK` (was `TASK`).
The existing, in-production CRM `Task` table is **not** renamed by this
architecture-only step — that stays a deliberately separate, deferred
decision.

**Resolves:** debt register Item 10 (was: "`TASK` naming collision"), and
Part D contradiction #4 in the Migration Map. Note this reverses Item 10's
original recommended direction (which suggested renaming the CRM table) —
the Founder decision instead renames the target entity, which is the
lower-risk choice since it touches only not-yet-implemented documentation,
not a live production table. **Files:** `02_ERD.md`,
`01_SYSTEM_ARCHITECTURE.md` (§3 Execution), `03_API_AND_EVENTS.md`
(Roadmap section note), `10_CURRENT_TO_TARGET_MIGRATION_MAP.md` (#14, Part
C #5, Part D #4), `11_TECHNICAL_DEBT_REGISTER.md` (Item 10).

### 9. Audit log

`AUDIT_LOG` added as a Platform entity:

```
AUDIT_LOG {
  uuid id PK
  uuid actor_user_id FK   -- nullable (system events)
  uuid tenant_id FK
  string entity_type
  uuid entity_id
  string action
  json before_snapshot     -- nullable
  json after_snapshot      -- nullable
  datetime occurred_at
}
```

Audit history is append-only by rule (`02_ERD.md` database rule #8) — a
correction is a new row, never an edit to an existing one.

**Resolves:** debt register Items 6 and (for `TimelineEvent`) part of the
same gap, and Part D contradiction #1 in the Migration Map (was: "`AuditLog`
... never defines it"). **Files:** `02_ERD.md`, `01_SYSTEM_ARCHITECTURE.md`
(§3 Platform), `10_CURRENT_TO_TARGET_MIGRATION_MAP.md` (#5, #15, Part D #1),
`11_TECHNICAL_DEBT_REGISTER.md` (Item 6).

### 10. AI Trace

`AI_TRACE` added as the target persistent representation of what
`app/ai_gateway.py` already emits as structured logs:

```
AI_TRACE {
  uuid id PK    -- doubles as the trace_id app/ai_gateway.py already emits
  string task
  string provider
  string model
  string prompt_version
  int latency_ms
  int input_tokens
  int output_tokens
  float estimated_cost_usd   -- nullable
  string status
  string error_type          -- nullable
  datetime created_at
}
```

**Not persisted in production yet** — this is a target shape only.
`app/ai_gateway.py` continues structured-logging until a persistence
decision and migration are made. No code change was made to
`app/ai_gateway.py` by this review.

**New debt register Item 16** (this gap had no dedicated item before —
`AITrace` was only ever named in `01_SYSTEM_ARCHITECTURE.md`'s prose list,
never tracked). **Files:** `02_ERD.md`, `04_AI_SYSTEM.md` (AI Gateway
section note), `11_TECHNICAL_DEBT_REGISTER.md` (new Item 16).

---

## Remaining unresolved architecture decisions

Not addressed by this review — either genuinely out of scope by
instruction, or real gaps that predate it and weren't asked for:

- **Taxonomy v1's actual content** (dimensions, terms, career taxonomy
  hierarchy, etc.) — explicitly deferred by instruction. Methodology
  Lead's work, against the now-fixed `TAXONOMY_TERM` shape.
- **Document/File domain entity** — the ERD still has no entity for
  `ClientFile`'s eventual target (Migration Map Part D #2). Not raised by
  any of the ten decisions; left open.
- **`GUIDE_SESSION`/`GUIDE_NOTE` field-level depth** — still only
  `starts_at`/`status` on `GUIDE_SESSION`, no fields on `GUIDE_NOTE` at
  all; not enough to represent what `Call` or `CareerConsultation` would
  need to migrate into them (Migration Map #11, #13).
- **`ClientStatus` → `CLIENT_RELATIONSHIP.stage` mapping** — the 7-stage
  CRM pipeline still has no defined mapping onto the target's free-string
  `stage` field.
- **`CLIENT_ASSIGNMENT.tenant_id` in practice** — `TENANT`/`MEMBERSHIP`
  already had ERD field definitions before this review, but no
  multi-tenancy is implemented anywhere in ICAN 1.1 today; `CLIENT_ASSIGNMENT`
  depends on a real `TENANT` row existing, which nothing creates yet.
- **`AI_TRACE` persistence decision** — which store, what retention, at
  what cost — not decided, only the target row shape (debt register Item
  16).
- **PostgreSQL CI coverage** (debt register Item 1) — not an architecture
  question, but the concrete precondition for safely writing *any* of the
  migrations this review's specs now unblock (AuthIdentity, AuditLog,
  ClientAssignment, ...).
- **`ProfileEditLog.edited_by`'s string-not-FK gap** (debt register Item
  14) — unrelated to this review's scope, still blocks a clean `AUDIT_LOG`
  migration for that specific table.

---

## Can Issue #1 start without AuthIdentity ambiguity?

**Yes.** `AUTH_IDENTITY`'s field-level shape is now fully specified (see
Decision 1 above) — the specific ambiguity the Sprint 0 exit report flagged
("`AuthIdentity`'s shape is still unspecified in the ERD") is closed.
Issue #1's acceptance criterion "API and DB are channel-agnostic; Telegram
is only a client" now has a concrete target schema to implement against,
not an inferred one.

This does **not** mean Issue #1 is fully unblocked in every respect —
three things the Sprint 0 exit report flagged remain unchanged by this
review, because none of them are architecture questions:

1. PR #11's architecture review — still Mykola's own pending action.
2. Owner assignment for Issue #1 (and #2–#10) — still a
   Founder/Tech-Lead staffing decision; still zero assignees as of the
   exit report.
3. PostgreSQL CI coverage (debt register Item 1) — still the concrete
   precondition for safely writing the `AuthIdentity` migration (or any
   other new v3.1 migration) against the real database dialect, not just
   validating the Alembic revision chain's structure.

So: the specific blocker named "AuthIdentity ambiguity" is resolved.
Starting Issue #1 cleanly still benefits from #3 landing first, and from
Mykola completing #1 and #2 per the exit report's own recommendation.

---

## Files changed by this review

- `docs/architecture/01_SYSTEM_ARCHITECTURE.md` — bounded contexts updated (Identity, Discovery, new Taxonomy context, Potential, Execution, Guide OS, Platform).
- `docs/architecture/02_ERD.md` — `AUTH_IDENTITY`, hardened `CONSENT`, `TAXONOMY`/`TAXONOMY_VERSION`/`TAXONOMY_TERM`, `PROFILE_CLAIM.taxonomy_version_id`, `GOAL`/`CONSTRAINT`/`EXPERIENCE`, `LANGUAGE`/`USER_LANGUAGE`, `ROADMAP_TASK` (renamed from `TASK`), `CLIENT_ASSIGNMENT`, `AUDIT_LOG`, `AI_TRACE`, two new database rules (8, 9).
- `docs/architecture/03_API_AND_EVENTS.md` — clarifying notes under Identity (AuthIdentity/Consent) and Roadmap (`ROADMAP_TASK` vs CRM `Task`); no endpoint added, removed, or renamed.
- `docs/architecture/04_AI_SYSTEM.md` — note linking the AI Gateway's existing per-call fields to `AI_TRACE`'s target shape.
- `docs/engineering/10_CURRENT_TO_TARGET_MIGRATION_MAP.md` — reconciled every item, Part C ranking, and Part D contradiction that referenced a now-resolved spec gap.
- `docs/engineering/11_TECHNICAL_DEBT_REGISTER.md` — Items 5–10 and 12 marked resolved/partially resolved at spec level, new Item 16 (`AI_TRACE`), new "Recorded Founder Architecture Decisions" section, updated Summary.
- `docs/engineering/13_FOUNDER_ARCHITECTURE_REVIEW.md` — this document (new).

No file under `app/`, `tests/`, `evals/`, or `migrations/` was touched.
