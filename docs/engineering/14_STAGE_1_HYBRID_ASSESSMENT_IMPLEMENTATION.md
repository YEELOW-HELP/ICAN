# Stage 1: Core Hybrid Assessment — Implementation Reference

Branch: `stage-1-core-hybrid-assessment-v1` (based on `product-system-v3.1`).
Implements the vertical slice authorized by the Founder's Stage 1 brief:
identity → consent → product access → Hybrid assessment (structured +
open + adaptive + optional CV) → pause/resume → completion, all
PostgreSQL-persisted, reachable from Telegram behind a feature flag.

This document is a reference for engineers and reviewers, not a product
spec — see `docs/product/14_MIY_NAPRYAM_V1_PRODUCT_DEFINITION.md` and
`15_MIY_NAPRYAM_V1_IMPLEMENTATION_ROADMAP.md` for product scope.

## 1. New tables

| Module | Tables |
|---|---|
| `app/db/models_identity.py` | `identity_users`, `auth_identities`, `consents` |
| `app/db/models_access.py` | `product_plans`, `organizations`, `package_allocations`, `promo_codes`, `promo_redemptions`, `entitlements` |
| `app/db/models_assessment.py` | `interview_sessions`, `answers`, `interview_messages`, `question_selections`, `cv_uploads` |
| `app/db/models_platform.py` | `audit_log` |

Plus: `admin_users.role` widened with `SUPER_ADMIN`/`REVIEWER`; `users.canonical_user_id`
(nullable FK to `identity_users.id`) as the additive legacy bridge.

Nothing in `app/db/models.py` (legacy `User`/`Profile`/`Message`) is read
by any Stage 1 module, and vice versa — the two schemas are independent
except for the one bridge column.

## 2. Migration chain

1. `cd3d7f6f9e54` — all 15 tables above + the `admin_users.role` enum
   widening + the `users.canonical_user_id` bridge column. Purely
   additive; no data backfill (Founder decision 2).
2. `fa4da9c6032d` — `uq_one_unfinished_session_per_user`: a partial
   unique index on `interview_sessions.user_id` WHERE
   `status IN ('draft','active','paused')` (Founder decision 3). Built as
   a `sqlalchemy.Index` with both `postgresql_where` and `sqlite_where` so
   the same constraint is real in both the SQLite test fixture and
   production PostgreSQL — not a SQLite-only proof.

Both are verified against real PostgreSQL by the `postgres-migrations`
CI job (Sprint 1 Part 0) via `tests/test_migrations_postgres.py`, and
structurally by `tests/test_migrations.py` (single head, fully linked,
no duplicate revisions) on every run.

Downgrading `cd3d7f6f9e54` is destructive once real Stage 1 traffic
exists (drops 15 tables) — see that migration's docstring. Downgrading
`fa4da9c6032d` is always safe (drops one index).

## 3. Identity

`app/services/identity.py`. `IdentityUser` is canonical; `AuthIdentity`
is one `(provider, provider_subject)` login method. A Telegram numeric ID
is never the canonical identity — it is `AuthIdentity.provider_subject`
for `provider="telegram"`, looked up through `UNIQUE(provider,
provider_subject)`.

`resolve_identity()` is the only place allowed to create these rows. It
is race-safe: an optimistic insert that recovers via re-read on
`IntegrityError` rather than a non-atomic check-then-insert.

Legacy bridge: if a Telegram ID resolving through `resolve_identity`
already has a legacy `users` row, `_link_legacy_telegram_user` sets that
row's `canonical_user_id` — opportunistically, on real traffic only,
never a bulk backfill (Founder decision 2).

## 4. Consent

`app/services/consent.py`. `Consent` rows are append-only — a withdrawal
followed by a fresh grant is a new row, never a re-activated old one.
`grantor_role` (`self` / `guardian` / `authorized_representative`)
supports guardian-granted consent without a separate table.
`has_active_consent(user_id, purpose)` is the single gate every
access-controlled flow calls — there is no UI-only consent check
anywhere.

## 5. Product access / entitlements

`app/services/product_access.py`. Chain: `Organization` →
`PackageAllocation` → `PromoCode` → `PromoRedemption` → `Entitlement`.
`ProductPlan` (`BASIC`/`PREMIUM`) holds price as data, never as branching
logic. No real payment provider exists yet (Stage 4) — `MANUAL` (admin
grant) and `PROMO` (code redemption) are the only entitlement sources.

- `can_user_start_assessment(user_id, plan_code=None)` — the single yes/no
  gate.
- `get_any_active_entitlement(user_id, plan_code=None)` — same query, but
  returns the entitlement (needed to know which `plan_code` to start an
  assessment under).
