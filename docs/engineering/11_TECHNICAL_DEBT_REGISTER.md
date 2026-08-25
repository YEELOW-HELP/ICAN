# Technical Debt Register

Sprint 0, Part 3 (Issue #12). Documentation only — no production code, schema,
or migration is included in this change. Nothing in this document is
implemented; it is a tracked inventory for sequencing future work.

> Updated by the Founder Architecture Review
> (`docs/engineering/13_FOUNDER_ARCHITECTURE_REVIEW.md`). Items 5–10 and 12
> were specification gaps — each now has a field-level ERD shape in
> `docs/architecture/02_ERD.md` and is marked **RESOLVED AT SPEC LEVEL**
> below. Resolved-at-spec-level means the target shape is no longer
> ambiguous; it does **not** mean anything is implemented — every one of
> these still needs an actual Alembic migration before it's real. Item 11
> is **PARTIALLY RESOLVED** (architecture specified, content still open).
> A new Item 16 tracks `AI_TRACE`, which didn't have its own item before
> this review.

Sources: Part 1 (regression baseline, `tests/`), Part 2
(`docs/engineering/10_CURRENT_TO_TARGET_MIGRATION_MAP.md`), the two
Founder/Product decisions recorded below, and the Founder Architecture
Review's ten decisions (`docs/engineering/13_FOUNDER_ARCHITECTURE_REVIEW.md`).

---

## Recorded Founder/Product decisions (Sprint 0, decided, not yet implemented)

These resolve two open questions raised in Part 2. Recording them here per
instruction — **no schema or code change follows from this document.**

### Decision 1 — Manager and Guide are separate concepts

- `CLIENT_RELATIONSHIP` (target ERD) represents the relationship between a
  User/Client and a **Guide** only. `manager_id` does **not** move into it.
- Operational ownership/coordination (manager, coordinator, and potentially
  other operational roles later) will be modeled separately in the future,
  conceptually as **`CLIENT_ASSIGNMENT`** — final naming/schema to be
  proposed later, supporting at least assignment types `MANAGER` and
  `COORDINATOR`.
- Until that replacement model is designed and safely migrated, the existing
  `Client.manager_id` semantics (`app/db/models_crm.py`) are preserved
  unchanged.
- Tracked as Item 12 below. **Schema now specified** by the Founder
  Architecture Review — see Item 12's updated status.

### Decision 2 — Taxonomies are versioned

- No single permanent methodology taxonomy will be frozen. The system must
  support **versioned taxonomies**, starting with Taxonomy v1.
- At minimum, future taxonomy work must cover: Potential dimensions,
  Strengths/talents, Interests, Values, Motivations, Traits, Work
  preferences, Constraints, Skills, Career taxonomy, Evidence types,
  ProfileClaim types.
- Historical profiles/results must remain traceable to the taxonomy version
  that produced them.
- Full taxonomy design is explicitly out of scope here (and was out of
  scope for Part 3 by instruction — and remains out of scope for the
  Founder Architecture Review, which specified the *versioning
  architecture* but not Taxonomy v1's *content*, by the same instruction).
- Tracked as Item 11 below.

---

## Recorded Founder Architecture Decisions (post-Sprint-0, decided and specified, not yet implemented)

Full detail, rationale, and exact field lists:
`docs/engineering/13_FOUNDER_ARCHITECTURE_REVIEW.md`. Summary, each
cross-referenced to the debt item it resolves:

1. **Canonical User / AuthIdentity** — `AUTH_IDENTITY` added to the ERD with a full field list and `UNIQUE(provider, provider_subject)`. Resolves Item 5.
2. **Consent hardened** — `CONSENT` now versioned, purpose-specific, auditable, withdrawable, and guardian/minor-capable via `granted_by_user_id`, without redesigning `USER`. Relates to Item 13 (implementation still not done).
3. **Versioned taxonomy architecture** — `TAXONOMY` → `TAXONOMY_VERSION` → `TAXONOMY_TERM` added to the ERD; `PROFILE_CLAIM.taxonomy_version_id` added for traceability. Taxonomy v1's content is explicitly not defined. Partially resolves Item 11.
4. **`CLIENT_ASSIGNMENT`** — full field list added, separate from `CLIENT_RELATIONSHIP`. Resolves Item 12.
5. **`INTERVIEW_MESSAGE`** — raw transcript entity added, distinct from `ANSWER`. Resolves Item 7.
6. **`GOAL`/`CONSTRAINT`/`EXPERIENCE` field-level ERD** — added, including `CONSTRAINT.is_hard`. Resolves Item 9.
7. **`LANGUAGE`/`USER_LANGUAGE`** — normalized entity pair added, distinct from `SKILL`. Resolves Item 8.
8. **`TASK` naming collision** — target entity renamed `ROADMAP_TASK`; the existing CRM `Task` table is explicitly **not** renamed by this architecture-only step. Resolves Item 10 (direction reversed from the item's original recommendation — see Item 10 below).
9. **`AUDIT_LOG`** — added as a Platform entity, append-only by rule. Resolves Item 6.
10. **`AI_TRACE`** — added as the target persistent shape of what `app/ai_gateway.py` already structured-logs. Not persisted in production yet. Tracked as new Item 16.

---

## How to read this register

| Field | Scale |
|---|---|
| **Severity** | Low / Medium / High — impact if the risk materializes |
| **Probability** | Low / Medium / High / Certain — likelihood or confirmation status |
| **Blast radius** | Narrow (one flow/table) / Moderate (one bounded context) / Wide (cross-cutting) |
| **Blocks R0/R1** | Whether this gates the current release scope per `docs/product/05_RELEASE_PLAN.md`, or can wait |

---

## A. Test coverage gaps (from Part 1)

### 1. PostgreSQL Alembic execution coverage in CI

- **Category:** Test Coverage / CI Infrastructure
- **Severity:** High
- **Probability:** Medium — already demonstrated: probing `alembic upgrade head` against SQLite in Part 1 failed with `sqlite3.OperationalError: near "ALTER"` on the CRM 1.0 migration's `ALTER COLUMN ... TYPE` statement. Every future migration carries the same untested risk until it runs against real Postgres somewhere.
- **Blast radius:** Wide — every future Alembic migration, and by extension every deploy.
- **Current evidence:** `tests/test_migrations.py` validates only the revision-graph structure (single head, no gaps/duplicates) — its own docstring documents that it deliberately does not execute the chain, and explains why (Postgres-only DDL, no Postgres available in this environment).
- **Recommended mitigation:** add a Postgres service container to CI (e.g. GitHub Actions `services: postgres`), then a test running `alembic upgrade head` / `alembic downgrade base` against it.
- **When must be resolved:** before the first v3.1 schema migration (User/AuthIdentity, Consent, InterviewSession) is written — those are exactly the kind most likely to contain non-trivial DDL. The Founder Architecture Review specified several of these entities' shapes but did not resolve this CI gap — it remains a precondition for implementing any of them safely.
- **Blocks R0/R1:** Does not block current R0 prototype work (no new migrations yet); blocks safely writing any Alembic migration for v3.1 entities.
- **Owner role:** Backend / DevOps (per `09_MIGRATION_AND_TEAM_OWNERSHIP.md`'s CI/CD row: Tech Lead accountable, DevOps/Backend responsible).

### 2. CV upload E2E coverage

- **Category:** Test Coverage
- **Severity:** Medium
- **Probability:** Medium — regressions in the Telegram-file-download ↔ text-extraction wiring wouldn't be caught by unit tests of the parser alone.
- **Blast radius:** Narrow/Moderate — isolated to the CV intake path; chat and anketa paths are unaffected.
- **Current evidence:** `tests/bot_harness.py`'s `FakeSession.make_request` raises `NotImplementedError` for `GetFile`; no test drives `on_cv_document`/`_handle_cv_upload`. `tests/test_documents.py` covers only `extract_text` in isolation.
- **Recommended mitigation:** extend `FakeSession` to fake `GetFile` and `stream_content` with real PDF/DOCX bytes; add e2e tests mirroring `tests/test_bot_e2e.py`'s chat-path coverage.
- **When must be resolved:** before the screening-turn logic shared with chat (`_run_screening_turn`) is touched by the v3.1 migration.
- **Blocks R0/R1:** No.
- **Owner role:** QA / Backend.

### 3. Anketa flow E2E coverage

- **Category:** Test Coverage
- **Severity:** Low/Medium
- **Probability:** Medium
- **Blast radius:** Narrow — isolated to the button-questionnaire intake path.
- **Current evidence:** no `BotHarness`-based test drives the `on_method_anketa` → `on_anketa_answer`/`on_anketa_text` sequence; only prior service-level tests of `anketa.build_profile` exist (per Part 1's coverage audit).
- **Recommended mitigation:** add e2e tests via `BotHarness.click()`/`send_text()` through the full anketa state sequence, reusing the Part 1 harness.
- **When must be resolved:** same trigger as Item 2.
- **Blocks R0/R1:** No.
- **Owner role:** QA / Backend.

### 4. Unresolved Telegram button-cascade bug (production)

This item covers three distinct things that must not be conflated: a
confirmed open defect, a separately confirmed architecture weakness, and a
planned mitigation whose effect on the defect is not yet proven.

**4a. Confirmed problem.** The button-cascade bug exists in production and
its root cause is unresolved.

- **Category:** Production Defect
- **Severity:** High
- **Probability:** Certain — already occurred in production, reproducibly, for at least two accounts, including one with zero prior history (which disproved the original "stale update backlog" theory).
- **Blast radius:** Wide — affects the entire onboarding/anketa flow for any live Telegram user.
- **Current evidence:** live-testing screenshots (pre-Sprint-0) showing cascading bot messages with missing inline keyboards after `/start`. `bot.delete_webhook(drop_pending_updates=True)` (`app/bot/main.py`) was added as a fix attempt but the identical failure reproduced afterward for a brand-new account. Root cause was never confirmed — it remains genuinely unknown, not "known but unfixed."
- **Recommended mitigation:** reproduce and diagnose independently — add structured logging/diagnostics around FSM transitions and Telegram update handling, then reproduce under controlled conditions before assuming any cause. Do not treat Item 15 below as this bug's explanation; they are tracked separately for exactly this reason.
- **When must be resolved:** before Telegram bot traffic resumes in production — as an open defect requiring reproduction and diagnostics, not assumed-fixed by any architecture change.
- **Blocks R0/R1:** Does not block R0/R1 engineering (bot traffic is currently paused); blocks re-enabling live Telegram traffic.
- **Owner role:** Backend / Tech Lead.

**4b. Separate confirmed architecture weakness.** See Item 15 — in-memory
FSM does not survive process restarts and is unsuitable for the target
production architecture. This is confirmed and independent of 4a's root
cause.

**4c. Planned mitigation (effect on 4a unproven).** The target
`InterviewSession`/`Answer`/`InterviewMessage` DB-backed state machine
(Migration Map, Part B; `InterviewMessage` added by the Founder Architecture
Review) should replace the in-memory FSM for durability and observability,
and may eliminate one class of state-related failures. It must **not** be
presented as a proven fix for the button-cascade bug (4a) until the bug has
been reproduced, diagnosed, and verified against the new implementation.
Treat the migration as justified on its own architectural merits (4b), not
as a confirmed cure for 4a.

---

## B. Specification gaps (from Part 2)

### 5. `AuthIdentity` missing field-level specification

**Status: RESOLVED AT SPEC LEVEL** by the Founder Architecture Review — not implemented.

- **Category:** Specification Gap (ERD)
- **Severity:** Medium → Low now that the spec exists; the underlying migration work (still not done) keeps this item open.
- **Probability:** Certain
- **Blast radius:** Wide — blocks the #1 highest-risk migration (User canonicalization) from starting with a concrete target schema.
- **Current evidence:** `docs/architecture/02_ERD.md` now defines `AUTH_IDENTITY` (`id`, `user_id`, `provider`, `provider_subject`, `provider_username`, `verified_at`, `last_seen_at`, `revoked_at`, `created_at`, `UNIQUE(provider, provider_subject)`).
- **Recommended mitigation:** implement as an Alembic migration (additive, per Migration Map #1) once Issue #1 begins — blocked on Item 1 (Postgres CI coverage) first.
- **When must be resolved:** before any canonical User/AuthIdentity migration is written.
- **Blocks R0/R1:** Blocked the User-canonicalization migration from having a concrete schema to build against; that ambiguity is now gone. Implementation itself does not block current R0 scope.
- **Owner role:** Tech Lead → Backend (implementation).

### 6. `AuditLog` missing from ERD

**Status: RESOLVED AT SPEC LEVEL** by the Founder Architecture Review — not implemented.

- **Category:** Specification Gap (ERD)
- **Severity:** Low/Medium → Low now that the spec exists.
- **Probability:** Certain
- **Blast radius:** Moderate — affects the eventual migration path for `ProfileEditLog` and `TimelineEvent`, both of which work fine today.
- **Current evidence:** `docs/architecture/02_ERD.md` now defines `AUDIT_LOG` (`id`, `actor_user_id`, `tenant_id`, `entity_type`, `entity_id`, `action`, `before_snapshot`, `after_snapshot`, `occurred_at`), append-only by database rule #8.
- **Recommended mitigation:** implement once `ProfileEditLog`/`TimelineEvent` are migrated — not urgent, both REUSE/ADAPT cleanly today. Item 14 (`ProfileEditLog.edited_by` not an FK) should be cleaned up first.
- **When must be resolved:** before `ProfileEditLog`/`TimelineEvent` are migrated.
- **Blocks R0/R1:** No.
- **Owner role:** Tech Lead → Backend (implementation).

### 7. Raw transcript/audit entity missing

**Status: RESOLVED AT SPEC LEVEL** by the Founder Architecture Review — not implemented.

- **Category:** Specification Gap (ERD)
- **Severity:** Low
- **Probability:** Certain
- **Blast radius:** Narrow — affects only how `Message`'s free-form transcript is preserved once `INTERVIEW_SESSION` exists.
- **Current evidence:** `docs/architecture/02_ERD.md` now defines `INTERVIEW_MESSAGE` (`id`, `session_id`, `role`, `content`, `sequence`, `created_at`), distinct from `ANSWER` (which assumes a fixed `question_id`).
- **Recommended mitigation:** implement alongside `INTERVIEW_SESSION`. Retention/redaction policy for raw messages is still a Product/Methodology/Consent call, not resolved by adding the entity.
- **When must be resolved:** before the Interview Orchestrator (`04_AI_SYSTEM.md` component #1) is built, or before `InterviewSession` itself if raw logging is wanted from day one.
- **Blocks R0/R1:** No — `Message` keeps working as-is until then.
- **Owner role:** Tech Lead (schema, done) → Backend (implementation); Product/Methodology still owns the retention-policy question.

### 8. Language taxonomy/entity missing

**Status: RESOLVED AT SPEC LEVEL** by the Founder Architecture Review — not implemented.

- **Category:** Specification Gap (ERD)
- **Severity:** Low
- **Probability:** Certain
- **Blast radius:** Narrow — affects only `ClientLanguage`'s eventual migration.
- **Current evidence:** `docs/architecture/02_ERD.md` now defines `LANGUAGE` (`id`, `code`, `name`) and `USER_LANGUAGE` (`id`, `user_id`, `language_id`, `proficiency_level`, `evidence_source`) — a normalized pair, not a `SKILL` row.
- **Recommended mitigation:** implement when `ClientLanguage` is migrated; seed `LANGUAGE` with a standard code/name reference set first.
- **When must be resolved:** before `ClientLanguage` is migrated.
- **Blocks R0/R1:** No.
- **Owner role:** Tech Lead → Backend (implementation).

### 9. `GOAL`/`CONSTRAINT`/`EXPERIENCE` missing field-level ERD

**Status: RESOLVED AT SPEC LEVEL** by the Founder Architecture Review — not implemented.

- **Category:** Specification Gap (ERD)
- **Severity:** Medium → Low now that the spec exists.
- **Probability:** Certain
- **Blast radius:** Wide — blocks migrating the CRM's richest, most human-verified data (`ClientProfile`, `WorkExperience`).
- **Current evidence:** `docs/architecture/02_ERD.md` now defines all three at field level, including `CONSTRAINT.is_hard` — the field that must gate scenario/recommendation generation server-side (`01_SYSTEM_ARCHITECTURE.md` §8, `02_ERD.md` database rule #9).
- **Recommended mitigation:** implement as part of the `ClientProfile`/`WorkExperience` migration (Migration Map #7, #8); enforce `is_hard` in the Scenario Ranker before that component is ever built, not as an afterthought.
- **When must be resolved:** before `ClientProfile`/`WorkExperience` migration starts.
- **Blocks R0/R1:** Blocks that specific future migration; does not block current R0 scope.
- **Owner role:** Tech Lead + Methodology Lead (spec, done) → Backend (implementation).

### 10. `TASK` naming collision

**Status: RESOLVED, direction reversed from original recommendation** by the Founder Architecture Review.

- **Category:** Specification Gap / Naming
- **Severity:** Low — collision risk removed at the source now that the names differ.
- **Probability:** N/A — resolved.
- **Blast radius:** N/A — resolved.
- **Current evidence:** `docs/architecture/02_ERD.md`'s target entity is now `ROADMAP_TASK`, not `TASK`. This item originally recommended renaming the CRM's `Task`/`tasks` table instead — the Founder Architecture Review took the opposite approach: rename the target, leave the existing production CRM table untouched (explicitly, as an architecture-only decision).
- **Recommended mitigation:** none further needed for the collision itself. The CRM table's name (`Task`/`tasks`) remains as-is; this is a deliberate choice, not an oversight.
- **When must be resolved:** resolved.
- **Blocks R0/R1:** No.
- **Owner role:** Tech Lead (resolved).

### 11. Versioned taxonomy architecture not yet specified

**Status: PARTIALLY RESOLVED** by the Founder Architecture Review — architecture specified, content still open.

- **Category:** Specification Gap (Methodology/Architecture)
- **Severity:** High — still High, because R1's Evidence Graph deliverable depends on the *content*, not just the architecture.
- **Probability:** Certain
- **Blast radius:** Wide — blocks Migration Map #2/#7 (`Profile`/`ClientProfile` → `PotentialProfile`/`ProfileClaim`/`Goal`/`Constraint`/`Experience`) and all Methodology work on dimensions/strengths/skills/etc.
- **Current evidence:** `docs/architecture/02_ERD.md` now defines `TAXONOMY` → `TAXONOMY_VERSION` → `TAXONOMY_TERM`, and `PROFILE_CLAIM.taxonomy_version_id` gives generated claims a concrete traceability link. **Taxonomy v1's actual dimension/label content is explicitly not defined** — this was out of scope for both Part 3 and the Founder Architecture Review by instruction.
- **Recommended mitigation:** Methodology Lead to design Taxonomy v1's actual content (dimensions, strengths/talents, interests, values, motivations, traits, work preferences, constraints, skills, career taxonomy, evidence types, profile claim types) against the now-fixed `TAXONOMY_TERM` shape.
- **When must be resolved:** before any `PROFILE_CLAIM`/`EVIDENCE` migration or generation work begins.
- **Blocks R0/R1:** Blocks R1 (Evidence Graph + Direction + Roadmap explicitly requires evidence-linked claims per `docs/product/00_MASTER_INDEX.md`'s release table); does not necessarily block a narrowly-scoped R0 (Product to confirm). Notably, **Issue #1 itself does not depend on this** — it's state-machine mechanics, not evidence-linked claims (see `docs/engineering/13_FOUNDER_ARCHITECTURE_REVIEW.md`).
- **Owner role:** Methodology Lead (accountable, content) + Tech Lead (schema, done).

### 12. `CLIENT_ASSIGNMENT` model not yet specified

**Status: RESOLVED AT SPEC LEVEL** by the Founder Architecture Review — not implemented.

- **Category:** Specification Gap (Architecture)
- **Severity:** Medium → Low now that the spec exists.
- **Probability:** Certain
- **Blast radius:** Moderate — blocks Migration Map #6 (`Client` split) from fully resolving the `manager_id` gap; current dual `manager_id`/`consultant_id` ownership keeps working as-is until this lands.
- **Current evidence:** `docs/architecture/02_ERD.md` now defines `CLIENT_ASSIGNMENT` (`id`, `client_user_id`, `assignee_user_id`, `tenant_id`, `assignment_type` [`MANAGER`/`COORDINATOR`, extensible], `status`, `valid_from`, `valid_to`, `assigned_by_user_id`, `created_at`), separate from `CLIENT_RELATIONSHIP`.
- **Recommended mitigation:** implement as part of the `Client` split migration (Migration Map #6), once `TENANT` exists for `CLIENT_ASSIGNMENT.tenant_id`.
- **When must be resolved:** before the `Client` → `USER`/`CLIENT_RELATIONSHIP`/`CLIENT_ASSIGNMENT` split is implemented; until then, `manager_id`/`consultant_id` semantics are preserved unchanged, per Decision 1.
- **Blocks R0/R1:** No — current CRM assignment flow keeps working; only blocks the future `Client` split.
- **Owner role:** Tech Lead (spec, done) → Backend (implementation).

---

## C. Additional debt identified during Part 1/2 work

Not explicitly requested, included for completeness since each is a concrete finding already surfaced during this sprint's own analysis, not new speculative digging.

### 13. No consent/privacy tracking exists

- **Category:** Compliance / Privacy Risk
- **Severity:** High
- **Probability:** Certain — confirmed absence, not speculative.
- **Blast radius:** Wide — affects every user who has completed screening (Telegram) or been entered into the CRM (any channel).
- **Current evidence:** no `Consent`-shaped table in `app/db/models.py` or `app/db/models_crm.py`; no consent-capture endpoint anywhere in `app/api/`. The target `CONSENT` entity is now hardened at spec level (Founder Architecture Review — versioned, purpose-specific, traceable to `granted_by_user_id`/`source`, withdrawable, guardian/minor-capable) but **still has zero implementation**.
- **Recommended mitigation:** Product/Legal to confirm whether current data collection requires retroactive consent capture, and prioritize `CONSENT` implementation ahead of any new user-data collection in v3.1 — not just as a v3.1 nice-to-have. The spec is no longer the blocker; the implementation and the Product/Legal decision are.
- **When must be resolved:** before scaling beyond the current closed test-user set; ideally before R0 if any new real users are onboarded.
- **Blocks R0/R1:** Should block wider R0 rollout beyond already-consented test users, pending a Product/Legal decision — flagged, not decided here.
- **Owner role:** Product (accountable) + Tech Lead (implementation), per `09_MIGRATION_AND_TEAM_OWNERSHIP.md`'s Security/privacy row.

### 14. `ProfileEditLog.edited_by` stored as a free string, not an FK

- **Category:** Data Quality
- **Severity:** Low/Medium
- **Probability:** Certain — confirmed by reading `app/db/models.py`.
- **Blast radius:** Narrow — affects only the admin-edit audit trail.
- **Current evidence:** `ProfileEditLog.edited_by: Mapped[str]` (`String(255)`), not a foreign key to `AdminUser.id` — unlike every other actor reference in the CRM schema (`Task.assignee_id`, `Call.employee_id`, `TimelineEvent.actor_id` are all proper FKs).
- **Recommended mitigation:** add an `edited_by_id` FK alongside (or replacing) the string field; backfill by matching existing string values to `AdminUser.email`/`full_name` where unambiguous, flag unmatched rows for manual review.
- **When must be resolved:** before any `AUDIT_LOG` migration (Item 6) relies on stable actor identity.
- **Blocks R0/R1:** No.
- **Owner role:** Backend.

### 15. In-memory FSM state does not survive process restarts

- **Category:** Architecture / Reliability
- **Severity:** Medium
- **Probability:** Certain — `aiogram.Dispatcher()` uses `MemoryStorage` by default; no persistent storage backend is configured anywhere in `app/bot/main.py`. Any Railway restart/redeploy silently resets every in-progress conversation's FSM state.
- **Blast radius:** Moderate — affects any user mid-conversation at deploy time. This was the original (later disproven) hypothesis for Item 4 — tracked separately here as a distinct, confirmed weakness even though it didn't turn out to fully explain that bug.
- **Current evidence:** no `RedisStorage`/DB-backed storage configured; `bot.delete_webhook(drop_pending_updates=True)` was added specifically to paper over this by discarding queued updates on restart, not to fix the underlying statelessness.
- **Recommended mitigation:** superseded by the planned `InterviewSession`/`Answer`/`InterviewMessage` DB-backed state machine (Migration Map, Part B) — no interim fix recommended given the replacement is already planned and now further specified (`INTERVIEW_MESSAGE`, Founder Architecture Review).
- **When must be resolved:** same as Item 4 — before Telegram bot traffic resumes in production.
- **Blocks R0/R1:** No (bot traffic currently paused).
- **Owner role:** Backend.

### 16. `AI_TRACE` not persisted in production

- **Category:** Specification Gap / Observability (new — Founder Architecture Review)
- **Severity:** Low — the data isn't lost, just not durably queryable; `app/ai_gateway.py` already structured-logs every field on both success and failure (Sprint 0 Parts 4 and 4-follow-up).
- **Probability:** Certain — confirmed absence of a persistence layer.
- **Blast radius:** Narrow today (one AI task, `legacy-screening-v1`); would widen as more AI Gateway callers are added (Evidence Extractor, Scenario Ranker, etc.), since none of them would have durable trace history either.
- **Current evidence:** `docs/architecture/02_ERD.md` now defines `AI_TRACE` (`id` PK, `trace_id` `UNIQUE` — the two deliberately kept as separate concepts, not one field doing both jobs — plus `task`, `provider`, `model`, `prompt_version`, `latency_ms`, `input_tokens`, `output_tokens`, `estimated_cost_usd`, `status`, `error_type`, `created_at`) as the target persistent shape — explicitly not implemented by that review (`AI_TRACE` is not persisted in production yet, by instruction).
- **Recommended mitigation:** implement `AI_TRACE` and switch `app/ai_gateway.py` from structured-logging to writing rows, once a persistence decision (which store, retention policy, cost) is made — not urgent while call volume is low (one legacy task).
- **When must be resolved:** before AI cost/latency monitoring needs to be queryable rather than log-grepped, or before additional AI Gateway callers make log-only tracing impractical.
- **Blocks R0/R1:** No.
- **Owner role:** AI Engineer / Backend.

---

## Summary

**16 items tracked:** 4 test-coverage gaps (Part 1), 8 specification gaps (Part 2 — 6 now resolved at spec level, 1 resolved outright, 1 partially resolved, by the Founder Architecture Review), 3 additional findings from Sprint 0's own analysis, 1 new item from the Founder Architecture Review (`AI_TRACE`).

**Resolved at spec level by the Founder Architecture Review (implementation still open):** Items 5, 6, 7, 8, 9, 12.

**Resolved outright:** Item 10 (naming collision — direction reversed, no further spec work needed).

**Partially resolved:** Item 11 (architecture specified; Taxonomy v1 content still open — this is the one that actually blocks R1).

**Blocks R0 rollout today:** Item 13 (consent) — pending a Product/Legal decision, not an engineering one; the spec is no longer the blocker.

**Blocks R1 specifically:** Item 11 (Taxonomy v1 content) — R1's Evidence Graph deliverable depends on it.

**Must resolve before Telegram traffic resumes (not R0/R1-gated, since bot traffic is currently paused):** Items 4 and 15.

**Gate specific future migrations but don't block current sprint work:** Items 1, 5, 6, 7, 8, 9, 12, 14, 16.

**Pure test-coverage gaps, lowest urgency:** Items 2, 3.

Recommended immediate attention, in order (recommendation only, not a decision):
1. **Item 13** — real compliance exposure today, independent of any migration timeline; spec is now ready, implementation and the Product/Legal call are what's left.
2. **Item 11** — blocks R1; architecture is now specified, Taxonomy v1 content needs a Methodology owner.
3. **Item 1** — blocks safely writing any of the upcoming v3.1 migrations that Items 5, 9, 11, and 12 all depend on landing correctly, now that their specs are no longer the blocker.
