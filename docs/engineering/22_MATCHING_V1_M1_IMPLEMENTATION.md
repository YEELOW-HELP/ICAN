# 22. Matching V1 M1 — Structured Assessment Data Model Implementation

**Status:** IMPLEMENTED (Founder Review "M1 GO", 2026-08-28). Scope: versioned structured (BASIC) question bank + attempt/answer persistence + assessment modes + zero-AI architecture. No scoring, no matching, no Telegram integration — see `docs/engineering/21_MATCHING_V1_RECONCILIATION_AND_IMPLEMENTATION_PLAN.md` §5 (M1) for the full slice boundary, unchanged.

---

## 1. New module map

| File | Purpose |
|---|---|
| `app/db/models_basic_assessment.py` | 7 new tables + 6 enums + `compute_matching_usage()` |
| `app/services/basic_assessment/definitions.py` | `get_active_definition`, `get_active_items` |
| `app/services/basic_assessment/validation.py` | `validate_response` — pure, no DB/AI |
| `app/services/basic_assessment/attempts.py` | attempt lifecycle: create/answer/complete |
| `app/services/basic_assessment/seed.py` | idempotent seed of the Alpha Long Form (75 items) |
| `migrations/versions/8e2c4a71d9f3_matching_v1_m1_basic_assessment.py` | additive migration, 7 tables |

Nothing in `app/services/assessment/` (PRO Hybrid), `app/db/models_assessment.py`, `app/bot/`, or `app/api/` is modified.

---

## 2. Assessment mode architecture

`AssessmentMode` (`BASIC_STRUCTURED` | `PRO_HYBRID`) lives only on the new `AssessmentDefinition.mode` column — it does not touch `InterviewSession.mode` (the existing free-text `"hybrid"` string), and no migration alters that column. The two modes are two entirely separate table families with no shared FK in either direction except both ultimately referencing `identity_users` (the shared, unmodified identity root). A user may have one open `InterviewSession` (PRO) and one open `BasicAssessmentAttempt` (BASIC) at the same time — the two state machines never interact, never gate each other, and this is the intended, permanent architecture, not a migration-in-progress state.

---

## 3. Question-bank schema

`AssessmentScale` (scale-level MNP↔O*NET compatibility metadata) → `AssessmentDefinition` (one versioned bank) → `AssessmentSection` (UI grouping) → `AssessmentItem` (one question, FK to both its section and its scale) → `AssessmentItemOption` (choice items only). `matching_usage` is computed once, at seed time, via `compute_matching_usage(mapping_status)` — the single function every scale's usage passes through; nothing else in the codebase is permitted to set it. `AssessmentItem.matching_usage` denormalizes the same value for fast per-item filtering without a join.

## 4. Seeded Alpha Long Form — exact counts

`assessment_version = "matching_v1_alpha_long_form_v0.1"`, seeded by `seed_alpha_long_form()`, idempotent (a second call is a no-op). Item count is **never hardcoded** in business logic — every count below is `len()` of a DB query result, verified by `tests/test_basic_assessment_seed.py::test_seed_is_idempotent_exactly_intended_bank_active`.

| Scale family | Scales | Items/scale | Items |
|---|---|---|---|
| RIASEC | 6 | 3 | 18 |
| Work Style | 10 | 2 | 20 |
| Work Values | 8 | 2 | 16 |
| Work Environment | 5 | 1 | 5 |
| Goals | 2 | 1 | 2 |
| Constraints | 10 | 1 | 10 |
| Experience | 4 | 1 | 4 |
| **Total** | | | **75** |

Mapping-status breakdown (30 scales total): RIASEC 6 DIRECT; Work Style 3 DIRECT / 2 DERIVED / 4 PROXY / 1 MNP_ONLY; Work Values 3 DIRECT / 2 PROXY / 3 MNP_ONLY; Work Environment 2 DIRECT / 3 DERIVED; Goals/Constraints/Experience (16 scales) all MNP_ONLY.