- `redeem_promo_code` is idempotent (`UNIQUE(promo_code_id, user_id)` +
  optimistic-insert-with-recovery) and race-safe against allocation
  overspend (`PackageAllocation` row locked with `with_for_update()`
  before counting existing redemptions — a no-op on SQLite, real on
  PostgreSQL).
- `grant_manual_access` / `create_package_allocation` are role-gated
  (`SUPER_ADMIN` / `ADMIN` / `MANAGER` only, via `_require_grant_role`)
  and write an `AuditLog` entry.

## 6. Assessment state machine

`app/services/assessment/state_machine.py`. Canonical states:

```
draft -> active -> paused -> complete -> processing -> ready
  |         |         |                        |
  +-------- +-------- +------------------------+--> failed
```

- `FAILED` and `READY` are terminal — no outgoing transition exists from
  either (Founder decision 5).
- `PAUSED -> ACTIVE` happens two ways: explicitly (`resume_assessment`,
  e.g. a `/resume`-style command with no new answer) or automatically the
  moment a valid new answer is submitted to a paused session
  (`submit_answer`) — both are exercised by dedicated tests (Founder
  decision 4).
- Nothing outside `state_machine.transition()` may assign
  `InterviewSession.status` — Telegram handlers never mutate state
  directly (Section 17/`app/bot/handlers_v1.py` only calls the domain
  commands).
- `fail_session()` is an administrative escape hatch. An ordinary AI
  provider failure during extraction does **not** call it — the session
  stays `ACTIVE` so the next message gets a fresh attempt (Founder
  decision 8, no automatic retry either).

**One unfinished session per user** (Founder decision 3):
`start_assessment` checks `get_unfinished_session_for_user` first and
raises `UnfinishedAssessmentExistsError` if one exists; the partial
unique index (`fa4da9c6032d`) is the authoritative guard against the
race (a concurrent `IntegrityError` on double-start also raises the same
error).

## 7. Idempotent, channel-agnostic answers

`app/services/assessment/sessions.py::submit_answer`. Keyed by
`UNIQUE(session_id, idempotency_key)` — the caller supplies the key
(Telegram derives it from `message_id`/callback `id`; a future web
client would derive its own). A duplicate submission returns the
existing `Answer` row and never re-invokes the AI Gateway or re-emits
`answer_submitted`.

**Failure model**: the raw text is written to `InterviewMessage` (via
`record_message`) *before* extraction is attempted. If extraction raises
(provider outage, timeout, malformed response), the exception propagates
to the caller — it is deliberately not caught — but the session remains
`ACTIVE` and the candidate's actual words are never lost; only the
structured `Answer` row for that attempt does not exist yet. See
`tests/test_assessment_ai_failure.py`.

## 8. Hybrid: structured + open + adaptive

`app/services/assessment/question_bank.py` defines a small, versionable
question bank (`kind="structured"` = fixed-choice, zero AI cost;
`kind="open"` = free text, extracted via the AI Gateway).
`app/services/assessment/content.py` holds all Ukrainian copy as
locale-keyed data (`uk` populated; `ru`/`en`/`de` are architecture-ready
keys, not translated — explicitly out of Stage 1 scope).

**Adaptive selection** (`app/services/assessment/next_question.py`):
deterministic and server-side — the AI Gateway is *never* asked which
question to pick, only (separately) to extract structured content from
an already-given answer. Priority: `contradiction` > `low_confidence` >
`missing`, in question-bank order within each tier; a `resolved`
dimension is never reselected. Optional (non-required) dimensions are
only resurfaced via the `low_confidence`/`contradiction` tiers, never
because they are merely missing — this is what keeps the interview
bounded to the required set instead of exhausting the whole bank (a real
bug caught and fixed by `test_all_required_resolved_means_ready_for_completion`).
A hard safety cap (`settings.max_assessment_questions`, default 20)
forces completion-eligibility regardless of unresolved dimensions,
mirroring the legacy `ScreeningAgent`'s turn cap.

Every selection is a first-class `QuestionSelection` row — written
*before* the question is shown, with a `reason` — and is linked to the
`Answer` that resolved it (`mark_question_answered`). This is the
traceability Founder decision 7 asked for, in place of the originally
proposed `adaptive_question_log`.

**Completeness** (`app/services/assessment/completeness.py`) is a
deterministic policy over the *required* subset of the question bank —
never an LLM self-assessment (Founder requirement, item 13).

## 9. AI Gateway usage

`app/services/assessment/extraction.py::AnswerExtractor` wraps the
existing `app.ai_gateway.AIGateway` unchanged, tagged with a new
`prompt_version="hybrid-assessment-v1"` (distinct from legacy screening's
`legacy-screening-v1`, so the two remain independently evaluable). No
direct provider SDK call exists anywhere in Stage 1 code. No automatic
retry or fallback was added (Founder decision 8) — a failure surfaces to
the caller as-is.

