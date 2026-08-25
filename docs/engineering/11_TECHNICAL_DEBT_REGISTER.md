# Technical Debt Register

Sprint 0, Part 3 (Issue #12). Documentation only — no production code, schema,
or migration is included in this change. Nothing in this document is
implemented; it is a tracked inventory for sequencing future work.

Sources: Part 1 (regression baseline, `tests/`), Part 2
(`docs/engineering/10_CURRENT_TO_TARGET_MIGRATION_MAP.md`), and the two
Founder/Product decisions recorded below.

---

## Recorded Founder/Product decisions (decided, not yet implemented)

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
- Tracked as Item 12 below.

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
  scope for Part 3 by instruction).
- Tracked as Item 11 below.

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
- **When must be resolved:** before the first v3.1 schema migration (User/AuthIdentity, Consent, InterviewSession) is written — those are exactly the kind most likely to contain non-trivial DDL.
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

- **Category:** Production Defect
- **Severity:** High
- **Probability:** Certain — already occurred in production, reproducibly, for at least two accounts, including one with zero prior history (which disproved the original "stale update backlog" theory).
- **Blast radius:** Wide — affects the entire onboarding/anketa flow for any live Telegram user.
- **Current evidence:** live-testing screenshots (pre-Sprint-0) showing cascading bot messages with missing inline keyboards after `/start`. `bot.delete_webhook(drop_pending_updates=True)` (`app/bot/main.py`) was added as a fix attempt but the identical failure reproduced afterward for a brand-new account. Root cause was never confirmed.
- **Recommended mitigation:** do not attempt a point-fix. The Migration Map (Part C, #5) already identifies the architectural fix — replacing aiogram's in-memory `MemoryStorage` FSM with the target `InterviewSession`/`Answer` DB-backed state machine. Treat this bug as a driving requirement for that migration's priority, not a separate patch. See also Item 15 (related, distinct finding).
- **When must be resolved:** before Telegram bot traffic resumes in production.
- **Blocks R0/R1:** Does not block R0/R1 engineering (bot traffic is currently paused); blocks re-enabling live Telegram traffic.
- **Owner role:** Backend / Tech Lead.

---

## B. Specification gaps (from Part 2)

### 5. `AuthIdentity` missing field-level specification

- **Category:** Specification Gap (ERD)
- **Severity:** Medium
- **Probability:** Certain
- **Blast radius:** Wide — blocks the #1 highest-risk migration (User canonicalization) from starting with a concrete target schema.
- **Current evidence:** `docs/architecture/02_ERD.md` has no `AuthIdentity` entity; `docs/engineering/09_MIGRATION_AND_TEAM_OWNERSHIP.md` references it only in prose ("Add canonical User/AuthIdentity/Consent/AssessmentSession structures").
- **Recommended mitigation:** Tech Lead to add `AuthIdentity` (`provider`, `provider_user_id`, `user_id` FK, `verified_at`) to `02_ERD.md` before Migration Map Part A #1 is implemented.
- **When must be resolved:** before any canonical User/AuthIdentity migration is written.
- **Blocks R0/R1:** Blocks the User-canonicalization migration specifically; does not block current R0 scope.
- **Owner role:** Tech Lead.

### 6. `AuditLog` missing from ERD

- **Category:** Specification Gap (ERD)
- **Severity:** Low/Medium
- **Probability:** Certain
- **Blast radius:** Moderate — affects the eventual migration path for `ProfileEditLog` and `TimelineEvent`, both of which work fine today.
- **Current evidence:** named in `01_SYSTEM_ARCHITECTURE.md` §3 (Platform context), absent from `02_ERD.md`.
- **Recommended mitigation:** define `AuditLog` fields (actor, entity_type, entity_id, before/after, occurred_at) in `02_ERD.md` once the Platform bounded context is scheduled.
- **When must be resolved:** before `ProfileEditLog`/`TimelineEvent` are migrated — not urgent, both REUSE cleanly today.
- **Blocks R0/R1:** No.
- **Owner role:** Tech Lead.

### 7. Raw transcript/audit entity missing

- **Category:** Specification Gap (ERD)
- **Severity:** Low
- **Probability:** Certain
- **Blast radius:** Narrow — affects only how `Message`'s free-form transcript is preserved once `INTERVIEW_SESSION`/`ANSWER` exist.
- **Current evidence:** `02_ERD.md` has no entity for conversational transcript; `ANSWER` assumes a fixed `question_id`, which the current fully-conversational agent doesn't produce.
- **Recommended mitigation:** decide whether raw transcript becomes a dedicated entity, or is intentionally not persisted once the Interview Orchestrator exists — a Product/Methodology call, not an engineering default.
- **When must be resolved:** before the Interview Orchestrator (`04_AI_SYSTEM.md` component #1) is built.
- **Blocks R0/R1:** No — `Message` keeps working as-is until then.
- **Owner role:** Product / Methodology Lead (decision), Tech Lead (schema).

### 8. Language taxonomy/entity missing

- **Category:** Specification Gap (ERD)
- **Severity:** Low
- **Probability:** Certain
- **Blast radius:** Narrow — affects only `ClientLanguage`'s eventual migration.
- **Current evidence:** `02_ERD.md` defines `SKILL`/`USER_SKILL` but no language equivalent anywhere.
- **Recommended mitigation:** add a language entity (or extend `SKILL` with a `type` discriminator) to the ERD.
- **When must be resolved:** before `ClientLanguage` is migrated — not urgent, REUSE today.
- **Blocks R0/R1:** No.
- **Owner role:** Tech Lead / Methodology.

### 9. `GOAL`/`CONSTRAINT`/`EXPERIENCE` missing field-level ERD

- **Category:** Specification Gap (ERD)
- **Severity:** Medium
- **Probability:** Certain
- **Blast radius:** Wide — blocks migrating the CRM's richest, most human-verified data (`ClientProfile`, `WorkExperience`).
- **Current evidence:** named only as bounded-context labels in `01_SYSTEM_ARCHITECTURE.md` §3; no field-level definition in `02_ERD.md`.
- **Recommended mitigation:** Tech Lead + Methodology to define fields for all three, explicitly preserving `ClientProfile.critical_constraint`'s hard-block semantics (`01_SYSTEM_ARCHITECTURE.md` §8: "hard constraints cannot be overridden by an LLM").
- **When must be resolved:** before `ClientProfile`/`WorkExperience` migration (Migration Map #7, #8) starts.
- **Blocks R0/R1:** Blocks that specific future migration; does not block current R0 scope (R0 is Profile→Scenarios for new users, not CRM data migration).
- **Owner role:** Tech Lead + Methodology Lead.

### 10. `TASK` naming collision

- **Category:** Specification Gap / Naming
- **Severity:** Low today, High if ignored during actual migration (real data-corruption risk)
- **Probability:** Medium — realistic risk a future engineer conflates the two `Task` concepts without this document in view.
- **Blast radius:** Moderate — a mistaken merge would corrupt both CRM operational tasks and roadmap execution tasks.
- **Current evidence:** `app/db/models_crm.py`'s `Task` (staff reminder) vs. the target ERD's `TASK` (candidate-facing roadmap step) — same name, unrelated concepts (Migration Map Part D #4).
- **Recommended mitigation:** rename the CRM table (`Task`/`tasks` → e.g. `StaffTask`/`staff_tasks`) the next time this area is touched, to remove the ambiguity at the source.
- **When must be resolved:** before the Execution bounded context (`ROADMAP`/`TASK`) is implemented, ideally earlier.
- **Blocks R0/R1:** No — a naming/clarity risk, not a functional blocker.
- **Owner role:** Backend.

### 11. Versioned taxonomy architecture not yet specified

- **Category:** Specification Gap (Methodology/Architecture)
- **Severity:** High
- **Probability:** Certain — Decision 2 above confirms versioned taxonomies are required, but no schema exists for how a taxonomy version attaches to `PROFILE_CLAIM`/`EVIDENCE`/results.
- **Blast radius:** Wide — blocks Migration Map #2/#7 (`Profile`/`ClientProfile` → `PotentialProfile`/`ProfileClaim`) and all Methodology work on dimensions/strengths/skills/etc.
- **Current evidence:** Decision 2 lists the required taxonomy categories and requires historical traceability to the producing version; `02_ERD.md` today only versions the *profile* (`POTENTIAL_PROFILE.version`/`.model_version`), not the *taxonomy* it was scored against.
- **Recommended mitigation:** Tech Lead + Methodology Lead to design a `TaxonomyVersion` (or equivalent) entity and confirm how `PROFILE_CLAIM`/`EVIDENCE`/`SCENARIO` reference it, starting with Taxonomy v1. Explicitly out of scope here — tracked as a blocker, not designed.
- **When must be resolved:** before any `PROFILE_CLAIM`/`EVIDENCE` migration or generation work begins.
- **Blocks R0/R1:** Blocks R1 (Evidence Graph + Direction + Roadmap explicitly requires evidence-linked claims per `docs/product/00_MASTER_INDEX.md`'s release table); does not necessarily block a narrowly-scoped R0 (Product to confirm).
- **Owner role:** Methodology Lead (accountable) + Tech Lead (schema).

### 12. `CLIENT_ASSIGNMENT` model not yet specified

- **Category:** Specification Gap (Architecture)
- **Severity:** Medium
- **Probability:** Certain — Decision 1 above confirms the concept but explicitly defers naming/schema.
- **Blast radius:** Moderate — blocks Migration Map #6 (`Client` split) from fully resolving the `manager_id` gap; current dual `manager_id`/`consultant_id` ownership keeps working as-is until this lands.
- **Current evidence:** Decision 1 — Manager and Guide are separate concepts; `CLIENT_RELATIONSHIP` is client↔guide only; a future `CLIENT_ASSIGNMENT`-type model must support `MANAGER`/`COORDINATOR` and potentially other operational roles.
- **Recommended mitigation:** Tech Lead to design `CLIENT_ASSIGNMENT` (or final name) — likely `client_id`, `assignee_id`, `assignment_type` enum, effective date range for history — once `TENANT`/`MEMBERSHIP` is further along. Explicitly out of scope here — tracked, not designed.
- **When must be resolved:** before the `Client` → `USER`/`CLIENT_RELATIONSHIP` split (Migration Map #6) is implemented; until then, `manager_id`/`consultant_id` semantics are preserved unchanged, per Decision 1.
- **Blocks R0/R1:** No — current CRM assignment flow keeps working; only blocks the future `Client` split.
- **Owner role:** Tech Lead.

---

## C. Additional debt identified during Part 1/2 work

Not explicitly requested, included for completeness since each is a concrete finding already surfaced during this sprint's own analysis, not new speculative digging.

### 13. No consent/privacy tracking exists

- **Category:** Compliance / Privacy Risk
- **Severity:** High
- **Probability:** Certain — confirmed absence, not speculative.
- **Blast radius:** Wide — affects every user who has completed screening (Telegram) or been entered into the CRM (any channel).
- **Current evidence:** no `Consent`-shaped table in `app/db/models.py` or `app/db/models_crm.py`; no consent-capture endpoint anywhere in `app/api/`; the target `CONSENT` entity has no current counterpart at all (Migration Map Part B).
- **Recommended mitigation:** Product/Legal to confirm whether current data collection requires retroactive consent capture, and prioritize `CONSENT` implementation ahead of any new user-data collection in v3.1 — not just as a v3.1 nice-to-have.
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
- **When must be resolved:** before any `AuditLog` migration (Item 6) relies on stable actor identity.
- **Blocks R0/R1:** No.
- **Owner role:** Backend.

### 15. In-memory FSM state does not survive process restarts

- **Category:** Architecture / Reliability
- **Severity:** Medium
- **Probability:** Certain — `aiogram.Dispatcher()` uses `MemoryStorage` by default; no persistent storage backend is configured anywhere in `app/bot/main.py`. Any Railway restart/redeploy silently resets every in-progress conversation's FSM state.
- **Blast radius:** Moderate — affects any user mid-conversation at deploy time. This was the original (later disproven) hypothesis for Item 4 — tracked separately here as a distinct, confirmed weakness even though it didn't turn out to fully explain that bug.
- **Current evidence:** no `RedisStorage`/DB-backed storage configured; `bot.delete_webhook(drop_pending_updates=True)` was added specifically to paper over this by discarding queued updates on restart, not to fix the underlying statelessness.
- **Recommended mitigation:** superseded by the planned `InterviewSession`/`Answer` DB-backed state machine (Migration Map, Part B) — no interim fix recommended given the replacement is already planned.
- **When must be resolved:** same as Item 4 — before Telegram bot traffic resumes in production.
- **Blocks R0/R1:** No (bot traffic currently paused).
- **Owner role:** Backend.

---

## Summary

**15 items tracked:** 4 test-coverage gaps (Part 1), 8 specification gaps (Part 2, including the two now-decided-but-undesigned items 11/12), 3 additional findings from this sprint's own analysis.

**Blocks R0 rollout today:** Item 13 (consent) — pending a Product/Legal decision, not an engineering one.

**Blocks R1 specifically:** Item 11 (versioned taxonomy) — R1's Evidence Graph deliverable depends on it.

**Must resolve before Telegram traffic resumes (not R0/R1-gated, since bot traffic is currently paused):** Items 4 and 15.

**Gate specific future migrations but don't block current sprint work:** Items 1, 5, 6, 7, 8, 9, 10, 12, 14.

**Pure test-coverage gaps, lowest urgency:** Items 2, 3.

Recommended immediate attention, in order (recommendation only, not a decision):
1. **Item 13** — real compliance exposure today, independent of any migration timeline.
2. **Item 11** — blocks R1 and now has confirmed direction (Decision 2) but no owner-assigned schema yet.
3. **Item 1** — blocks safely writing any of the upcoming v3.1 migrations that Items 5, 9, 11, and 12 all depend on landing correctly.
