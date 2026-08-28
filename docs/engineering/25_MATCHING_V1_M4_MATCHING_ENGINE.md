# 25. Matching V1 M4 — Deterministic User × Career Matching Engine

**Status:** IMPLEMENTED (Founder Review "M4 GO", 2026-08-28). Scope: `DeterministicProfile × CareerMatchingProfile → Interest Fit / Work Style Fit / Values Fit / Transition Feasibility / Match Coverage → deterministic ranking`. ZERO LLM TOKENS. No Career Catalog UI, no Compatibility Report frontend, no Route Builder (M5+). This document does not restate `docs/product/20_MATCHING_V1_FOUNDER_DEFINITION.md`.

---

## 1. New module map

| File | Purpose |
|---|---|
| `app/db/models_matching.py` | 3 tables + 3 enums, additive beside `DeterministicProfile`/`CareerMatchingProfile` |
| `app/services/matching/config.py` | `MatchingConfig` — every threshold/version, versioned and explicit |
| `app/services/matching/pure.py` | pure calculation — guarded cosine + Feasibility, zero DB imports |
| `app/services/matching/engine.py` | DB orchestration + persistence — fetch, convert, call `pure.py`, persist |
| `app/services/matching/ranking.py` | deterministic ranking over a set of results |
| `app/services/matching/queries.py` | `explain_matching_result` — structured explainability trace |
| `migrations/versions/d5f9b3a71c84_...py` | additive migration, 3 tables |

M1/M2/M3 (frozen) are unmodified. Stage 3A (`CareerRequirement`/`CareerSkill`/`CareerWorkContext`/`CareerFact`) is read-only here.

---

## 2. Persistence decision (audit result)

Stage 3B's `DirectionRun`/`Direction`/`DirectionScoreComponent` (`models_direction.py`) has an `OutputFamily` enum hardcoded to the OLD four outputs (`POTENTIAL_FIT`/`GOAL_ALIGNMENT`/`TRANSITION_FEASIBILITY`/`EVIDENCE_CONFIDENCE`). Reusing it for the new five-output Matching V1 model would force a reinterpretation of historical columns — explicitly forbidden (Founder Review §16). A wholly new, additive family (`MatchingResult`/`MatchFamilyResult`/`MatchFeasibilityResult`) was built instead, reusing only the *shape* of the existing `ScoreComponentStatus` convention (SCORED/INSUFFICIENT_DATA/NOT_APPLICABLE), extended with `LOW_DIFFERENTIATION`. Old and new coexist permanently; no migration touches Stage 3B data.

---

## 3. Calculation/persistence separation

`app/services/matching/pure.py` imports no SQLAlchemy — every formula (`guarded_cosine_fit`, `compute_feasibility`) operates on plain dataclasses and is independently unit-testable without a database (`tests/test_matching_pure_cosine.py`, `tests/test_matching_pure_feasibility.py`). `engine.py`'s job is strictly "fetch M2/M3/Stage-3A rows → convert to `pure.py`'s dataclasses → call the pure function → persist the result" — no formula logic lives there.

---

## 4. Interest Fit formula (RIASEC)

Full 6-dimensional vectors, both sides — no Top-3-code shortcut. `guarded_cosine_fit`:
1. If the career side has zero RIASEC components (UNMAPPED career), or the comparable intersection is below `MIN_COMPARABLE_COMPONENTS=2`: **INSUFFICIENT_DATA**.
2. Else compute population stdev of both sides' comparable values. If either falls below `DIFFERENTIATION_STDEV_THRESHOLD=0.10` (imported unchanged from `app/services/basic_profile/config.py`, never redeclared, so M2 and M4 can never drift apart on this constant): **LOW_DIFFERENTIATION**.
3. Else: **SCORED**, `raw_score = cosine_similarity(u, c)`, banded via the same HIGH≥0.70/MEDIUM≥0.40/LOW cutoffs as M2/Golden Test doc §23.

Since M2 always computes all-6-or-none for a user's RIASEC vector (Golden Test doc §9), the comparable-count guard rarely binds for Interest Fit specifically — it is the differentiation guard that does the real work here.

---

## 5. Guarded cosine — implementation