## 10. Optional CV

`app/services/assessment/cv.py::upload_cv`. Reuses
`app/services/documents.py` unchanged (PDF/DOCX). Rejects files over
`settings.max_upload_size_mb` before extraction
(`CVFileTooLargeError`) — the same limit the CRM upload endpoint already
enforces, not a new hardcoded number. Extracted text is never trusted
directly: each open dimension the CV might answer still goes through
`AnswerExtractor`, and a result below `LOW_CONFIDENCE_THRESHOLD` (0.5)
is discarded rather than recorded — a vague CV must not silently mark a
dimension resolved and suppress a question that should still be asked.
Facts that *do* clear the bar land as ordinary `Answer` rows tagged
`source="cv"`; no Evidence Graph or Human Potential Profile entity is
created (that's Stage 2).

## 11. Telegram adapter

`app/bot/handlers_v1.py`, registered only when `settings.bot_flow ==
"v1"` (`app/bot/main.py` branches on this — exactly one handler set is
ever attached to the Dispatcher, never both, so there is no `/start`
ambiguity). Every handler: receive update → resolve identity → invoke a
channel-agnostic domain command (`resolve_identity`, `grant_consent`,
`redeem_promo_code`, `start_assessment`, `submit_answer`,
`pause_assessment`, `resume_assessment`, `upload_cv`,
`get_next_question_for_session`, `complete_assessment`) → render the
result. No handler assigns `InterviewSession.status` directly.

Resume-across-restart works because FSM state (aiogram's in-memory
`FSMContext`) is not the source of truth — on `/start`,
`get_unfinished_session_for_user` re-derives where the candidate is from
the database, so a process restart mid-assessment loses only the
transient "which exact FSM state" bookkeeping, not the assessment
itself. Verified by
`tests/test_bot_v1_e2e.py::test_resume_across_simulated_process_restart`,
which drives a second, independent `BotHarness`/Dispatcher against the
same database.

The legacy flow (`app/bot/handlers.py`) is untouched; `tests/test_bot_e2e.py`
and `tests/test_ai_provider_failure.py` continue to pass unmodified.
Cutover from legacy to v1 is a separate, explicitly reviewed decision —
`bot_flow` defaults to `"legacy"`.

## 12. Events and audit

`app/services/events.py::emit_event` — structured-logged (not persisted;
same scoping decision already made for `AI_TRACE` in Sprint 0), never
raises, never carries raw answer/CV text or secret tokens — only IDs,
enum values, and plan/promo codes. Emitted: `identity_created`,
`consent_granted`, `product_access_granted`, `promo_redeemed`,
`assessment_started`, `answer_submitted`, `assessment_paused`,
`assessment_resumed`, `cv_uploaded`, `cv_processed`,
`assessment_completed`, `assessment_failed`.

`app/services/audit.py::record_audit` — append-only, wired into
`grant_manual_access` and `create_package_allocation` (privileged,
security-sensitive mutations). `issue_promo_code` is not separately
audited in Stage 1: it always draws from an allocation whose creation
was already audited and role-checked; adding a second audit entry for
drawing a code from an already-audited allocation was judged
disproportionate for this stage (documented limitation, §14).

## 13. Feature flags / config

`app/core/config.py`: `bot_flow` (`"legacy"` default | `"v1"`),
`default_locale` (`"uk"`), `max_assessment_questions` (`20`).

## 14. Known limitations / deferred tech debt

- `issue_promo_code` does not write its own `AuditLog` entry (see §12) —
  revisit if promo-code issuance needs independent audit granularity.
- No admin UI/endpoint exists yet to change an `AdminUser.role` — so
  "privileged role change" audit logging has nothing to hook into yet;
  add it when that mutation is built.
- The Stage 1 question bank (`question_bank.py`) is a small, explicit
  set, not the final Taxonomy v1 content — Methodology's future work
  (`docs/engineering/11_TECHNICAL_DEBT_REGISTER.md` Item 11).
  `total_experience`/`employment_format`/`constraints` are optional and
  may go unanswered in a completed assessment; this is intentional
  (bounds interview length) but means Stage 2 profile-building must treat
  them as possibly-null.
- `ru`/`en`/`de` locale keys exist in `content.py` but are untranslated —
  `default_locale="uk"` is the only populated locale.
- Real PostgreSQL execution of both Stage 1 migrations is confirmed by
  the CI job on push, not locally (no local PostgreSQL instance in this
  environment) — consistent with the Sprint 1 Part 0 precedent.
- CV content-type is not recorded on `CVUpload` (the column exists,
  nothing sets it) — filename extension is what `documents.extract_text`
  actually keys off, so this is cosmetic, not a functional gap.
