# Canonical ERD v3.1

> Hardened by the Founder Architecture Review (`docs/engineering/13_FOUNDER_ARCHITECTURE_REVIEW.md`) after Sprint 0. Entities added or changed there are marked inline. Nothing in this document has been implemented as a schema/migration yet.

```mermaid
erDiagram
  USER ||--o{ MEMBERSHIP : has
  TENANT ||--o{ MEMBERSHIP : contains
  USER ||--o{ AUTH_IDENTITY : authenticates
  USER ||--o{ CONSENT : grants
  USER ||--o{ INTERVIEW_SESSION : starts
  INTERVIEW_SESSION ||--o{ ANSWER : contains
  INTERVIEW_SESSION ||--o{ INTERVIEW_MESSAGE : logs
  ANSWER ||--o{ EVIDENCE : produces
  USER ||--|| POTENTIAL_PROFILE : owns
  POTENTIAL_PROFILE ||--o{ PROFILE_CLAIM : contains
  PROFILE_CLAIM }o--o{ EVIDENCE : grounded_by
  TAXONOMY ||--o{ TAXONOMY_VERSION : versions
  TAXONOMY_VERSION ||--o{ TAXONOMY_TERM : defines
  TAXONOMY_VERSION ||--o{ PROFILE_CLAIM : grounds
  USER ||--o{ GOAL : has
  USER ||--o{ CONSTRAINT : has
  USER ||--o{ EXPERIENCE : has
  USER ||--o{ USER_SKILL : has
  SKILL ||--o{ USER_SKILL : classifies
  USER ||--o{ USER_LANGUAGE : speaks
  LANGUAGE ||--o{ USER_LANGUAGE : classifies

  CAREER ||--o{ CAREER_SKILL : requires
  SKILL ||--o{ CAREER_SKILL : maps
  CAREER ||--o{ CAREER_EDGE : from
  CAREER ||--o{ CAREER_EDGE : to
  CAREER ||--o{ MARKET_SIGNAL : has

  USER ||--o{ SCENARIO : receives
  POTENTIAL_PROFILE ||--o{ SCENARIO : generates
  CAREER ||--o{ SCENARIO : anchors
  SCENARIO ||--o{ SCENARIO_SCORE : scored_by
  USER ||--o{ DIRECTION_DECISION : makes
  DIRECTION_DECISION }o--|| SCENARIO : chooses

  USER ||--o{ ROADMAP : owns
  ROADMAP ||--o{ ROADMAP_VERSION : versions
  ROADMAP_VERSION ||--o{ MILESTONE : contains
  MILESTONE ||--o{ ROADMAP_TASK : contains
  ROADMAP_TASK ||--o{ TASK_EVIDENCE : proves

  OPPORTUNITY ||--o{ OPPORTUNITY_SKILL : needs
  SKILL ||--o{ OPPORTUNITY_SKILL : maps
  USER ||--o{ OPPORTUNITY_MATCH : receives
  OPPORTUNITY ||--o{ OPPORTUNITY_MATCH : ranked
  OPPORTUNITY_MATCH ||--o| APPLICATION : may_create

  USER ||--o{ CLIENT_RELATIONSHIP : client
  GUIDE_PROFILE ||--o{ CLIENT_RELATIONSHIP : guide
  CLIENT_RELATIONSHIP ||--o{ GUIDE_SESSION : has
  GUIDE_SESSION ||--o{ GUIDE_NOTE : has

  USER ||--o{ CLIENT_ASSIGNMENT : assigned_as_client
  USER ||--o{ CLIENT_ASSIGNMENT : assigned_as_assignee
  TENANT ||--o{ CLIENT_ASSIGNMENT : scopes

  USER ||--o{ OUTCOME_EVENT : produces
  ROADMAP ||--o{ OUTCOME_EVENT : linked
  OPPORTUNITY ||--o{ OUTCOME_EVENT : linked

  GUIDE_PROFILE ||--o{ REFERRAL : owns
  REFERRAL ||--o{ ATTRIBUTION : creates
  PAYMENT ||--o{ ATTRIBUTION : attributed
  PAYMENT ||--o{ COMMISSION : generates
  GUIDE_PROFILE ||--o{ COMMISSION : earns

  USER |o--o{ AUDIT_LOG : acts_as_actor

  USER {
    uuid id PK
    string email
    string phone
    string locale
    string timezone
    datetime created_at
    datetime deleted_at
  }
  AUTH_IDENTITY {
    uuid id PK
    uuid user_id FK
    string provider
    string provider_subject
    string provider_username
    datetime verified_at
    datetime last_seen_at
    datetime revoked_at
    datetime created_at
  }
  TENANT {
    uuid id PK
    string type
    string name
    string status
  }
  MEMBERSHIP {
    uuid id PK
    uuid user_id FK
    uuid tenant_id FK
    string role
  }
  CONSENT {
    uuid id PK
    uuid user_id FK
    uuid granted_by_user_id FK
    string grantor_role
    string purpose
    string policy_version
    string source
    datetime granted_at
    datetime withdrawn_at
  }
  INTERVIEW_SESSION {
    uuid id PK
    uuid user_id FK
    string status
    string assessment_version
    json completeness
  }
  ANSWER {
    uuid id PK
    uuid session_id FK
    string question_id
    text answer_text
  }
  INTERVIEW_MESSAGE {
    uuid id PK
    uuid session_id FK
    string role
    text content
    int sequence
    datetime created_at
  }
  EVIDENCE {
    uuid id PK
    uuid user_id FK
    string source_type
    uuid source_ref
    string claim_key
    float weight
    float confidence
  }
  POTENTIAL_PROFILE {
    uuid id PK
    uuid user_id FK
    int version
    string model_version
    datetime generated_at
  }
  PROFILE_CLAIM {
    uuid id PK
    uuid profile_id FK
    uuid taxonomy_version_id FK
    string dimension
    string label
    float score
    float confidence
  }
  TAXONOMY {
    uuid id PK
    string key
    string name
    string description
  }
  TAXONOMY_VERSION {
    uuid id PK
    uuid taxonomy_id FK
    int version
    string status
    datetime published_at
    datetime created_at
  }
  TAXONOMY_TERM {
    uuid id PK
    uuid taxonomy_version_id FK
    uuid parent_term_id FK
    string term_key
    string label_uk
    string label_en
    json metadata
  }
  GOAL {
    uuid id PK
    uuid user_id FK
    string goal_type
    text description
    string priority
    uuid taxonomy_version_id FK
    datetime created_at
  }
  CONSTRAINT {
    uuid id PK
    uuid user_id FK
    string constraint_type
    text description
    boolean is_hard
    string source
    datetime created_at
    datetime resolved_at
  }
  EXPERIENCE {
    uuid id PK
    uuid user_id FK
    string title
    string organization
    string start_period
    string end_period
    text description
    datetime created_at
  }
  LANGUAGE {
    uuid id PK
    string code
    string name
  }
  USER_LANGUAGE {
    uuid id PK
    uuid user_id FK
    uuid language_id FK
    string proficiency_level
    string evidence_source
  }
  CAREER {
    uuid id PK
    string taxonomy_ref
    string title_uk
    string title_en
    string status
  }
  SCENARIO {
    uuid id PK
    uuid user_id FK
    uuid career_id FK
    uuid profile_id FK
    string trace_id
    string scenario_type
    float fit_score
    float confidence
  }
  DIRECTION_DECISION {
    uuid id PK
    uuid user_id FK
    uuid scenario_id FK
    text rationale
    datetime selected_at
  }
  ROADMAP {
    uuid id PK
    uuid user_id FK
    uuid direction_decision_id FK
    string status
  }
  ROADMAP_VERSION {
    uuid id PK
    uuid roadmap_id FK
    int version
    string reason
  }
  ROADMAP_TASK {
    uuid id PK
    uuid milestone_id FK
    string type
    string status
    datetime due_at
  }
  OPPORTUNITY {
    uuid id PK
    string type
    string title
    string source_name
    string source_url
    datetime verified_at
    string status
  }
  OPPORTUNITY_MATCH {
    uuid id PK
    uuid user_id FK
    uuid opportunity_id FK
    float fit_score
    float confidence
    string status
  }
  GUIDE_PROFILE {
    uuid id PK
    uuid user_id FK
    string level
    string certification_status
  }
  CLIENT_RELATIONSHIP {
    uuid id PK
    uuid client_user_id FK
    uuid guide_id FK
    string stage
    string status
  }
  CLIENT_ASSIGNMENT {
    uuid id PK
    uuid client_user_id FK
    uuid assignee_user_id FK
    uuid tenant_id FK
    string assignment_type
    string status
    datetime valid_from
    datetime valid_to
    uuid assigned_by_user_id FK
    datetime created_at
  }
  GUIDE_SESSION {
    uuid id PK
    uuid relationship_id FK
    datetime starts_at
    string status
  }
  OUTCOME_EVENT {
    uuid id PK
    uuid user_id FK
    string type
    json value
    datetime occurred_at
  }
  PAYMENT {
    uuid id PK
    uuid user_id FK
    int amount_minor
    string currency
    string status
  }
  COMMISSION {
    uuid id PK
    uuid payment_id FK
    uuid guide_id FK
    int amount_minor
    string status
  }
  AUDIT_LOG {
    uuid id PK
    uuid actor_user_id FK
    uuid tenant_id FK
    string entity_type
    uuid entity_id
    string action
    json before_snapshot
    json after_snapshot
    datetime occurred_at
  }
```