Pure function (`cosine_similarity` + the three-step gate above), deterministic (`test_interest_fit_deterministic` calls it 5 times on the same input, asserts byte-identical dataclass equality), no AI, no learned coefficient, no randomness. Every constant (`differentiation_stdev_threshold`, `min_comparable_components`, band cutoffs) comes from `MatchingConfig`, passed explicitly into every call — never a module-global read inside the function (`test_stdev_guard_configurable_versioned` swaps the threshold and observes the outcome change for identical inputs, proving it is not a hardcoded magic number). Persisted audit trail per family: `comparable_scale_keys` (which dimensions), `user_component_count`/`career_component_count`/`comparable_component_count`, `user_stdev`/`career_stdev`/`differentiation_threshold` — never a second copy of the raw vectors themselves (those remain reconstructable from `ProfileScaleResult`/`CareerMatchingComponent` via the parent `MatchingResult`'s `profile_id`/`career_matching_profile_id`).

---

## 6. Work Style Fit behavior

Compares ONLY the intersection of (a) the user's MATCH_ENABLED, sufficiently-answered Work Style scales (5 of M2's 10: `ambiguity_tolerance`, `leadership`, `initiative` — DIRECT; `structure_preference`, `collaboration` — DERIVED) and (b) whatever `CareerMatchingComponent` rows exist for that career. PROFILE_ONLY scales (`autonomy`, `pace`, `customer_interaction`, `decision_responsibility`, `routine_tolerance`) are excluded from the user side outright — never merely deprioritized (`test_work_style_compares_only_match_enabled`, `test_profile_only_excluded`). A career with zero Work Style components (23 of 24 Alpha careers — only `sales_manager` has any) gets an empty career-side dict, never a dict of fabricated zeros (`test_missing_career_work_style_not_zero`) and therefore **INSUFFICIENT_DATA** (`test_insufficient_work_style_data_result`).

---

## 7. Values Fit behavior

