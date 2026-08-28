# 23. Matching V1 M2 — Deterministic Profile Engine

**Status:** IMPLEMENTED (Founder Review "M2 GO", 2026-08-28). Scope: deterministic profile calculation over a COMPLETED `BasicAssessmentAttempt`. Zero LLM tokens. No career vectors, no matching, no O*NET/Work.ua import, no UI — see `docs/engineering/21_..._IMPLEMENTATION_PLAN.md` §5 for the M1–M6 slice boundary (unchanged) and the M2 order's own §20 ("do not build") list.

This document does not restate `docs/product/20_MATCHING_V1_FOUNDER_DEFINITION.md`; it documents what M2 actually implemented.

---

## 1. New module map

| File | Purpose |
|---|---|
| `app/db/models_basic_profile.py` | 4 new tables + 3 enums, wholly separate from `models_profile.py`'s PRO Hybrid `PotentialProfile` family |
| `app/services/basic_profile/config.py` | versioned, documented constants — nothing inlined as magic numbers |
| `app/services/basic_profile/calculation.py` | `calculate_basic_profile`, `recalculate_basic_profile` |
| `app/services/basic_profile/queries.py` | `get_basic_profile`, `get_profile_scale_results` |
| `app/services/basic_profile/contract.py` | `BasicProfileResult` — channel-independent read contract |
| `migrations/versions/b3f7d1c92a56_...py` | additive migration, 4 tables |

M1's tables/services (`app/db/models_basic_assessment.py`, `app/services/basic_assessment/`) are unmodified. PRO Hybrid (`models_profile.py`, `models_assessment.py`) is unmodified.

---

## 2. Persistence decision (audit result)

`PotentialProfile`/`ProfileClaim`/`Evidence` (Stage 2) are evidence-grounded claim models with an `extraction_method ∈ {"deterministic","llm_extraction"}` field and a `prompt_version` column — i.e. the schema itself assumes an AI-provenance story even for its "deterministic" claims. Reusing it for BASIC would either force fake evidence/claim rows around a plain Likert mean, or silently blur BASIC's zero-AI provenance into a model designed to carry AI provenance. Per Founder Review instruction 11, a new, wholly separate family was built instead: `DeterministicProfile` reuses only `PotentialProfile`'s **versioning idiom** (one row per generation attempt, `is_current` + a partial unique index per user, `supersedes_id` chain) — the one part of that design that generalizes cleanly — without inheriting any of its AI-specific columns.

---

## 3. Profile-engine architecture