`AI_TRACE` is defined below (not in the diagram above) because it isn't
owned by a single FK relationship — the AI Gateway is called from many
different domains (screening today; Discovery, Profile, Scenario, Roadmap,
Guide OS later), so forcing one relationship line would misrepresent it.

```
AI_TRACE {
  uuid id PK
  string trace_id
  string task
  string provider
  string model
  string prompt_version
  int latency_ms
  int input_tokens
  int output_tokens
  float estimated_cost_usd
  string status
  string error_type
  datetime created_at
}
UNIQUE(trace_id)
```

## Entity notes (Founder Architecture Review additions)

- **`AUTH_IDENTITY`** — `provider_username`, `verified_at`, `last_seen_at`,
  `revoked_at` are nullable. `UNIQUE(provider, provider_subject)`. Never
  store provider secrets or tokens here — this table identifies an
  authentication channel, not credentials. A Telegram id (or any other
  provider's id) is an `AUTH_IDENTITY` identifier, never the canonical
  `USER` identity.
- **`CONSENT`** (hardened) — `granted_by_user_id` normally equals `user_id`
  (self-consent) but may differ, which is what lets a guardian grant consent
  on behalf of a minor `user_id` without redesigning `USER` itself.
  `grantor_role` records the *capacity* consent was granted in — `SELF`,
  `GUARDIAN`, `AUTHORIZED_REPRESENTATIVE` (extensible) — a neutral field,
  not a legal determination; it says what the app was told, not what any
  jurisdiction requires. `policy_version` makes consent versioned; `purpose`
  makes it purpose-specific; `source` (e.g. `telegram_bot` / `web` /
  `admin_import`) plus `granted_by_user_id`/`grantor_role` make it
  traceable; `withdrawn_at` (nullable) makes it withdrawable. Every
  grant/withdrawal is additionally expected to produce an `AUDIT_LOG` row
  for auditability. No country-specific legal rules are encoded here —
  that is explicitly out of scope for this review.
- **`TAXONOMY` / `TAXONOMY_VERSION` / `TAXONOMY_TERM`** — one `TAXONOMY` row
  per category (potential dimensions, strengths/talents, interests, values,
  motivations, traits, work preferences, constraints, skills, career
  taxonomy, evidence types, profile claim types, ...). `TAXONOMY_VERSION`
  carries `status` (e.g. draft/active/deprecated); `TAXONOMY_TERM.parent_term_id`
  (nullable) supports hierarchical taxonomies such as career taxonomy.
  `PROFILE_CLAIM.taxonomy_version_id` is the concrete mechanism that keeps a
  generated claim traceable to the exact taxonomy version that produced it,
  even after a newer version is published. **Taxonomy v1's actual content is
  not defined by this document** — only the versioning architecture.
- **`GOAL` / `CONSTRAINT` / `EXPERIENCE`** — previously named only as
  bounded-context labels, now field-level. `CONSTRAINT.is_hard` is the
  field that must gate scenario/recommendation generation: a hard
  constraint (`is_hard = true`) cannot be overridden by AI recommendations
  (`01_SYSTEM_ARCHITECTURE.md` §8) — this has to be enforced server-side in
  the Scenario Ranker, not left as a prompt instruction alone.
- **`LANGUAGE` / `USER_LANGUAGE`** — a normalized entity pair, not a
  `SKILL` row. `proficiency_level` (e.g. A1–C2/native/unknown) and
  `evidence_source` (nullable; self_reported/cv_extracted/verified) mirror
  the level of detail ICAN 1.1's `ClientLanguage` already captures today.
- **`ROADMAP_TASK`** (renamed from `TASK`) — renamed specifically to avoid
  collision with the existing, unrelated CRM `Task` (staff operational
  reminders — see `11_TECHNICAL_DEBT_REGISTER.md` Item 10). The CRM table
  itself is **not** renamed by this document — that stays a separate,
  explicitly deferred implementation step.
- **`CLIENT_ASSIGNMENT`** — distinct from `CLIENT_RELATIONSHIP`, which
  stays `USER`/Client ↔ `GUIDE_PROFILE` only. `CLIENT_ASSIGNMENT` is
  operational ownership/coordination (`assignment_type`: `MANAGER`,
  `COORDINATOR`, extensible later). `valid_to` (nullable) plus multiple
  historical rows per `client_user_id` let assignment history be
  reconstructed — something today's single mutable `Client.manager_id`
  cannot do.
- **`AUDIT_LOG`** — `actor_user_id` is nullable for system-originated
  events; `before_snapshot`/`after_snapshot` are nullable, populated where
  a before/after diff is meaningful. Rows are append-only: a correction is
  a new row, never an edit to an existing one.
- **`AI_TRACE`** — `id` is the database primary key; `trace_id` (`UNIQUE`)
  is the separate *runtime* identifier already emitted today by
  `app/ai_gateway.py`'s structured logs (`str(uuid.uuid4())` per call, see
  Sprint 0 Part 4). The two are related but not the same concept: `id`
  identifies the row once persisted, `trace_id` identifies the call itself
  and is what other artifacts reference (e.g. `SCENARIO.trace_id`, below) —
  a generated artifact should never need to know whether `AI_TRACE` has
  been persisted yet to record which call produced it. `estimated_cost_usd`
  and `error_type` are nullable. **This document defines the target shape
  only — `AI_TRACE` is not persisted in production yet.** `app/ai_gateway.py`
  continues structured-logging this data until a persistence decision and
  migration are made.