Identical mechanism to Work Style. **Locked regression** (`test_real_alpha_values_fit_insufficient_data`): the real Alpha dataset has zero Work Values `CareerMatchingComponent` rows for all 24 careers (M3's honest limitation) — Values Fit is **INSUFFICIENT_DATA for every single Alpha career, unconditionally**, until real O*NET Work Values data is imported. No provisional/fake Values component was created to make this family appear populated for M4.

---

## 8. Work Environment behavior

Never a public Fit output (Founder Review §7 — "do not create a fifth public Fit output"). No `MatchFamilyResult` row exists for `work_environment` at all (`test_environment_missing_not_treated_as_mismatch` confirms exactly 3 family rows per result: `riasec`/`work_style`/`work_values`, never a 4th). Since M3 also created zero career-side Work Environment components, this family currently contributes nothing anywhere in the pipeline — consistent, not a special case.

---

## 9. Transition Feasibility behavior

Deterministic gate-then-score, using only structured facts already present (M1's `ProfileStructuredContext` constraints + Stage 3A's `CareerRequirement`/`CareerSkill`/`CareerWorkContext`/M3's `onet_job_zone` `CareerFact`). Hard-gate invariant (binding, Founder Review §9): a hard barrier fires **only** for a `CareerRequirement` with `certainty="hard_factual"` in `{license, certification, legal_regulatory}` AND an explicit incompatible user answer. `typical_recommendation` never blocks (soft barrier only); `unknown` certainty is never even a soft barrier (`test_typical_recommendation_never_hard_blocks`, `test_unknown_certainty_never_a_barrier_or_gap`). A missing user answer is an information gap, never an assumed pass or fail.

**On the real Alpha data, no career is ever BLOCKED** — Stage 3A's existing seed contains zero `HARD_FACTUAL` `CareerRequirement` rows for any career (documented in that seed's own docstring). The BLOCK mechanism is fully implemented and tested (`test_hard_feasibility_requirement_can_block`, `test_blocked_career_excluded_from_eligible_ranking`) using a test-only synthetic requirement, not a claim that it fires in the current real dataset.

Soft penalties reuse, verbatim, the four factors already approved in `MNP_GOLDEN_TEST_V0.1.md` §22 (education-below-Job-Zone-typical ×0.85, work-format mismatch ×0.90, family-logistics-significant ×0.90, no-capacity-with-skills-gap ×0.80) — no fifth, undocumented penalty was introduced. License/language mismatches without a numeric penalty in that table are surfaced as qualitative soft barriers only, never as an invented multiplier. Required career skills with no shared user↔career skill taxonomy (M3's own honest limitation) are listed in `skills_to_verify` with status `UNKNOWN` — never inferred `CONFIRMED_MISSING` (`test_missing_user_skill_stays_unknown`); the `PRESENT`/`CONFIRMED_MISSING`/`UNKNOWN` vocabulary is preserved and reusable once a shared taxonomy exists (`test_confirmed_missing_skill_represented_correctly`).

---

## 10. Match Coverage behavior

Two genuinely distinct concepts, never conflated (`test_assessment_coverage_separate_from_match_coverage`): **Assessment Coverage** (M2, `DeterministicProfile.coverage`) measures how much of the *user's own test* was completed; **Match Coverage** (`MatchFamilyResult.coverage_ratio = comparable_component_count / user_component_count`) measures, per family per pairwise result, how much of what the user has could actually be compared against this specific career. No overall single percentage is invented across all families — per Founder Review §8 ("if methodology does not define a defensible overall percentage, do not invent one"), M4 reports family-level coverage only; `MatchingResult` itself carries no `coverage` field.

---

## 11. Ranking policy

No composite Match score anywhere (`test_no_composite_score_field`). Three explicit, never-interleaved groups (`RankingResult.ranked`/`unranked`/`blocked`):
- **blocked**: `Feasibility.status == "blocked"` — excluded from eligible ranking, always present in the full dataset, sorted by `Career.code`.
- **unranked**: eligible, but Interest Fit is not SCORED (INSUFFICIENT_DATA/LOW_DIFFERENTIATION) — sorted only by `Career.code`, since there is genuinely nothing comparable to rank by.
- **ranked**: eligible AND Interest Fit SCORED — sorted by the Golden Test doc §24-25 tuple: `(Interest band, Interest raw, Work Style band+score WHEN SCORED else neutral, Values band+score WHEN SCORED else neutral, Feasibility raw score, Goals domain-match tie-break, Career.code)`. A family that is not SCORED contributes an identical neutral value at its own tier for every not-scored career — it can only ever be a *secondary* tie-break preference among careers already tied on Interest Fit, never a penalty on the primary criterion (`test_missing_family_not_treated_as_zero_in_ranking`).

Deterministic (`test_ranking_deterministic`), stable `Career.code` final tie-break (`test_stable_career_code_tie_break`).

---

## 12. Missing-data semantics — the binding rule

`INSUFFICIENT_DATA` and `LOW_DIFFERENTIATION` are never treated as, converted to, or displayed as a low score. `MatchFamilyResult.raw_score`/`.band` are `NULL` for both states — there is no code path that substitutes 0 or `LOW`. `Missing != low fit`. This is proven directly by the real Alpha run: `Interest Fit: HIGH`, `Work Style Fit: INSUFFICIENT_DATA`, `Values Fit: INSUFFICIENT_DATA` is the actual, expected shape of most Alpha results — not a bug to "fix" by fabricating data.

---

## 13. Explainability

`explain_matching_result` (`app/services/matching/queries.py`) returns, per family, the exact `comparable_scale_keys` list that participated, the counts, the stdevs, and the threshold used — and, for Feasibility, the exact `hard_barriers`/`soft_barriers`/`information_gaps`/`skills_to_verify` lists. No LLM prose — a structured trace only (`test_structured_explanation_references_real_components`).

---

## 14. Versioning

Every `MatchingResult` pins all 8 required fields (`assessment_version`, `profile_engine_version`, `matching_methodology_version`, `career_vector_version`, `career_source_version`, `matching_engine_version`, `metric_version`, `config_version`) at calculation time (`test_versions_pinned`). Immutable — a re-run with the same inputs and engine/config version returns the existing row (`test_historical_result_immutable`); a genuinely changed version produces a new row.

---

## 15. Zero-AI guarantee

Same two-layer approach as every prior Matching V1 slice: (a) AST-based static scan of `app/services/matching/` and `app/db/models_matching.py` for any `app.ai_gateway` import or `AIGateway`/etc. reference; (b) a behavioral guard — `AIGateway.call_tool` patched to raise, then a full profile matched against all 24 Alpha careers. Matching succeeds (`test_full_matching_run_makes_zero_ai_gateway_calls`).

---

## 16. Actual 24-career Alpha catalog results, all 5 M2 personas

Persona bias maps reused **unchanged** from `tests/test_basic_profile_personas.py` (M2) — never re-tuned after seeing the resulting rankings, per Founder Review §18. Output exactly as computed (`ranked` list, best-first):

**A. technical/investigative:** `it_support_specialist, civil_engineer, mechanical_engineer, truck_driver, software_developer, electrician, plumber, pharmacist, financial_analyst, accountant, logistics_coordinator, project_manager, video_editor, registered_nurse, sales_manager, call_center_operator, customer_service_representative, retail_sales_associate, operations_manager, graphic_designer, school_teacher, social_worker, corporate_trainer` (23 ranked; `community_outreach_coordinator` unranked — UNMAPPED).

**B. social/helping:** `corporate_trainer, call_center_operator, customer_service_representative, retail_sales_associate, operations_manager, school_teacher, registered_nurse, social_worker, sales_manager, logistics_coordinator, project_manager, accountant, pharmacist, financial_analyst, video_editor, software_developer, graphic_designer, mechanical_engineer, it_support_specialist, civil_engineer, truck_driver, electrician, plumber`.

**C. entrepreneurial/leadership:** `sales_manager, call_center_operator, customer_service_representative, retail_sales_associate, logistics_coordinator, operations_manager, project_manager, accountant, financial_analyst, corporate_trainer, pharmacist, registered_nurse, software_developer, graphic_designer, video_editor, truck_driver, electrician, plumber, mechanical_engineer, school_teacher, social_worker, it_support_specialist, civil_engineer`.

**D. artistic/creative:** `video_editor, school_teacher, social_worker, graphic_designer, pharmacist, software_developer, mechanical_engineer, financial_analyst, logistics_coordinator, project_manager, registered_nurse, corporate_trainer, accountant, call_center_operator, customer_service_representative, retail_sales_associate, it_support_specialist, civil_engineer, operations_manager, sales_manager, truck_driver, electrician, plumber`.

**E. flat/undifferentiated:** `ranked = []` — all 23 mapped careers correctly land in `unranked` with Interest Fit = `LOW_DIFFERENTIATION` (stdev = 0.0, never scored); `community_outreach_coordinator` also unranked, but via `INSUFFICIENT_DATA` (zero career-side RIASEC components, a stronger/earlier guard than differentiation). **Persona E never receives an apparently strong Interest Fit anywhere** — the exact protection Founder Review §19 required.

**Honest reading of these rankings (a sanity test, not validation):** Persona A's top results are heavily Realistic/Investigative-coded occupations (Holland codes containing R/I), consistent with its bias. Persona C correctly places `sales_manager` (Holland `EC`) first. Persona B and D's exact orderings are a direct, un-tuned consequence of cosine similarity applied to the specific bias values M2 chose (e.g., `corporate_trainer`'s Holland code `SEC` aligns numerically with persona B's S+E-heavy bias at least as strongly as `registered_nurse`'s `SCI` does) — reported as-is, not adjusted to match an intuitive expectation.

---

## 17. Known limitations

- Values Fit and Work Environment carry zero real data for the entire Alpha catalog (inherited from M3's honest limitation) — every Values Fit result today is INSUFFICIENT_DATA.
- Work Style has real data for exactly 1 of 24 careers (`sales_manager`).
- No career in the real Alpha data can currently be BLOCKED (zero HARD_FACTUAL requirements exist in the Stage 3A seed) — the mechanism is implemented and tested with synthetic data only.
- No shared user↔career skill taxonomy exists yet — every required-skill check is honestly `UNKNOWN`, never `CONFIRMED_MISSING`.
- Band cutoffs (0.70/0.40) remain PROVISIONAL/EXPERIMENTAL, unchanged from M0/M2 — never claimed calibrated here.
- Persona rankings (§16) are engineering sanity checks only, explicitly not psychometric validation.

## 18. Data gaps to fill before a real-user product pilot

1. **Work Values numeric career-side data** (all 24 careers) — requires a genuine O*NET bulk-file/API import (not page-by-page web fetch), the single largest gap.
2. **Work Environment numeric career-side data** (all 24 careers) — same import dependency.
3. **Work Style coverage beyond `sales_manager`** — the other 23 careers need at least their DIRECT/DERIVED-eligible scales populated.
4. **At least one real HARD_FACTUAL `CareerRequirement`** (e.g., an actual UA nursing/legal license citation) so the BLOCK path is exercised by real data, not only by a test fixture.
5. **A shared skill taxonomy between M1's `known_skills` options and Stage 3A's `CareerSkill`/`TaxonomyTerm`** — without this, `skills_to_verify` will remain permanently `UNKNOWN` for every user, indefinitely.
6. **Expansion beyond 24 careers** toward the eventual ~149-career catalog (Founder Review, M3 doc 24 §16).