`matching_usage` breakdown: **MATCH_ENABLED** = RIASEC(6) + Work Style DIRECT+DERIVED(5) + Work Values DIRECT(3) + Work Environment(5) = **19 scales**. **PROFILE_ONLY** = Work Style PROXY+MNP_ONLY(5) + Work Values PROXY+MNP_ONLY(5) + Goals/Constraints/Experience(16) = **26 scales**. (Known limitation §7 below explains a deliberate one-item resolution of a minor spec ambiguity between the Golden Test doc's Constraints/Experience "education level" mention.)

## 5. Structured-answer schema & validation

`BasicAssessmentAnswer` mirrors the existing `Answer` model's immutability/idempotency convention exactly: never updated, `UNIQUE(attempt_id, idempotency_key)`, "latest by `created_at` wins" is the read convention (`attempts.latest_answers_by_item`). `validate_response()` (pure function, no DB/AI) enforces: LIKERT_5 ∈ [1,5] int only; NUMERIC requires a value; BOOLEAN requires a bool; SINGLE_CHOICE requires exactly one option from the item's declared set; MULTI_CHOICE requires ≥1, all from the declared set, no duplicates. Any mismatch raises `InvalidResponseError` (`app/services/exceptions.py`).

## 6. Retake / one-attempt-at-a-time

`uq_one_open_basic_attempt_per_user` (partial unique index on `basic_assessment_attempts.user_id`, `WHERE status IN ('not_started','in_progress')`) is the DB-level guarantee — mirrors `interview_sessions`' existing pattern but as a wholly separate constraint. `get_or_create_active_attempt()` is idempotent (resumes an open attempt); a genuinely new attempt is only possible once the current one reaches `COMPLETED`. `submit_answer()` rejects outright against a `COMPLETED`/`CALCULATED` attempt (`BasicAttemptClosedError`) — completion is the lock, there is no separate lock step.

## 7. Known limitation — Constraints/Experience "education level"

`MNP_GOLDEN_TEST_V0.1.md` §1/§14 lists "education level" as both a Constraints-block feasibility input *and* one of Experience's 4 items — a minor spec redundancy in the M0 methodology document, only surfaced during M1 implementation. Resolved here by seeding the education question once, under Constraints (where it functions as a feasibility input per §20–21 of that document), and giving Experience a distinct 4th item (`current_field`) instead — preserving the documented 10+4=14 item count without asking the user the same question twice. This is a naming/placement clarification only; no methodology content was invented. Flagged for a future light-touch correction to the Golden Test doc's §1 table.

## 8. Zero-AI guarantee

`tests/test_basic_assessment_zero_ai.py` enforces this two ways: (a) an AST-based static scan (mirroring the existing Direction Intelligence readmodel privacy-guard pattern) failing if any module under `app/services/basic_assessment/` or `app/db/models_basic_assessment.py` imports `app.ai_gateway` or references `AIGateway`/`AnswerExtractor`/`ClaimSynthesizer`/etc. by name; (b) a behavioral guard that monkeypatches `AIGateway.call_tool` to raise, then drives a complete BASIC attempt end-to-end (seed → start → answer all 75 items → complete) and asserts it never fires.

## 9. Migration

`8e2c4a71d9f3`, `down_revision = 4f1d7c92e6ab` (the prior single head). Purely additive — 7 new tables, zero altered/dropped columns on any existing table. Verified independently (via a standalone `MigrationContext`/`Operations` harness, isolated from the rest of the migration chain) that `upgrade()` creates exactly the 7 intended tables and `downgrade()` cleanly removes them, since the full `alembic upgrade head` chain cannot run end-to-end against SQLite in this environment (a pre-existing, unrelated migration several revisions earlier uses a Postgres-only `ALTER COLUMN ... TYPE` statement — this project has always targeted Postgres in production per `.env.example`; no live Postgres instance is available in this sandbox, a known limitation carried over from Stage 4A.5).