`calculate_basic_profile(session, attempt)` is the single entry point. It:
1. Requires `attempt.status ∈ {COMPLETED, CALCULATED}` (else `BasicAttemptNotCompletedError`).
2. Is idempotent per `(attempt_id, profile_engine_version)` — a second call for an already-calculated (attempt, engine version) pair returns the existing row untouched, no duplicate work, no mutation.
3. Reads `AssessmentItem`/`AssessmentScale` (M1, read-only) and the attempt's `BasicAssessmentAnswer` rows via M1's own `latest_answers_by_item` (M1's "latest wins" convention, reused, not reimplemented).
4. Computes every Likert scale's raw/normalized value, the schema-driven Coverage, the separate context completeness, the per-vector-family differentiation state, and the RIASEC ordering — all pure functions of already-persisted data.
5. Persists one `DeterministicProfile` + N `ProfileScaleResult` + 4 `ProfileVectorDifferentiation` + M `ProfileStructuredContext` rows, flips `attempt.status → CALCULATED`, and supersedes (never edits) any prior `is_current` profile for the same user.

`recalculate_basic_profile` is a documented alias with identical behavior — Founder Review's suggested interface list, no separate "force" semantics (that would violate immutability).

No Telegram/Web/API/UI code exists anywhere in this package.

---

## 4. Scoring formulas implemented (verbatim from the canonical methodology, no new formula invented)

- **Reverse scoring** (`MNP_GOLDEN_TEST_V0.1.md` §5): `corrected = 6 - raw` when `item.reverse_scored`.
- **Per-scale scoring** (§6): `raw_mean = mean(corrected values)`; `normalized_value = (raw_mean - 1) / 4`.
- **Missing-answer / sufficiently-answered** (§7): a scale is sufficiently answered if `answered_items ≥ ceil(0.8 × items_total)`; below that, the scale is **UNSCORED** (`raw_mean`/`normalized_value` stay `NULL`), never scored on the reduced subset.
- **Coverage** (§15, hardened): `coverage = scored_required_scales / enabled_required_scales`, where both numerator and denominator are computed live from the active `AssessmentItem`/`AssessmentScale` rows of the attempt's own `AssessmentDefinition` — **29 never appears as a literal in the code**; it is only what the current seeded schema happens to evaluate to (proven directly by `test_coverage_schema_driven_not_hardcoded`, which mutates the schema and observes the denominator move from 29 to 28).
- **Differentiation gate** (`MNP_MATCHING_METRIC_BENCHMARK_V0.1.md` §6): population `stdev` over a vector family's sufficiently-answered normalized components; `< 0.10` (the Founder-approved, versioned, configurable `DIFFERENTIATION_STDEV_THRESHOLD`) → `LOW_DIFFERENTIATION`. A family with `<80%` of its own scales sufficiently answered, or fewer than 2 computable components, is `INSUFFICIENT_DATA` outright — never scored on a too-thin vector.
- **RIASEC ordering** — the one genuinely new mechanical rule this slice adds: descending `normalized_value`, ties broken by ascending `scale_key` (alphabetical). This is a plain engineering tie-break, not a methodology interpretation, and produces **no archetype/personality label** — only an ordered list of letters.

---

## 5. Result contracts

**RIASEC**: 6 `ProfileScaleResult` rows (`scale_key ∈ {R,I,A,S,E,C}`), each with `raw_mean`/`normalized_value`/`sufficiently_answered` + denormalized `mapping_status=DIRECT`/`matching_usage=MATCH_ENABLED` (all six, per the M0 mapping doc). Plus `DeterministicProfile.interest_ordering` (deterministic list) and one `ProfileVectorDifferentiation` row.

**Work Style**: 10 `ProfileScaleResult` rows, all computed regardless of `matching_usage` — 3 DIRECT/2 DERIVED (MATCH_ENABLED), 4 PROXY/1 MNP_ONLY (PROFILE_ONLY), every one still carries a real `normalized_value` (Founder Review §5: PROFILE_ONLY is not a reason to hide a measured characteristic).

**Work Values**: 8 `ProfileScaleResult` rows, same rule (3 DIRECT MATCH_ENABLED, 5 PROXY/MNP_ONLY PROFILE_ONLY, all computed).

**Work Environment**: 5 `ProfileScaleResult` rows, all MATCH_ENABLED (2 DIRECT, 3 DERIVED per the mapping doc) — this vector is USER PROFILE ONLY in M2; no career-side comparison exists yet (Founder Review §7).

**Structured Goals/Experience/Constraints**: `ProfileStructuredContext` rows, one per answered item, storing exactly the raw answer value (`numeric_value`/`boolean_value`/`selected_option_keys`) with no synthesized severity/hardness/confidence field — verified structurally by `test_no_invented_constraint_hardness` (`hasattr(row, "is_hard")` etc. is `False`; no such column exists on the model at all).

**Channel-independent contract**: `BasicProfileResult` (`app/services/basic_profile/contract.py`) — `interests`/`work_styles`/`work_values`/`work_environment` (each a `VectorView`: scale results + differentiation state + stdev), `goals`/`experience`/`constraints` (lists of `StructuredContextItemView`), `coverage`/`coverage_band`/`context_completeness`/`differentiation_state`/`interest_ordering`, and `provenance` (`ProvenanceView`). Pure dataclasses, no formatting, no locale strings — M5 (Telegram/Web, later) decides rendering.

---

## 6. User-facing bands — deliberately NOT invented

Per Founder Review §13, no HIGH/MEDIUM/LOW band is attached to any individual scale's `normalized_value` — the canonical methodology defines bands only for the *matching outputs* (Interest/Work Style/Values Fit, Feasibility — user×career comparisons, `MNP_GOLDEN_TEST_V0.1.md` §23), never for a raw single-scale profile value. Only Coverage's own three-band model (Full/Partial/Insufficient, already methodology-defined) and the differentiation state (Normal/Low/Insufficient, Founder-approved) are surfaced as bands. **Profile score ≠ Career Fit** — nothing in this module computes or implies a fit/compatibility judgment.

---

## 7. Provenance / versioning

Every `DeterministicProfile` stamps: `assessment_code` (derived from `assessment_version` by stripping a trailing `_v<n>` suffix — e.g. `matching_v1_alpha_long_form_v0.1` → `matching_v1_alpha_long_form`), `assessment_version`, `methodology_version` (both copied from the `AssessmentDefinition` used), `profile_engine_version` (`basic_profile_engine_v0.1`, this module's own code version). A version bump to any of these fields naturally produces a new `(attempt_id, profile_engine_version)` combination and therefore a new row — no historical row is ever reinterpreted under a later version.

---

## 8. Determinism proof

`test_same_answers_produce_identical_result`: two different `IdentityUser`s complete separate attempts with byte-identical answers; both profiles' `BasicProfileResult` (everything except `provenance`, which legitimately differs by user/attempt/timestamp) compare exactly equal via `dataclasses.asdict`. Re-invoking `calculate_basic_profile` a second time on the same attempt returns the same row (`profile.id` unchanged) — proven in the same test.

---

## 9. Zero-AI guarantee

Identical two-layer approach to M1: (a) AST-based static scan of every module under `app/services/basic_profile/` and `app/db/models_basic_profile.py`, failing on any import of `app.ai_gateway`/PRO Hybrid extraction modules or reference to `AIGateway`/`AnswerExtractor`/`ClaimSynthesizer`/etc.; (b) a behavioral guard that monkeypatches `AIGateway.call_tool` to raise, then calculates a full, real 75-answer profile end-to-end and asserts it completes.

---

## 10. Example persona outputs (engineering fixtures — NOT Golden Cases, NOT psychometric validation)

| Persona | RIASEC top | RIASEC differentiation | Overall differentiation* |
|---|---|---|---|
| A. technical/investigative | I, R | NORMAL | LOW (see note) |
| B. social/helping | S | NORMAL | LOW (see note) |
| C. entrepreneurial/leadership | E | NORMAL | LOW (see note) |
| D. artistic/creative | A | NORMAL | LOW (see note) |
| E. flat/undifferentiated | (none meaningful) | LOW_DIFFERENTIATION | LOW |

\* The overall `differentiation_state` reported by `BasicProfileResult` is the worst-case across all 4 vector families. Personas A–D deliberately bias only RIASEC (+1–2 Work Style/Values items) to isolate and verify the RIASEC-specific formula; their un-biased Work Style/Work Values/Work Environment vectors are therefore flat by construction and correctly report LOW_DIFFERENTIATION on their own — this is the guard working as intended (it does not get fooled into NORMAL by an unrelated, genuinely-differentiated RIASEC vector), not a defect in the personas. Each persona's `differentiation_state` on its own **interests** (`RIASEC`) vector specifically is asserted NORMAL for A–D and LOW_DIFFERENTIATION for E, matching the intended demonstration exactly.

---

## 11. Known limitations

- Personas A–D exercise only the RIASEC formula path directly; a future v0.2 fixture set could bias all four vector families per persona for a fuller demonstration — not required for M2's stated goal (prove the arithmetic is correct and deterministic), and not built here to avoid scope creep into content authoring.
- The differentiation threshold (`0.10`) and the minimum-scale-coverage floor for a vector's differentiation check (`80%`, mirroring Coverage's own floor) are both explicitly PROVISIONAL — see `app/services/basic_profile/config.py` for the exact constants and their source citations.
- As with M1, the full Alembic migration chain cannot be run end-to-end against SQLite in this sandbox (an unrelated, earlier, pre-existing migration uses a Postgres-only `ALTER COLUMN TYPE`); this migration's own `upgrade()`/`downgrade()` were verified in isolation instead (a standalone `MigrationContext`/`Operations` harness against a fresh SQLite connection with the M1 prerequisite tables stubbed in).