- **Generated-artifact reproducibility (`SCENARIO` → `DIRECTION_DECISION` →
  `ROADMAP`)** — `PROFILE_CLAIM.taxonomy_version_id` alone isn't enough for
  artifacts further downstream, since a `SCENARIO` can depend on multiple
  claims grounded in multiple taxonomy categories/versions at once. Rather
  than stack a `taxonomy_version_id` on every generated artifact,
  `SCENARIO.profile_id` (FK → `POTENTIAL_PROFILE.id`) records the exact
  profile *row* — and therefore version — a scenario was generated from;
  every claim and taxonomy version behind it is then reachable by walking
  `POTENTIAL_PROFILE` → `PROFILE_CLAIM` (`profile_id`) →
  `PROFILE_CLAIM.taxonomy_version_id` / `EVIDENCE` (`grounded_by`), instead
  of duplicating that chain onto `SCENARIO` itself. `SCENARIO.trace_id`
  (references `AI_TRACE.trace_id`, not persisted as a DB-level FK since
  `AI_TRACE` itself isn't persisted yet) records which model/prompt call
  produced it, per database rule #7. `DIRECTION_DECISION.scenario_id` and
  `ROADMAP.direction_decision_id` already existed and already chain
  backward through `SCENARIO` to the same profile/claim/taxonomy/trace
  history — no new field was needed on either of them for this. Together
  this is enough to reconstruct, for any published recommendation: which
  profile version, which claims/evidence, which taxonomy versions, and
  which model/prompt produced it — without a separate provenance subsystem.

## Database rules

1. Critical business data must be relational; JSON is for flexible snapshots, not the only source of truth.
2. Every changing recommendation object has a `version` or immutable history record.
3. Deletes of user data follow privacy workflow; audit/security records follow separate retention rules.
4. Money is stored in minor units + currency.
5. Timestamps are UTC; user timezone is presentation metadata.
6. Foreign keys and tenant ownership are enforced server-side.
7. AI trace/model/prompt versions are stored against generated artifacts — via a direct `trace_id` reference (e.g. `SCENARIO.trace_id` → `AI_TRACE.trace_id`) and via the input-state chain (`PROFILE_CLAIM.taxonomy_version_id`, `SCENARIO.profile_id`), not by duplicating taxonomy/model fields onto every downstream artifact.
8. `AUDIT_LOG` rows are append-only; corrections are new rows, never edits to an existing one.
9. `CONSTRAINT.is_hard = true` rows are enforced server-side wherever scenarios/recommendations are generated — never delegated to an LLM's discretion.
