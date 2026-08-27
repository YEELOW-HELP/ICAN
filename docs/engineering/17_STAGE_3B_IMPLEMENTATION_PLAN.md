# Stage 3B: Direction Intelligence — Implementation Plan (Founder-approved methodology contract; Slice 1 not yet coded)

> **Status: PLAN ONLY. No Stage 3B code is written.** This document
> proposes *how* to build Direction Intelligence technically while
> preserving every approved product/methodology/Stage-2/Stage-3A contract.
> Founder review (this revision) resolved the methodology contract (§4A)
> and fixed one engineering conflict found in the prior revision (§7,
> Hard Constraint Gate). It does not itself start coding — see §18 for
> the controlled slice sequence, of which only Slice 1 is currently in
> scope to begin.
>
> Branch: `stage-3b-direction-intelligence-v1`, based on
> `product-system-v3.1` @ `ccf3013` (merge of PR #19, Stage 3A — migration
> head `7d3720363f8e`). Nothing here authorizes a merge — Founder-controlled
> merge only, per `docs/product/15_MIY_NAPRYAM_V1_IMPLEMENTATION_ROADMAP.md`.

---

## 0. Methodology contract status (resolved)

Per Founder decision, the inline MNP-HPM v0.1 / Evidence Standard v0.1 /
Career Fit Model v0.1 / Consultant Feedback v0.1 contract given directly
to this planning task **is binding for Stage 3B**. The canonical
`methodology_lab/{02_HUMAN_POTENTIAL_MODEL,03_EVIDENCE_STANDARD,`
`04_CAREER_FIT_MODEL,07_CONSULTANT_FEEDBACK,09_EVALUATIONS}/` documents
referenced by the original task do not yet exist in this repository
(a `methodology-lab-v0.1` branch exists remotely, developed in parallel)
— this plan does not wait for them. All twelve methodology decisions
this plan originally flagged as blocking (MDR-1…MDR-12) are now
Founder-resolved; see §4A for the resolution of each, and §4A's closing
note for what still awaits *content* (not a decision) before later
slices can fully execute.

**Canonical MNP-HPM v0.1 top-level dimensions (Founder-approved,
authoritative for Stage 3B):**

1. Interests
2. Strengths
3. Skills
4. Abilities & Learning Potential
5. Work Style
6. Work Environment
7. Values
8. Motivation
9. Experience
10. Goals
11. Constraints
12. Career Adaptability / Agency

Stage 2's existing `ProfileDimension` enum (11 values: `strength`,
`interest`, `value`, `motivation`, `skill`, `trait`, `work_preference`,
`constraint`, `goal`, `experience`, `contextual_factor`) is **not
migrated** — per Founder decision, Stage 2 code and its 333 green tests
stay untouched. Stage 3B reads existing `ProfileClaim` rows through a new
**versioned legacy→canonical dimension adapter** (§5.4) instead.

**Restated binding contract principles** (Founder decision, carried
forward from the original task and unchanged by this revision):
Fit ≠ Confidence; hard constraints are evaluated before Fit; missing
data is never treated as zero; confidence is deterministic; Fit is
deterministic; scoring weights are experimental/versioned/configurable
until Methodology validates them; no LLM ever produces a numeric
fit/confidence value; no LLM ever asserts an unsupported career fact;
synthetic golden fixtures are engineering tests, not scientific ground
truth (§16, MDR-12).

---

## 1. Current repository analysis

### 1.1 What exists (verified by reading the code, not the docs alone)

| Layer | Module | Relevant capability |
|---|---|---|
| Identity/Access | `app/db/models.py`, `models_access.py`, `app/services/identity.py`, `product_access.py`, `consent.py` | Canonical `identity_users`, `Entitlement`, `Consent`, admin RBAC (`admin_users`, `AdminRole` in `models.py`, `app/core/security.py`, `app/api/deps.py`). `AdminRole` values: `SUPER_ADMIN`, `ADMIN`, `MANAGER`, `CAREER_CONSULTANT`, `REVIEWER` — **note the exact spelling `CAREER_CONSULTANT`, not `CONSULTANT`** (fixed throughout this revision; see §8). |
| Assessment (Stage 1) | `app/db/models_assessment.py`, `app/services/assessment/*` | `InterviewSession` state machine `draft→active→paused→complete→processing→ready→failed` (`state_machine.py`), `Answer`, `InterviewMessage`, `QuestionSelection`, `CVUpload`, adaptive `next_question.py` with traceable `SelectionReason` (`missing`/`low_confidence`/`contradiction`). `ready`/`failed` are terminal with zero outgoing transitions (hardened, tested) — **Stage 3B never touches this state machine** (§9). |
| Evidence/Profile (Stage 2) | `app/db/models_profile.py`, `app/services/profile/*` | `Evidence` (source-referenced, idempotent), `PotentialProfile` (per-user versioned, one `is_current`, immutable history), `ProfileClaim` (dimension + `ClaimStatus` + deterministic `confidence`), `ProfileClaimEvidence` M2M. `compute_claim_confidence` is a pure function. `ClaimSynthesizer` = LLM grouping only; confidence/status decided afterward deterministically. Contradiction → `is_contradictory` → `CONTRADICTED`, both evidence rows retained, never averaged. `superseded_by_claim_id`/`correction_reason` exist as unused hooks for a future human-correction workflow. **No `Constraint.is_hard` entity exists** — confirmed by direct code inspection, not just docs (verified: no `class Constraint` anywhere in `app/db/`). |
| Career Knowledge (Stage 3A) | `app/db/models_knowledge.py`, `app/services/knowledge/*` | `KnowledgeBaseVersion` (`DRAFT→PUBLISHED→SUPERSEDED`, one `is_current`, immutable once published), `Career` (16-domain enum, 7 nullable intrinsic-task characteristics), `CareerWorkContext` (12 environment attributes, **no certainty/provenance grading at all** — curated structural data, same standing as `Career`'s own characteristics), `CareerSkill` (→ `skills` taxonomy term), `CareerRequirement` (`RequirementCertainty`: `HARD_FACTUAL` / `TYPICAL_RECOMMENDATION` / `UNKNOWN`; `RequirementCategory` incl. `license`/`legal_regulatory`/`physical_environmental`), `CareerRelation`, `CareerFact` (`is_market_sensitive` requires source+date), `KnowledgeSource`. **Read surface: `app/services/knowledge/retrieval.py` — the single intended query API for Stage 3B, deterministic, no AI call.** Every function defaults to current published version, honours an explicit `knowledge_base_version_id`. **Write-path contract (`docs/engineering/16_...md` §13): all KB mutation goes through `app/services/knowledge/*`; Stage 3B never writes to these tables at all — read-only consumer.** **Stage 3A seed: 0 `HARD_FACTUAL` `CareerRequirement` rows, 0 `CareerFact` rows** — directly relevant to §7's Hard Constraint Gate fix below. |
| Taxonomy (cross-cutting) | `app/db/models_profile.py` (`Taxonomy`/`TaxonomyVersion`/`TaxonomyTerm`), `app/services/profile/taxonomy.py`, `app/services/knowledge/skills.py` | Two taxonomies seeded: `potential_dimensions` v1 (~32 terms, "not final methodology"), `skills` (~36 terms). `TaxonomyTerm.parent_term_id` supports hierarchy (unused so far). `TaxonomyTerm.dimension` is an informational `ProfileDimension.value` string. |
| AI Gateway | `app/ai_gateway.py` | Single seam. `call_tool(task_name, prompt_version, model, system, messages, tools, tool_choice, max_tokens)` → `GatewayResult(tool_input, raw_content, trace: GatewayTrace)`. `GatewayTrace` carries trace_id, tokens, latency, cost, stop_reason. **No retry/fallback, no `AI_TRACE` persistence** — structured logs only, and **Stage 3B keeps it that way** (§3, Founder decision — see §15 R4). |
| Platform | `app/db/models_platform.py`, `app/services/audit.py` | `AuditLog` (append-only, `record_audit(...)`), `app/services/events.py` `emit_event(...)` (structured log, never raises, envelope v1). |
| Evals | `evals/golden/schema.json`, `evals/golden/v1/` | Case schema already has `target` enum incl. `scenario_generation` (folder reserved, empty), `acceptable_outputs`/`unacceptable_outputs`, `required_claims`/`forbidden_claims` (reserved), `expected_constraints`, `methodology_version`, `prompt_version`, `provenance` (`synthetic`/`consented-anonymized`), `status` (`draft`/`approved`/`retired`). **No eval runner exists** — pre-existing debt since Sprint 0, not introduced or resolved by Stage 3B. |

### 1.2 Delivery/quality conventions this plan must follow

- Modular monolith, strict domain boundaries (`app/services/<domain>/`),
  service layer only — **Stage 1/2/3A all shipped with no HTTP API router**
  (`app/api/` has only `admin` + `crm` legacy routers). Stage 3B follows
  the same pattern: a service surface first, an API/adapter later.
- Additive, FK-ordered Alembic migration; downgrade reverses exactly; no
  existing table altered. PostgreSQL CI (`tests/test_migrations_postgres.py`)
  and single-head check (`tests/test_migrations.py`) gate it automatically.
- Enums are for **stable architectural lists** only; methodology *content*
  is `TaxonomyTerm` rows / seed data / versioned config, never a Python
  enum (`ProfileDimension`/`CareerDomain` precedent). The 12 canonical
  dimensions (§0) are the one exception discussed explicitly in §5.4 —
  they are Founder-approved, fixed, and structural for V1, the same
  standing `ProfileDimension`/`CareerDomain` already have.
- Deterministic business logic is a **pure function**, unit-tested against
  invariants (`compute_claim_confidence` precedent).
- Confidence is **never** an LLM's self-reported number.
- Provenance stamped on every generated artifact via `trace_id` reference +
  input-state chain (database rule 7), not by duplicating taxonomy/model
  fields.
- No `logger.*` with user/answer/CV/claim text in `app/services/profile/*`
  or `app/services/knowledge/*` — Stage 3B keeps this.
- `emit_event` after commit, IDs/counts/enums only in properties.
- Definition of Done (`docs/engineering/07_DEFINITION_OF_DONE.md`) applies
  per unit of work.

---

## 2. Existing components we can reuse (no rebuild)

| Need in Stage 3B | Reuse directly |
|---|---|
| Read career knowledge | `app/services/knowledge/retrieval.py` in full — `find_careers`, `get_career_details`, `get_career_skills/requirements/relations/facts`, `get_sources_for_career`, `search_careers`, version-scoped lookups. |
| Read the person's profile | `app/services/profile/generation.py::get_current_profile` / `get_owned_profile` / `explain_claim`; `ProfileClaim` rows by `dimension` + `status` + `confidence`; `ProfileClaimEvidence` for grounding. |
| Deterministic confidence pattern | `compute_claim_confidence` — copy the *shape* (pure fn, thresholds as named module constants, returns value+status, `None` = "don't emit"). |
| Contradiction handling | `ProfileClaim.status == CONTRADICTED` + `is_contradictory` semantics already computed in Stage 2 — Stage 3B **consumes** these, does not recompute. |
| Versioned publish lifecycle | `KnowledgeBaseVersion` / `PotentialProfile` idiom — one incrementing version, one `is_current` via partial unique index, immutable history, `supersedes_id`. Apply verbatim to `DirectionRun`. |
| LLM calls | `app/ai_gateway.AIGateway.call_tool` — forced-tool structured output, trace captured. New `task_name`s + `prompt_version`s only. |
| Provenance chain | `Direction.profile_id`-style FK to `PotentialProfile` + `knowledge_base_version_id` + `trace_id` strings (database rule 7) — **no new `AI_TRACE` table** (§3, §15 R4). |
| Audit | `app/services/audit.record_audit` for every consultant review action. |
| Events | `app/services/events.emit_event` with new event names. |
| Eval structure | `evals/golden/schema.json` + `v1/scenario_generation/` folder — extend, don't replace. |
| RBAC for the review console | `app/core/security.py` + `app/api/deps.py` + `AdminRole` (incl. `CAREER_CONSULTANT`) — same pattern as `app/api/crm.py`'s RBAC. |

---

## 3. Gaps (what Stage 3B must add)

### 3.1 Engineering gaps (this plan fills these)

| # | Gap | Fill |
|---|---|---|
| G1 | No Direction Intelligence domain at all — no tables, no service. | New bounded module `app/services/direction/` + `app/db/models_direction.py`, using `Direction*` naming (§5, Founder decision — supersedes ERD `SCENARIO` terminology for this V1 slice). |
| G2 | No hard-constraint representation on the user side. `CONSTRAINT.is_hard` (ERD, `01_SYSTEM_ARCHITECTURE.md` §8, database rule 9) was **never implemented** — Stage 2 folded constraints into `ProfileClaim(dimension=constraint)` with **no hardness flag and no structured value**. | New `ProfileConstraint` projection table (§5.3) built deterministically from constraint-dimension claims. |
| G3 | No shared vocabulary linking a user constraint to a `CareerRequirement`/`CareerWorkContext` attribute. | A `constraint_vocabulary` taxonomy (schema in this plan; **terms are methodology content**, delivered as data later — see §4A MDR-7/MDR-3 closing note). |
| G4 | No scoring-config persistence/versioning. Weights are explicitly **not approved**. | `ScoringConfig` table + `app/services/direction/config.py` with clearly-labelled `EXPERIMENTAL_NON_PRODUCTION` defaults, referenced by every `DirectionRun`. |
| G5 | No critic/verification layer anywhere in the codebase. | `app/services/direction/critic.py` — deterministic checks first (§4A MDR-9), optional LLM semantic critic, run **after** generation as a separate stage. |
| G6 | No consultant-review workflow beyond the unused `ProfileClaim` hooks. | `app/db/models_review.py` — `DirectionReview` state machine + `ConsultantCorrection` (append-only, original preserved; regeneration always creates a new `DirectionRun`, §8). |
| G7 | No eval runner; `scenario_generation` golden folder empty; schema lacks direction-specific expected fields. | Extend `evals/golden/schema.json`; author synthetic cases (MDR-12: engineering-only, not ground truth); a minimal offline runner is **out of Stage 3B scope** unless Founder adds it. |
| G8 | No dimension bridge between Stage 2's 11-value `ProfileDimension` and the 12 canonical MNP-HPM dimensions (§0). | `app/services/direction/dimension_adapter.py` — versioned legacy→canonical mapping (§5.4). Founder decision: do not migrate Stage 2. |
| G9 | No async job queue (`01_SYSTEM_ARCHITECTURE.md` §6 says scenario generation "must be queued"). | Stage 3B ships **synchronous generation with a per-user in-progress guard** (Stage 2 `ProfileGenerationInProgressError` precedent); orchestrator written to be queue-movable without a rewrite (Founder decision, §10 — acceptable for pilot, no queue infrastructure built). |

**Removed from this revision:** the previous draft's G8 ("`AI_TRACE` still not persisted") is **no longer a gap Stage 3B fills**. Founder decision (§3 of the review): do not persist `AI_TRACE` in Stage 3B core. See §15 R4 and the technical-debt note in §17.

### 3.2 Methodology decisions — resolved, not gaps

The previous revision listed twelve methodology gaps (MDR-1…MDR-12) as
blocking. **All twelve now have a Founder-approved resolution** — see
§4A. A handful of resolutions fix the *rule/mechanism* while leaving
*content* (specific subdimension terms, the correction reason-code list)
to arrive later as versioned data, exactly like Stage 2's taxonomy and
Stage 3A's skills seed — this does not block Slice 1 (§18), which builds
the mechanism, not the final content.

---

## 4. Proposed architecture

### 4.1 Module layout

```
app/services/direction/                 NEW bounded context — "Direction Intelligence"
  __init__.py
  dimension_adapter.py  CanonicalDimension enum (12) + versioned legacy ProfileDimension mapping
  pipeline.py        orchestrator: generate_directions(profile_id) -> DirectionRun
  candidates.py      candidate career selection over knowledge.retrieval (deterministic
                     filter; OPTIONAL llm re-rank AMONG KB CANDIDATES ONLY)
  constraints.py     Hard Constraint Gate — deterministic, runs BEFORE fit (§7: fixed rule)
  fit/
    __init__.py
    components.py     FitComponent protocol + registry
    interests.py, strengths.py, skills.py, ...   one scorer per methodology component
    aggregate.py      weighted aggregation (config-driven), missing-data handling
  confidence.py      deterministic direction-confidence fn (evidence + KB coverage)
  ranking.py         ordering + MAIN/ALTERNATIVE split + de-duplication + diversity flag
  critic.py          verification layer — deterministic checks (MDR-9) + optional LLM critic
  narrative.py       LLM "why this direction" generation (schema-validated, no new facts)
  config.py          ScoringConfig loader; EXPERIMENTAL_NON_PRODUCTION defaults
  explain.py         read surface: explain_direction(direction_id) -> full provenance bundle

app/services/review/                    NEW — consultant review integration
  __init__.py
  direction_review.py  DirectionReview state machine (server-side, like assessment SM)
  corrections.py       record_correction(...) — append-only, original preserved

app/db/models_direction.py              NEW tables (§5) -- Direction* naming, no AITrace table
app/db/models_review.py                 NEW tables (§5)

migrations/versions/<rev>_stage_3b_direction_intelligence.py   ONE additive migration
```

### 4.2 Pipeline (preserves the mandated processing order)

```
get_current_profile(user)                         [reuse Stage 2]
        │
        ▼
LEGACY→CANONICAL DIMENSION ADAPTER    dimension_adapter.py  (read-only view over
        │                             ProfileClaim.dimension -- Stage 2 untouched)
        ▼
MINIMUM-INPUT GATE (MDR-8, resolved)   is_current/READY profile AND
        │                             >=4 SUPPORTED claims AND >=3 canonical dimensions
        ▼ (below threshold)
        └──► DirectionRun(status=INSUFFICIENT_INFORMATION) + ClarificationRequest[]
        ▼ (meets threshold)
candidate career selection            candidates.py   (deterministic filter over
        │                             knowledge.retrieval; KB version pinned)
        ▼
HARD CONSTRAINT GATE                   constraints.py  (per candidate, BEFORE fit --
        │                             a BLOCKED career can never be MAIN/ALTERNATIVE.
        │                             BLOCK requires: user constraint hard+confirmed
        │                             AND CareerRequirement.certainty==HARD_FACTUAL
        │                             with a source. TYPICAL_RECOMMENDATION/UNKNOWN/
        │                             CareerWorkContext-sourced conflicts NEVER block --
        │                             soft risk/gap/trade-off/confidence-reduction/
        │                             review-warning signal only. See §7 for the full
        │                             rule and §16 for the required tests.)
        ▼   (surviving candidates)
FIT COMPONENTS  (per candidate)        fit/*.py        (each: 0..1 sub-score OR
        │                             "insufficient_evidence"; unknown ≠ 0, MDR-5/6)
        ▼
FIT AGGREGATION                        fit/aggregate.py (ScoringConfig weights,
        │                             versioned; weighted mean over AVAILABLE
        │                             components only, MDR-6)
        ▼
DIRECTION CONFIDENCE  (separate!)      confidence.py    (evidence sufficiency + KB
        │                             coverage + contradiction load -- NOT fit;
        │                             internal raw 0..1 EXPERIMENTAL, client-facing
        │                             band is LOW/MEDIUM/HIGH only, MDR-4)
        ▼
CRITIC / VERIFICATION                  critic.py        (deterministic first, MDR-9;
        │                             blocks invalid directions from proceeding)
        ▼
RANKING + MAIN/ALTERNATIVE + DIVERSITY ranking.py       (split rule = MDR-10;
        │                             de-dup near-identical/exact-duplicate careers;
        │                             never pads to six -- §5's material-differentiation rule)
        ▼
NARRATIVE  ("why this direction")      narrative.py     (LLM, schema-valid, cites
        │                             claims + KB facts already computed; adds nothing)
        ▼
DirectionRun(status=READY)  + Direction[] + FitComponent[] + ConstraintCheck[]
        + CriticFinding[]  + full provenance stamp
        │
        ▼
CONSULTANT REVIEW  (mandatory gate)    app/services/review/*  — nothing reaches a
                                       report/user without an APPROVED DirectionReview
```

**FIT ≠ CONFIDENCE is structural**, not a naming convention: `fit_score`
and `confidence` are computed by two different modules (`fit/` vs
`confidence.py`), from two different input sets, and stored in two
different columns. A direction can be `fit_score=0.92, confidence=0.41`
or the reverse. No code path multiplies them into a single number before
ranking without both being independently visible and persisted.

### 4.3 LLM vs deterministic split

| Responsibility | Owner | Rationale |
|---|---|---|
| Candidate career *filtering* (domain / characteristic thresholds / constraint pre-filter) | **Deterministic** | Reproducible; no invented careers. |
| Candidate career *re-ranking among KB rows* (optional, only if the deterministic shortlist is too broad) | LLM via Gateway, **inputs = KB rows only**, output = ordering of provided `career_id`s | Never introduces a career not in the KB; output validated against the input id set. |
| Hard constraint gate | **Deterministic** | Non-negotiable; an LLM must never decide whether a confirmed hard constraint is violated, and neither may an under-sourced `CareerRequirement` (§7). |
| Every fit sub-score | **Deterministic** given methodology scoring rules (MDR-5) | Auditable, testable against invariants. |
| Fit aggregation, weights | **Deterministic**, versioned config | Weights are methodology, not model output. |
| Direction confidence | **Deterministic** pure fn | "LLM-generated confidence can NEVER be the authoritative final confidence" (§0/MDR-4). |
| Ranking / split / de-dup / diversity flag | **Deterministic** | Reproducible; never a secret fit-score adjustment for diversity (§5). |
| Critic — structural checks (constraint re-check, provenance present, claim/fact references resolve, score↔explanation numeric consistency, duplicate detection) | **Deterministic** | These are invariants (MDR-9). |
| Critic — semantic checks (does the narrative assert something not in the structured inputs? tone/diagnosis/guarantee language?) | LLM via Gateway, **read-only, advisory**, findings persisted, cannot silently pass a direction the deterministic checks failed | Semantic judgement genuinely needs a model; it never *overrides* a deterministic failure. |
| "Why this direction" narrative | LLM via Gateway, structured input = already-computed claims + fit components + KB facts; **output adds no new fact** | The LLM may explain a recommendation; it may not create unsupported salary, admission, vacancy, or credential facts. |

---

## 5. Domain models

> All new tables: `native_enum=False` string-backed enums; UUID PKs;
> `created_at` server default. Direction Intelligence legitimately joins
> user profile + career knowledge, so it *does* reference
> `potential_profiles.id` and `identity_users.id` — it is the arrow that
> connects the two bounded domains. It still never copies raw answer/CV
> text, and it never writes to any Stage 3A `careers*` table (§1.1,
> write-path contract).

**Naming (Founder decision, §2 of the review):** this V1 slice uses
`Direction*` naming throughout — `DirectionRun`, `Direction`,
`DirectionFitComponent`, `DirectionConstraintCheck`,
`DirectionCriticFinding` — **not** the ERD's literal `SCENARIO`/
`SCENARIO_SCORE` terminology. The old ERD naming is superseded for this
V1 product slice; it is not forced merely to match the target ERD.
Compatibility is preserved through documentation only: `Direction`
*is* the ERD's `SCENARIO` concept (`scenario_type` was already a free
string, per `docs/product/14_...md` §11 — no ERD field-shape conflict,
only a table-name difference), `DirectionFitComponent` is `SCENARIO_SCORE`,
and a future `DirectionDecision` table (§8 of the original plan, not
required for Slice 1) is the ERD's `DIRECTION_DECISION`. No code should
introduce a parallel `Scenario` name anywhere.

### 5.1 `app/db/models_direction.py`

**`DirectionRun`** — one versioned generation attempt (the `PotentialProfile` idiom).
```
id, user_id (FK identity_users), profile_id (FK potential_profiles),
knowledge_base_version_id (FK knowledge_base_versions),
scoring_config_id (FK scoring_configs),
dimension_adapter_version (str, e.g. "dimension-adapter-v1" -- §5.4),
version (int, per-user), is_current (bool, partial-unique-index),
status: GENERATING | READY | FAILED | INSUFFICIENT_INFORMATION,
methodology_version (str, e.g. "mnp-hpm:v0.1"),
direction_engine_version (str, e.g. "direction-intelligence-v0.1"),
constraint_vocabulary_version_id (FK taxonomy_versions, nullable until MDR-7 content lands),
candidate_prompt_version, narrative_prompt_version, critic_prompt_version (str|null),
model (str), trace_ids (JSON list) -- structured-log-referencing strings only, no AITrace FK,
supersedes_id (FK self, null), failure_reason (str|null),
generated_at, created_at
```

**`Direction`** — one candidate career evaluated in a run.
```
id, run_id (FK), career_id (FK careers), career_code (str, denormalized for
  cross-KB-version stability), domain (str),
placement: MAIN | ALTERNATIVE | BLOCKED | REJECTED_BY_CRITIC | DEDUPED,
rank_within_placement (int|null),
fit_score (float|null -- null when blocked before fit),
fit_score_is_partial (bool -- some components were insufficient_evidence),
confidence (float),
confidence_band (str: high|medium|low -- deterministic mapping, no raw float to UI, MDR-4),
narrative_text (text|null), narrative_locale (str|null), narrative_trace_id (str|null),
created_at
```

**`DirectionFitComponent`** — per-component sub-score.
```
id, direction_id (FK), component_key (str -- one of the methodology Fit
  components, MDR-5), raw_score (float|null), weight_applied (float),
status: SCORED | INSUFFICIENT_EVIDENCE | NOT_APPLICABLE,
rationale (text -- deterministic, human-readable, e.g. "3 supporting claims,
  1 contradicted; career requires X at 'required' level"),
contributing_claim_ids (JSON list), contributing_career_attr (JSON --
  which career fields/skills/requirements were compared), created_at
```

**`DirectionConstraintCheck`** — Hard Constraint Gate result, one row per (direction, constraint). **This table's shape is the direct fix for the conflict found in the prior review** — see §7 for the full rule.
```
id, direction_id (FK), profile_constraint_id (FK profile_constraints),
constraint_vocab_key (str), career_attribute_ref (str -- requirement/work-context field),
matched_via: CAREER_REQUIREMENT | CAREER_WORK_CONTEXT,
career_requirement_certainty (str|null -- copied from CareerRequirement.certainty
  at check time; null when matched_via=CAREER_WORK_CONTEXT, since CareerWorkContext
  carries no certainty grading at all),
result: PASS | BLOCK | INSUFFICIENT_DATA | SOFT_SIGNAL,
is_hard (bool -- copied from ProfileConstraint at check time),
is_confirmed (bool -- copied from ProfileConstraint at check time),
explanation (text, deterministic), created_at
```
> **Binding rule (Founder decision, §1 of the review):**
> `result=BLOCK` **and** `Direction.placement=BLOCKED` may only occur when
> **all** of: `is_hard=true`, `is_confirmed=true`, `matched_via=CAREER_REQUIREMENT`,
> **and** `career_requirement_certainty=HARD_FACTUAL` (with the underlying
> `CareerRequirement.source_id` populated -- already guaranteed by Stage
> 3A's own service-layer enforcement, so this is a read-only invariant
> here, not a new provenance check to reimplement). Every other case --
> `TYPICAL_RECOMMENDATION` or `UNKNOWN` certainty, `matched_via=CAREER_WORK_CONTEXT`
> (no certainty concept exists for it at all), or `is_confirmed=false` --
> produces `result=SOFT_SIGNAL` (or `INSUFFICIENT_DATA` when the career
> attribute itself is unknown/null) and **never** `BLOCK`. A `SOFT_SIGNAL`
> row feeds a fit penalty, a `DirectionExplanation` risk/gap note, a
> confidence reduction, and/or a `DirectionCriticFinding(WARNING)` --
> never an irrevocable placement change. This also means: **for V1, a
> `CareerWorkContext`-sourced conflict can never block a direction**,
> since `CareerWorkContext` has no certainty/provenance grading in Stage
> 3A's schema at all and therefore cannot meet the "authoritative" bar
> the Founder decision defines specifically in terms of
> `CareerRequirement.certainty`. This is a deliberate, conservative
> default for V1, not an oversight -- see §7 for why, and §16 for the
> required tests proving it.

**`DirectionCriticFinding`** — verification output.
```
id, run_id (FK), direction_id (FK|null -- null = run-level finding),
check_key (str: hard_constraint_violation | unsupported_claim_reference |
  unsupported_career_fact | narrative_asserts_new_fact | explanation_score_mismatch |
  ranking_anomaly | near_duplicate | exact_duplicate | insufficient_diversity |
  missing_provenance | forbidden_language | nonexistent_or_unpublished_career |
  invented_evidence_or_source),
severity: BLOCKER | WARNING | INFO,
detector: DETERMINISTIC | LLM,
detail (text), evidence (JSON), created_at
```
> Any `severity=BLOCKER` on a direction ⇒ that direction cannot be
> `MAIN`/`ALTERNATIVE` (moves to `REJECTED_BY_CRITIC`). A run with a
> run-level BLOCKER cannot reach `READY`. BLOCKER/WARNING classification
> is fixed by MDR-9 (§4A) -- see that entry for the exact list.

**`ClarificationRequest`** — produced when the run is `INSUFFICIENT_INFORMATION` or a critical contradiction is unresolved.
```
id, run_id (FK), reason: MISSING_DIMENSION | LOW_CONFIDENCE_COVERAGE |
  UNRESOLVED_CONTRADICTION | CONSTRAINT_UNCONFIRMED,
dimension (str|null -- a canonical MNP-HPM dimension, §0), related_claim_ids (JSON),
suggested_question_topic (text),
status: OPEN | ADDRESSED | DISMISSED, created_at
```
> Stage 3B **emits** these only. Founder decision (§9 of the review):
> Stage 3B does **not** reopen or redesign Stage 1's `InterviewSession`
> state machine to wire these back into a new question round -- that is
> explicitly deferred to a separate, future plan.

**`ScoringConfig`** — versioned weights + thresholds (never edited once referenced).
```
id, version (int, unique), label (str), status: DRAFT | ACTIVE | SUPERSEDED,
is_experimental (bool -- TRUE for every V1 config until Methodology signs
  off real weights), component_weights (JSON: {component_key: weight}),
thresholds (JSON: min_supported_claims=4, min_canonical_dimensions=3
  (MDR-8), main_count=3, alternative_count=3 (MDR-10), dedup_similarity,
  confidence_bands),
notes (text), created_at
```

### 5.2 `app/db/models_review.py`

**`DirectionReview`** — the mandatory human-review gate (server-side state machine).
```
id, run_id (FK direction_runs), reviewer_admin_id (FK admin_users|null until claimed),
status: PENDING | IN_REVIEW | CHANGES_REQUESTED | APPROVED | REJECTED,
assigned_at, decided_at, decision_note (text|null),
methodology_version, knowledge_base_version_id, scoring_config_id,   (copied at creation)
created_at, updated_at
```
State table (server-enforced, no handler mutates `status` directly — assessment SM precedent):
```
PENDING        -> IN_REVIEW (claim)
IN_REVIEW      -> CHANGES_REQUESTED | APPROVED | REJECTED
CHANGES_REQUESTED -> IN_REVIEW           (only after a NEW DirectionRun is generated;
                                          the old run and this review row are never
                                          edited -- the new run gets its own new
                                          DirectionReview row, PENDING -- Founder
                                          decision, §8 of the review)
APPROVED / REJECTED = terminal
```
> **A `DirectionRun` may only be surfaced to a report/user when a
> `DirectionReview` with `status=APPROVED` exists for it.** Enforced in
> the read surface, not by convention. **`request_changes`/regeneration
> never overwrites `DirectionRun` or `DirectionReview` — it always
> produces a new, independently versioned `DirectionRun` (§8).**

**`ConsultantCorrection`** — append-only; original always preserved.
```
id, review_id (FK), run_id (FK), target_type: DIRECTION | FIT_COMPONENT |
  CONSTRAINT_CHECK | NARRATIVE | RANKING,
target_id (uuid), field (str),
original_value (JSON), corrected_value (JSON),
reason_code (str -- MDR-11 approved taxonomy, delivered as data), reason_note (text),
reviewer_admin_id (FK), methodology_version, knowledge_base_version_id,
scoring_config_id, model, prompt_version, created_at
```
> Never UPDATEs a `Direction*` row. A correction is a new row; the
> read/report surface applies approved corrections as an overlay and
> always keeps the AI original addressable. Corrections **do not** change
> methodology or config — they feed the structured feedback dataset for a
> later, separate, human-approved methodology-release process.

### 5.3 `ProfileConstraint` (projection) — lives in `app/db/models_direction.py`

Deterministically derived from `ProfileClaim(dimension=constraint)` of the
`is_current` profile, at `DirectionRun` generation time (Stage 2 untouched —
see §17 point 5 for the deferred "materialize during profile generation"
alternative).
```
id, profile_id (FK potential_profiles), source_claim_id (FK profile_claims),
constraint_vocab_key (str -- constraint_vocabulary taxonomy term, MDR-7 vocabulary,
  delivered as data),
normalized_value (str -- e.g. "no_night_shift", "max_travel=occasional",
  "location_locked=Lviv"),
is_hard (bool -- promotion rule below),
is_confirmed (bool -- a hard constraint must be *confirmed*, not merely
  mentioned once; drives BLOCK-eligibility vs INSUFFICIENT_DATA/SOFT_SIGNAL),
confidence (float -- copied from the source claim),
created_at
```
**Hardness/confirmation promotion rule (engineering default, pending
Methodology's final `constraint_vocabulary` content):** a constraint-
dimension `ProfileClaim` is projected with `is_hard=true` only when its
`constraint_vocab_key` is in a Methodology-curated hard-constraint list
(delivered as `constraint_vocabulary` `TaxonomyTerm` metadata, not
invented here), and `is_confirmed=true` only when `ClaimStatus==SUPPORTED`
(never `HYPOTHESIS`/`CONTRADICTED`/`INSUFFICIENT_EVIDENCE`) — mirroring
the same "don't treat a weak signal as settled fact" discipline Stage 2
already applies elsewhere. Until the vocabulary ships, every projected
constraint defaults to `is_hard=false`, which — combined with §7's rule —
means the Hard Constraint Gate produces zero `BLOCK` results until real
vocabulary content exists, by construction, not by accident.

### 5.4 `app/services/direction/dimension_adapter.py` — legacy→canonical dimension mapping

**`CanonicalDimension`** (new enum, 12 values, §0) is the dimension
vocabulary `fit/`, `constraints.py`, and `ClarificationRequest` use.
Stage 2's `ProfileClaim.dimension` stays `ProfileDimension` (11 values) —
**not migrated** (Founder decision, §6 of the review). A versioned,
explicit mapping bridges the two for read purposes only:

```
LEGACY_TO_CANONICAL: dict[ProfileDimension, CanonicalDimension | None] = {
    STRENGTH: STRENGTHS,
    INTEREST: INTERESTS,
    SKILL: SKILLS,
    VALUE: VALUES,
    MOTIVATION: MOTIVATION,
    GOAL: GOALS,
    EXPERIENCE: EXPERIENCE,
    CONSTRAINT: CONSTRAINTS,
    WORK_PREFERENCE: WORK_STYLE,   # see gap note below
    TRAIT: None,                  # UNMAPPED -- flagged, not guessed
    CONTEXTUAL_FACTOR: None,      # UNMAPPED -- flagged, not guessed
}
DIMENSION_ADAPTER_VERSION = "dimension-adapter-v1"
```

**Explicit, flagged gaps (engineering may not invent a fix — MDR-3's
"engineering may not invent new constructs" applies directly here):**
- Legacy `WORK_PREFERENCE` maps to canonical `WORK_STYLE` by default;
  canonical `WORK_ENVIRONMENT` has **no legacy source at all** until
  Stage 2's evidence/claim pipeline is extended (out of Stage 3B scope).
  Every `WORK_ENVIRONMENT` fit component resolves to
  `INSUFFICIENT_EVIDENCE` for every candidate in v0.1, never a guessed
  score.
- Legacy `TRAIT` and `CONTEXTUAL_FACTOR` are **unmapped** — claims under
  these dimensions are invisible to Stage 3B's Fit components entirely
  in v0.1 (they remain fully intact and queryable in Stage 2, untouched).
- Canonical `ABILITIES_AND_LEARNING_POTENTIAL` and
  `CAREER_ADAPTABILITY_AGENCY` have **zero legacy claims to draw from** —
  both dimensions' Fit components resolve to `NOT_APPLICABLE` for every
  candidate in v0.1 until a future Stage extends evidence extraction to
  cover them.
- `DIMENSION_ADAPTER_VERSION` is stamped on every `DirectionRun` (§5.1)
  so a future adapter revision (e.g. once Stage 2 is extended) never
  silently changes the interpretation of an already-generated,
  already-reviewed run.

---

## 6. Database changes

**One migration**, `stage_3b_direction_intelligence`, revising
`7d3720363f8e` (Stage 3A head). Additive only. Creates:
`scoring_configs`, `direction_runs`, `directions`, `direction_fit_components`,
`direction_constraint_checks`, `direction_critic_findings`,
`clarification_requests`, `profile_constraints`, `direction_reviews`,
`consultant_corrections`.

**No `ai_traces` table** (Founder decision, §3 of the review — reversed
from the prior revision's R4 recommendation; see §15 and the
technical-debt note in §17).

Constraints/indexes:
- `uq_direction_run_user_version` `UNIQUE(user_id, version)`.
- `uq_one_current_direction_run_per_user` partial unique index
  `WHERE is_current = true` (Postgres) / `= 1` (SQLite) — the Stage 2/3A
  idiom.
- `uq_scoring_config_version` `UNIQUE(version)`.
- `uq_direction_run_career` `UNIQUE(run_id, career_code)` — one evaluation
  per career per run.
- `uq_fit_component` `UNIQUE(direction_id, component_key)`.
- `uq_one_review_per_run` `UNIQUE(run_id)` (one review lifecycle per run;
  regeneration = new run = new review row, never a reused one).
- FK indexes on every `*_id`.

No existing table altered. `taxonomy_terms` gains new rows only (new
`constraint_vocabulary` taxonomy via an idempotent
`ensure_constraint_vocabulary()` seeder, `ensure_seed_taxonomy` precedent)
— **contents pending Methodology delivery** (§4A MDR-7 closing note);
the seeder ships with zero or placeholder terms, never invented content.

Seeding: `app/services/direction/config.py::ensure_experimental_scoring_config()`
inserts one `ScoringConfig(version=1, is_experimental=True,
status=ACTIVE)` with clearly-labelled non-production defaults, idempotent.

Downgrade drops the new tables in FK-safe reverse order; removes the
seeded `constraint_vocabulary` taxonomy rows and the experimental config.

---

## 7. Hard Constraint Gate — full rule (Founder-fixed, binding)

This section is the direct resolution of the conflict the prior review
found against Stage 3A's own contract (`docs/engineering/16_...md` §6:
*"`CareerRequirement.certainty == TYPICAL_RECOMMENDATION` MUST NOT be
treated as an automatic hard blocking constraint... A future hard block
may rely only on requirement data that is sufficiently authoritative...
which, for a `CareerRequirement`, effectively means
`certainty == HARD_FACTUAL`."*).

`constraints.py::run_hard_constraint_gate(session, direction_candidates, profile_constraints) -> list[DirectionConstraintCheck]`

Pure/deterministic. For each candidate × each `ProfileConstraint`:

1. Resolve `constraint_vocab_key` to either a `CareerRequirement`
   (category in `license`/`legal_regulatory`/`physical_environmental`/
   `language`/...) or a `CareerWorkContext` attribute (`shift_work`,
   `travel_required`, `setting`, ...) via the (Methodology-delivered)
   vocabulary mapping.
2. **`BLOCK` — the only path to `Direction.placement=BLOCKED` — requires
   every one of:**
   - `ProfileConstraint.is_hard == true`
   - `ProfileConstraint.is_confirmed == true`
   - matched via a `CareerRequirement` (not `CareerWorkContext`)
   - that `CareerRequirement.certainty == HARD_FACTUAL`
   - the career attribute genuinely conflicts with the confirmed constraint.
3. **`SOFT_SIGNAL` (never `BLOCK`) whenever any of the above is not met**,
   specifically including:
   - the matched `CareerRequirement.certainty` is `TYPICAL_RECOMMENDATION`
     or `UNKNOWN` — regardless of how "hard" or "confirmed" the user's
     constraint is, an insufficiently-sourced career-side requirement can
     never irrevocably block a direction;
   - the match is via `CareerWorkContext` — this attribute type carries
     no certainty/provenance grading in Stage 3A's schema at all, so it
     structurally cannot meet the "authoritative" bar; this is a
     deliberate V1 default, revisit only if Methodology explicitly
     approves treating specific `CareerWorkContext` fields as
     block-eligible;
   - `ProfileConstraint.is_confirmed == false` — regardless of career-side
     certainty, an unconfirmed user constraint never blocks (matches
     `INSUFFICIENT_DATA` handling for the user side).
4. `INSUFFICIENT_DATA` when the career attribute itself is null/unknown
   (unknown ≠ violation — same "missing data is never zero" principle
   applied to the career side).
5. A `SOFT_SIGNAL` row is not discarded: it feeds (a) a fit-component
   penalty/risk note in `fit/aggregate.py`, (b) a
   `DirectionCriticFinding(WARNING, check_key="hard_constraint_soft_signal")`
   for consultant visibility, and (c) a risk entry in
   `explain_direction`'s bundle — it is never silently dropped, only
   never promoted to an irrevocable block.

**Practical consequence, stated explicitly:** because the Stage 3A seed
has zero `HARD_FACTUAL` `CareerRequirement` rows today, the Hard
Constraint Gate will produce **zero real `BLOCK` results against the
current seed**, by design — every conflict resolves to `SOFT_SIGNAL` or
`INSUFFICIENT_DATA`. This is the correct, honest behavior given the KB's
current content, not a mechanism failure (already noted as a known
limitation in §15 R3; the fix is curating real `HARD_FACTUAL` data in a
future KB version, not loosening this rule).

---

## 7A. Services / modules (behaviour detail)

> Restores and updates the module-behavior detail from the prior
> revision (dropped by mistake when §7 was rewritten to fix the Hard
> Constraint Gate rule — caught during this revision's end-to-end
> re-read). References to the Hard Constraint Gate now point to §7
> rather than duplicating it.

### `pipeline.py::generate_directions(session, *, user_id, profile_id=None, scoring_config_id=None, locale="uk")`
- Resolves the `is_current` profile (or the explicit `profile_id`), the
  current published `KnowledgeBaseVersion`, the `ACTIVE` `ScoringConfig`.
- **Concurrency guard**: at most one `DirectionRun(status=GENERATING)` per
  user (`DirectionGenerationInProgressError`) — Stage 2 `ProfileGenerationInProgressError` precedent.
- Creates `DirectionRun(status=GENERATING)`, stamps every version field
  (incl. `dimension_adapter_version`) and `trace_ids=[]` up front.
- **Minimum-input gate (MDR-8, resolved):** if the profile is not
  `is_current`/`READY`, or has fewer than 4 `SUPPORTED` claims, or those
  claims cover fewer than 3 distinct canonical dimensions (via the
  dimension adapter, §5.4) — finish as `INSUFFICIENT_INFORMATION` +
  `ClarificationRequest[]`, emit `direction_generation_insufficient_information`,
  return. No directions.
- Otherwise run the pipeline (§4.2), including the Hard Constraint Gate
  (§7). Wrap in try/except: any exception → `status=FAILED`,
  `failure_reason=type(exc).__name__` (never `str(exc)` — Stage 2 privacy
  precedent), emit `direction_generation_failed`, re-raise.
- On success: mark previous run not-current, set `is_current=True`, commit,
  emit `directions_generated` (run_id, version, main_count, alternative_count,
  blocked_count, soft_signal_count).

### `candidates.py`
- `select_candidates(session, profile, kb_version_id) -> list[Career]`.
- Deterministic first pass: `knowledge.retrieval.find_careers(...)` filtered
  by profile-derived signals (e.g. domain interest claims, characteristic
  bands from strengths/work-style claims). **Never excludes a career on a
  missing signal** (MDR-6: missing data is never treated as a negative
  signal). Returns a bounded shortlist (config cap, e.g. 25).
- Optional LLM re-rank: only if the shortlist exceeds the cap; input =
  the shortlisted `Career` rows (title, description, characteristics) +
  a profile digest; output validated to be a permutation of the input
  `career_id`s. If validation fails → keep deterministic order.

### `constraints.py`
See §7 for the full, binding Hard Constraint Gate rule
(`run_hard_constraint_gate`) — not repeated here.

### `fit/components.py`
```python
class FitComponent(Protocol):
    key: str
    def score(self, ctx: FitContext) -> FitComponentResult: ...
    # FitComponentResult: raw_score: float | None, status: SCORED|INSUFFICIENT_EVIDENCE|NOT_APPLICABLE, rationale: str, ...
```
- One module per methodology component (MDR-5: the final component list
  and per-component comparison logic are Methodology content, delivered
  later; Slice 1 builds this protocol + registry, not the final roster).
  Each scorer: pull the relevant `ProfileClaim`s (by canonical dimension,
  via the adapter, + `ClaimStatus`) and the relevant career attributes;
  produce a 0..1 `raw_score` **or** `INSUFFICIENT_EVIDENCE`/`NOT_APPLICABLE`
  (never `0.0` for "we don't know" — MDR-5/MDR-6). `CONTRADICTED` claims
  lower the score / flag a risk, never silently averaged.
- Registry is config-gated: only components enabled in the active
  `ScoringConfig` run.

### `fit/aggregate.py::aggregate(components, config) -> (fit_score | None, fit_score_is_partial: bool)`
- Weighted mean over **available** (`SCORED`) components only (MDR-6,
  resolved) — missing/`INSUFFICIENT_EVIDENCE`/`NOT_APPLICABLE` components
  are never treated as a zero; they reduce coverage and set
  `fit_score_is_partial=True`.
- If too few components are `SCORED` (config threshold) → `fit_score=None`,
  the direction is still shown but flagged "insufficient data to score
  fit", never ranked as MAIN.
- A `SOFT_SIGNAL`/`INSUFFICIENT_DATA` row from the Hard Constraint Gate
  (§7) may also feed a fit penalty here — a soft conflict lowers `fit_score`,
  it does not block placement.
- `is_experimental=True` config ⇒ every resulting `fit_score` is stamped
  and surfaced with an "experimental, not methodology-validated" marker
  through to the review console and report.

### `confidence.py::compute_direction_confidence(direction_ctx) -> (float, band)`
- Pure/deterministic. Inputs: supporting-claim `ClaimStatus` mix &
  count & source diversity for the components that drove the fit; KB
  coverage for this career (how many of the compared career attributes
  were actually curated vs null); unresolved-contradiction load;
  `CareerFact` freshness where market-sensitive facts were used.
- **Independent of `fit_score`.** Internal raw value is `EXPERIMENTAL`;
  coefficients/thresholds are conservative placeholders pending
  Methodology calibration (MDR-4, resolved as a rule, content pending).
- Returns a rounded float + a `high|medium|low` band; only the band goes
  to any user-facing surface (mirrors Stage 2's `confidence_bucket`).

### `critic.py::verify_run(session, run) -> list[DirectionCriticFinding]`
- Runs **after** the full run is assembled, as its own stage.
- Deterministic checks (MDR-9's BLOCKER list, always run): re-run the
  hard-constraint gate independently and assert no `BLOCKED` career sits
  in MAIN/ALTERNATIVE; every `contributing_claim_id` / `CareerFact` id
  resolves and belongs to the pinned versions; `fit_score` is numerically
  consistent with its components + weights (± epsilon); no two MAIN/
  ALTERNATIVE directions exceed `config.thresholds.dedup_similarity`;
  every MAIN/ALTERNATIVE has non-empty provenance (≥1 claim + the KB
  version); ranking monotonic w.r.t. MDR-10's split rule; no exact-duplicate
  career appears twice (§5, material differentiation).
- Optional LLM semantic critic: narrative vs structured inputs
  (does it assert a fact/number not present?), forbidden
  diagnosis/guarantee language. **Advisory** — a `WARNING`, never an
  override of a deterministic `PASS`, and never a way to pass a
  deterministic `BLOCKER`.
- BLOCKER/WARNING classification is fixed by MDR-9 (§4A); persistence
  shape is `DirectionCriticFinding` (§5.1).

### `narrative.py::write_direction_narrative(direction_ctx, locale) -> (text, trace_id)`
- LLM via Gateway, forced tool. System prompt (`prompt_version`
  `direction-narrative-v0.1`): explain using ONLY the provided claims, fit
  components, and KB facts; cite which; never introduce a
  salary/demand/credential/institution fact; never diagnose or guarantee;
  present `contradictory`/`low` items honestly; locale is a parameter
  (not baked Ukrainian, per `docs/product/14_...md` §19).
- Output schema-validated; on invalid/missing → direction keeps
  `narrative_text=None`, a `DirectionCriticFinding(INFO)` records it,
  generation does not crash.

### `explain.py::explain_direction(session, direction_id) -> DirectionExplanation`
`DirectionExplanation` (new dataclass, read-only bundle, no persistence
of its own — assembled on demand from already-persisted rows) — the
"why this direction?" bundle: supporting claims (+ their evidence via
`explain_claim`), career facts used (+ `get_sources_for_career`), every
fit component with rationale, every constraint check (incl. any
`SOFT_SIGNAL` rows, §7), gaps (`INSUFFICIENT_EVIDENCE`/`NOT_APPLICABLE`
components + `ClarificationRequest`s), risks (soft-constraint conflicts +
`CONTRADICTED` claims + stale facts), `confidence` band,
`methodology_version`, `dimension_adapter_version`,
`knowledge_base_version_id`, `scoring_config` (+ experimental flag),
`direction_engine_version`, `prompt_version`s, `model`, `trace_ids`, run
`generated_at`. Deterministic, no AI call.

### `app/services/review/direction_review.py`
- `create_review(run_id)` (auto on run READY), `claim_review`,
  `request_changes`, `approve`, `reject` — each a guarded state
  transition; `record_audit(...)` on every one; `emit_event`
  (`direction_review_*`). `request_changes` never mutates the run in
  place — see §14 for the full immutable-history rule (regeneration
  always creates a new `DirectionRun` + new `DirectionReview`).
- `get_approved_run(user_id)` — the **only** function a report builder
  calls; returns `None` if no APPROVED review exists.

### `app/services/review/corrections.py::record_correction(...)`
- Validates `target_id` belongs to the run; writes one append-only
  `ConsultantCorrection`; never mutates the target; `record_audit`;
  `emit_event('direction_correction_recorded', reason_code=...)`.

---

## 8. APIs

Consistent with Stage 1/2/3A: **no public HTTP router in Stage 3B itself.**
The service functions in §4.1/§this section are the surface. When an
admin/consultant console is built (Stage 3's review-console work, tracked
separately), it will add an `app/api/` router using the existing
`app/api/deps.py` RBAC (`AdminRole` — `CAREER_CONSULTANT`/`REVIEWER`/
`MANAGER`/`ADMIN`/`SUPER_ADMIN` — **exact codebase spelling, no parallel
`CONSULTANT` role invented**, §4 of the review), mirroring `app/api/crm.py`.
Target shapes (for when that lands):

```
POST /v1/me/directions/generate         -> DirectionRun summary (202-style; sync for pilot)
GET  /v1/me/directions                   -> current APPROVED run (404/409 if none approved)
GET  /v1/me/directions/{id}/explain       -> explain_direction bundle
POST /v1/me/direction                     -> DirectionDecision (user picks one MAIN direction)

# consultant console (admin RBAC -- AdminRole.CAREER_CONSULTANT et al.)
GET   /v1/admin/direction-reviews?status=pending
POST  /v1/admin/direction-reviews/{id}/claim
POST  /v1/admin/direction-reviews/{id}/request-changes
POST  /v1/admin/direction-reviews/{id}/approve
POST  /v1/admin/direction-reviews/{id}/reject
POST  /v1/admin/direction-runs/{id}/corrections
POST  /v1/admin/direction-runs/{id}/regenerate
```
`DirectionDecision` = the ERD's `DIRECTION_DECISION` (add a thin
`app/db` model when the picking flow is built; not required for Slice 1
or the generation+review core).

---

## 9. LLM responsibilities (exhaustive list for Stage 3B)

| `task_name` | `prompt_version` | Input | Output | Guardrail |
|---|---|---|---|---|
| `direction_candidate_rerank` (optional) | `direction-candidate-rerank-v0.1` | shortlisted `Career` rows + profile digest | ordering of the given `career_id`s | output must be a permutation of input ids or it is discarded |
| `direction_narrative` | `direction-narrative-v0.1` | one direction's computed claims + fit components + KB facts | `why_text`, `strengths_used[]`, `gaps[]`, `risks[]` | schema-validated; every referenced fact must exist in input; no new market/credential facts; no diagnosis/guarantee; locale param |
| `direction_semantic_critic` (advisory) | `direction-critic-v0.1` | narrative + the structured inputs it should be grounded in | `findings[]` (check_key, detail) | advisory only; cannot override deterministic result |

Everything else in the pipeline is deterministic. No LLM call decides:
a career's existence, a constraint violation, any numeric score, any
confidence value, the ranking, the MAIN/ALTERNATIVE split, or diversity.

---

## 10. Deterministic responsibilities (exhaustive)

Legacy→canonical dimension mapping · candidate filtering · minimum-input
gate · hard constraint gate · every fit sub-score · fit aggregation &
weights · direction confidence · ranking · MAIN/ALTERNATIVE split ·
exact/near-duplicate detection & diversity flagging · all structural
critic checks · clarification-request generation · provenance stamping ·
review state machine · correction recording · `explain_direction`. All
pure functions where possible, all unit-tested against methodology
invariants (§16).

---

## 11. Career KB interface

Stage 3B consumes `app/services/knowledge/retrieval.py` **only** — no new
SQL against `careers*` tables, no writes (write-path contract,
`docs/engineering/16_...md` §13). Functions used: `find_careers`,
`get_career_details`, `get_career`, `get_career_by_code`,
`get_career_skills`, `get_career_requirements`, `get_career_relations`,
`get_career_facts`, `get_sources_for_career`, `search_careers`,
`get_current_knowledge_version`.

Every `DirectionRun` pins `knowledge_base_version_id`; every retrieval call
inside a run passes that explicit id (not "current") so a re-run / audit
of an old run reads exactly the KB it used, even after a republish
(`test_retrieval_defaults_to_current_version_even_after_republish`
already proves this works).

**Known limitation** (§15 R3, unchanged): the Stage 3A seed has **0
`HARD_FACTUAL` requirements and 0 `CareerFact` rows**. Combined with §7's
fixed gate rule, this means the hard-constraint gate is mechanically
correct but produces no real `BLOCK` against current seed data — a KB
content gap, not an engine gap.

New external sources (O*NET/ESCO): `Career.external_esco_id/onet_id/isco_id`
columns already exist, unpopulated. Stage 3B does **no** external
ingestion. Any future mapping lands as new `KnowledgeSource` +
`CareerFact` rows in a new `DRAFT` KB version — no Stage 3B code change.

---

## 12. Scoring interface

- `ScoringConfig` row = the single source of weights + thresholds for a
  run. Immutable once any `DirectionRun` references it.
- `app/services/direction/config.py`:
  `get_active_scoring_config()`, `ensure_experimental_scoring_config()`,
  `create_scoring_config(...)` (draft), `activate_scoring_config(id)`
  (supersede-previous, one ACTIVE — the KB-version idiom).
- **`EXPERIMENTAL_NON_PRODUCTION` defaults** live in `config.py` as a
  named constant with a docstring stating they are engineering placeholders
  for pipeline validation, not methodology-approved weights, and must not
  be cited as such in any report. `is_experimental=True` propagates to
  `DirectionRun`, `Direction`, `explain_direction`, and the review console.
- Direction confidence's internal raw float is `EXPERIMENTAL`
  (MDR-4); only the deterministic `LOW`/`MEDIUM`/`HIGH` band ever reaches
  a client-facing surface (mirrors `confidence_bucket` in Stage 2's
  `app/services/profile/summary.py`).
- When Methodology delivers real weights: a new non-experimental
  `ScoringConfig` is created and activated; old runs keep their old
  config id and stay reproducible.

---

## 13. Critic / verification layer

Covered in §4.3, §5.1 (`DirectionCriticFinding`), and the Hard Constraint
Gate rule in §7. Key properties:
- **Separate stage, separate module** from generation — a run is fully
  assembled, *then* verified. Generation never calls the critic; the
  orchestrator does.
- Deterministic checks are invariants and produce `BLOCKER`s that
  demote a direction or fail a run (exact list: MDR-9, §4A).
- The LLM semantic critic is advisory (`WARNING`/`INFO`) and can never
  upgrade a deterministic `BLOCKER` to pass or downgrade a deterministic
  `PASS`.
- Every finding is persisted with `detector` (DETERMINISTIC/LLM) so a
  reviewer sees exactly what flagged what.
- Diversity/duplication checks (§5, material differentiation) are
  deterministic critic findings, same as every other structural check —
  never a hidden fit-score adjustment.

---

## 14. Consultant-review integration

- `DirectionReview` is created automatically when a `DirectionRun` reaches
  `READY` (status `PENDING`).
- **Hard gate**: `get_approved_run()` is the only path from Direction
  Intelligence to a report; it returns a run only if its `DirectionReview`
  is `APPROVED`. The future report builder must call it — enforced by
  making it the sole read entry point, and by a test asserting no other
  function returns a report-ready run.
- Consultant actions: `approve` / `reject` / `request_changes` (+ note) /
  `record_correction` (structured, append-only) / trigger `regenerate`.
- **`request_changes`/regeneration semantics (Founder decision, §8 of the
  review, binding):** consultant review must preserve immutable history.
  `request_changes` never edits `DirectionRun` or its `DirectionReview` in
  place. Regeneration always produces a brand-new `DirectionRun`
  (`version = previous + 1`, its own `is_current` handoff, same versioning
  idiom as Stage 2/3A) and a brand-new `DirectionReview` row
  (`status=PENDING`) for that new run. The previous `DirectionRun` and its
  `DirectionReview` (`status=CHANGES_REQUESTED`) are never overwritten and
  remain permanently queryable. `ConsultantCorrection` rows remain
  append-only regardless of this flow and are never a substitute for
  regeneration when methodology-affecting changes are needed — they
  overlay presentation-level corrections onto an existing run.
- Every action → `AuditLog` row (`record_audit`) + product event.
- Corrections **never** alter `ScoringConfig`, taxonomy, or methodology.
  They accumulate into the structured feedback dataset that a *later,
  separate, human-approved* methodology-release process consumes
  (MDR-11).

---

## 15. Versioning & reproducibility

Every `DirectionRun` records, at creation:
`methodology_version`, `dimension_adapter_version`,
`constraint_vocabulary_version_id`, `knowledge_base_version_id`,
`scoring_config_id`, `direction_engine_version`, `candidate_prompt_version`,
`narrative_prompt_version`, `critic_prompt_version`, `model`, `trace_ids[]`,
`profile_id` (→ profile version → claims → evidence → potential-taxonomy
versions, via the Stage 2 chain), `generated_at`.

Together these answer **"why did the system give this recommendation to
this person on this date?"** from the database, resolving `trace_ids`
against retained structured logs (no `AI_TRACE` table — §3, §17).

`ConsultantCorrection` and `DirectionReview` each also copy
`methodology_version` / `knowledge_base_version_id` / `scoring_config_id`
at creation, so a correction stays interpretable after configs move on.

**Decisions (resolved this revision unless noted):**

| id | Risk / decision | Status |
|---|---|---|
| R1 | Inline task text vs real `methodology_lab/` docs as the contract. | **Resolved (§0):** inline Founder contract is binding; canonical docs developed in parallel, not blocking. |
| R2 | Synchronous generation vs job queue. No queue exists. | **Resolved (§10 of the review):** synchronous acceptable for pilot; orchestrator written queue-movable; no queue infrastructure built for Stage 3B. |
| R3 | Hard-constraint gate & market-fact critic have near-empty KB data to act on. | **Unchanged, still open as a KB-content task:** accept for pilot (§7/§11); add a KB-curation task for real `HARD_FACTUAL` requirements before commercial launch; keep tests that prove the mechanism with fixtures. |
| R4 | `AI_TRACE` still not persisted — provenance is log-only. | **Resolved, reversed from the prior revision (§3 of the review): do NOT persist `AI_TRACE` in Stage 3B.** Keep existing trace_id-only/log-only behavior. A technical-debt note is added instead (§17). This remains a separate, dedicated architecture decision for later. |
| R5 | `Direction` vs. literal ERD `SCENARIO` naming. | **Resolved (§2 of the review): use `Direction*` naming**; `SCENARIO` terminology superseded for this V1 slice; mapping documented in §5, not code. |
| R6 | Contradiction/clarification → re-open assessment. Stage 1 `ready` is terminal. | **Resolved (§9 of the review):** Stage 3B only *emits* `ClarificationRequest`s; wiring them into a new Stage 1 question round is explicitly deferred, not designed here. |
| R7 | `request_changes` workflow: regenerate vs correction-overlay. | **Resolved (§8 of the review):** always regenerate (new `DirectionRun` + new `DirectionReview`); corrections are an append-only overlay, never a substitute for regeneration; never edits history. |
| R8 | Experimental weights leaking into a real pilot report as if validated. | **Ongoing engineering safeguard, not a one-time decision:** `is_experimental` flag propagated everywhere + explicit report marker + mandatory review, enforced at every layer that surfaces a `fit_score`. |

---

## 16. Tests (methodology invariants, not just execution)

New files: `tests/test_direction_dimension_adapter.py`,
`tests/test_direction_constraints.py`, `tests/test_direction_fit.py`,
`tests/test_direction_confidence.py`, `tests/test_direction_critic.py`,
`tests/test_direction_ranking.py`, `tests/test_direction_pipeline.py`,
`tests/test_direction_review.py`, `tests/test_direction_corrections.py`,
`tests/test_direction_versioning.py`, plus `evals/golden/v1/scenario_generation/`
cases and a `schema.json` extension.

Invariant coverage (each = an explicit assertion):

| Scenario | Asserted invariant |
|---|---|
| **hard constraint — HARD_FACTUAL, confirmed, hard** | `CareerRequirement.certainty=HARD_FACTUAL` + confirmed hard `ProfileConstraint` conflict → `DirectionConstraintCheck.result=BLOCK`, `Direction.placement=BLOCKED`, irrelevant of `fit_score`. |
| **hard constraint — TYPICAL_RECOMMENDATION never blocks** | Same confirmed hard constraint, but the matched `CareerRequirement.certainty=TYPICAL_RECOMMENDATION` → `result=SOFT_SIGNAL`, `Direction.placement` is **never** `BLOCKED` on this basis alone; a `DirectionCriticFinding(WARNING)` is produced instead. |
| **hard constraint — UNKNOWN never blocks** | Same, with `certainty=UNKNOWN` → `SOFT_SIGNAL`, never `BLOCK`. |
| **hard constraint — CareerWorkContext never blocks** | A conflict matched via `CareerWorkContext` (e.g. `shift_work`) never produces `BLOCK`, regardless of how hard/confirmed the user constraint is — `matched_via=CAREER_WORK_CONTEXT` is structurally ineligible for `BLOCK` in v0.1. |
| **hard constraint — unconfirmed never blocks** | `is_hard=true` but `is_confirmed=false` → never `BLOCK`, even against a `HARD_FACTUAL` requirement. |
| **hard constraint — unknown career attribute** | Career attribute null/unknown → `INSUFFICIENT_DATA`, never treated as a violation. |
| normal profile | 6 directions (3 MAIN + 3 ALTERNATIVE) when data supports it; every one has ≥1 supporting claim + KB version. |
| missing data | a dimension with no claims → affected fit components `INSUFFICIENT_EVIDENCE`, **not** `raw_score=0`; direction not auto-zeroed; confidence lowered. |
| dimension adapter — unmapped dimension | A `TRAIT`/`CONTEXTUAL_FACTOR` claim never silently appears in any canonical-dimension Fit component; `WORK_ENVIRONMENT` and the two legacy-sourceless canonical dimensions resolve to `INSUFFICIENT_EVIDENCE`/`NOT_APPLICABLE` for every candidate, never a guessed score. |
| minimum-input gate | Profile with <4 `SUPPORTED` claims or <3 canonical dimensions covered → `status=INSUFFICIENT_INFORMATION`, zero directions, `ClarificationRequest[]`, event emitted; a profile meeting both thresholds proceeds. |
| weak evidence | only `HYPOTHESIS`/`INSUFFICIENT_EVIDENCE` claims → direction confidence band `low`; not placed MAIN. |
| strong evidence | multiple `SUPPORTED` corroborating claims → higher confidence band; fit unaffected by confidence. |
| contradictory evidence | `CONTRADICTED` claim in a component → component flags risk, score not silently averaged; `ClarificationRequest` or critic `WARNING` produced. |
| **material differentiation — exact duplicate careers prevented** | The same `career_id` can never appear twice as separate `Direction` rows in one run (`uq_direction_run_career`); an exact-duplicate candidate collapses before ranking. |
| **material differentiation — near-duplicate flagged, not hidden** | Two near-identical directions (above `dedup_similarity`) → one is `DEDUPED` or both raise `DirectionCriticFinding(check_key=near_duplicate)`; fit scores of the surviving directions are **not** secretly altered to manufacture apparent diversity. |
| **material differentiation — never pads to six** | Fewer than 6 eligible (non-blocked, non-deduped) candidates exist → the run legitimately returns fewer than 6 directions rather than padding with a low-fit filler; a `DirectionCriticFinding(check_key=insufficient_diversity, severity=WARNING)` surfaces this for consultant review. |
| multiple competing careers | deterministic ranking is stable & reproducible for identical inputs (MDR-10 split rule: fit desc, confidence tie-break, first 3 MAIN, next 3 ALTERNATIVE, never padded). |
| high fit / low confidence | both values persisted independently; direction shown with an explicit "we don't know you well enough yet" note. |
| moderate fit / high confidence | same — independent fields, no collapsing. |
| unsupported career facts | narrative citing a fact not in KB input → critic `BLOCKER`; direction demoted. |
| consultant correction history | `ConsultantCorrection` never UPDATEs a `Direction*` row; original always retrievable; overlay applies only approved corrections; correction carries all version stamps. |
| **request_changes creates a new run, never edits the old one** | Calling `request_changes` then regenerating produces a `DirectionRun` with `version = old + 1` and a fresh `DirectionReview(status=PENDING)`; the old `DirectionRun` row and its `DirectionReview(status=CHANGES_REQUESTED)` are unchanged and independently queryable afterward. |
| insufficient information | below the cutoff → `status=INSUFFICIENT_INFORMATION`, zero directions, `ClarificationRequest[]`, event emitted. |
| reproducibility | a run re-executed against its pinned versions + a stubbed Gateway yields identical deterministic outputs (fit, constraint, confidence, ranking). |
| provenance | `explain_direction` returns non-empty claims + evidence + KB sources + all version fields for every MAIN/ALTERNATIVE direction. |
| bounded domain | `direction_*`/`review_*` tables reference `potential_profiles`/`careers`/`identity_users` only as designed; no raw answer/CV text stored anywhere in the new schema; zero writes to any `careers*` table (assertion tests, Stage 3A precedent). |
| **no AI_TRACE table exists** | Migration structural test confirms no `ai_traces` table is created (guards against silently reintroducing the reversed R4 decision). |

All Stage 1/2/3A tests must stay green (currently 334 passed / 2 skipped);
the migration is picked up automatically by the existing migration tests.

Golden fixtures are labelled `provenance.type: synthetic` and
`methodology_version` reflecting MNP-HPM v0.1 — they are **engineering
fixtures, not validated ground truth** (MDR-12: golden-case ground truth
requires a career expert/panel + Methodology Owner sign-off; synthetic
fixtures remain engineering-only until that happens).

---

## 17. Migration strategy

1. Branch `stage-3b-direction-intelligence-v1` off Stage 3A head (done —
   this plan revision itself lives on that branch, based on
   `product-system-v3.1` @ `ccf3013`).
2. One additive migration (`revises = "7d3720363f8e"`), FK-ordered,
   exact-reverse downgrade. No `ALTER` on any existing table. **No
   `ai_traces` table** (§3, §6).
3. `constraint_vocabulary` taxonomy + experimental `ScoringConfig` seeded
   by idempotent `ensure_*` service functions (not baked into the
   migration — `ensure_seed_taxonomy` / `ensure_seed_knowledge_base`
   precedent), so methodology content can evolve as data.
4. PostgreSQL CI (`tests/test_migrations_postgres.py`) + single-head +
   linked-chain checks gate the migration with no test-file changes.
5. `ProfileConstraint`: materialized at `DirectionRun` time by default
   (no change to Stage 2). **Open question, still deferred:** also
   populate it during `generate_potential_profile` so the profile
   carries structured constraints natively — would touch Stage 2 and
   needs its own separate review; not part of Stage 3B.
6. No data backfill required — no `DirectionRun` exists until the engine
   runs.
7. Rollback: the migration downgrade + feature is inert until
   `generate_directions` is called from an adapter; nothing in Stage 1/2/3A
   calls it.
8. **Technical-debt note to add** (`docs/engineering/11_TECHNICAL_DEBT_REGISTER.md`,
   per Founder decision §3 of the review): "`AI_TRACE` persistence
   remains deferred across Stage 1/2/3A/3B. `GatewayTrace` continues to be
   structured-logged only; `DirectionRun.trace_ids` references log entries
   by id, not a database row. A dedicated, separately-reviewed persistence
   design is needed before any stage relies on querying AI call history
   from the database rather than logs." This is documentation only — no
   schema change accompanies it in Stage 3B.

---

## 18. Implementation sequence (Slice 1 authorized to begin planning; still no code in this step)

Per Founder decision (§11 of the review), Stage 3B is split into
controlled slices. This step (updating this plan) does not itself start
Slice 1 — it prepares the ground for a future, separate "begin Slice 1"
authorization.

### Slice 1 (schema + deterministic gates + interfaces)
| Step | Work |
|---|---|
| 1 | Migration + `models_direction.py` + `models_review.py` + `ProfileConstraint`; `dimension_adapter.py`; `ensure_*` seeders (empty/placeholder `constraint_vocabulary` content); migration tests green. |
| 2 | `config.py` + `ScoringConfig` + experimental defaults (labelled), thresholds incl. `min_supported_claims=4`, `min_canonical_dimensions=3`, `main_count=3`, `alternative_count=3`. |
| 3 | `constraints.py` — Hard Constraint Gate implementing §7's exact rule; full test coverage per §16's hard-constraint rows. |
| 4 | Deterministic fit **interfaces** (`fit/components.py` protocol + registry, `fit/aggregate.py`'s missing-data handling) and confidence **interface** (`confidence.py`'s signature + band mapping) — concrete per-component scorers may be stubbed/minimal for Slice 1 (MDR-5 content, e.g. real subdimension terms, still arrives as data). |
| 5 | Full test suite for everything above; full regression pass (Stage 1/2/3A stay green). |

### Later slices (not this step, not yet authorized)
- Candidate generation (`candidates.py`) + ranking/diversity (`ranking.py`).
- Deterministic critic (`critic.py`) — full MDR-9 check list.
- Narrative/explanations (`narrative.py`, `explain.py`) — LLM integration.
- Pipeline orchestration (`pipeline.py`) tying every stage together.
- Consultant review backend (`app/services/review/*`).
- Golden evals (`evals/golden/v1/scenario_generation/`).

### Still explicitly NOT Stage 3B (any slice)
Route Builder, final Report assembly, PDF rendering, Dashboard UI, full
Client Card, the Admin/Consultant **UI** (backend review state machine
only). These are the rest of roadmap "Stage 3" and each needs its own
plan.

---

## 4A. Methodology decisions — Founder-resolved

> Status key: **RESOLVED (rule)** = the decision/framework is fixed and
> binding; engineering can build the mechanism now. **RESOLVED (rule);
> content pending** = the rule is fixed, but specific data/content
> (subdimension terms, a reason-code list, etc.) still arrives later as
> versioned data — exactly like Stage 2/3A's taxonomy seeds — and does
> not block Slice 1.

**MDR-1 — Canonical methodology documents. RESOLVED (rule).**
The inline Founder methodology contract (§0) is binding for Stage 3B.
Canonical `methodology_lab/*` documents are being developed in parallel
(a `methodology-lab-v0.1` branch exists) and are not a blocker — Stage 3B
proceeds on the contract as given.

**MDR-2 — Human Potential dimension set. RESOLVED (rule).**
The 12 canonical MNP-HPM v0.1 dimensions (§0) are authoritative. Stage
2's `ProfileDimension` (11 values) is **not migrated** now. A versioned
legacy→canonical adapter (§5.4) bridges the two, with explicit,
documented gaps (`WORK_ENVIRONMENT`, `TRAIT`, `CONTEXTUAL_FACTOR`,
`ABILITIES_AND_LEARNING_POTENTIAL`, `CAREER_ADAPTABILITY_AGENCY` have no
legacy source) rather than a guessed mapping.

**MDR-3 — Subdimension taxonomies. RESOLVED (rule); content pending.**
Subdimensions are config/versioned `TaxonomyTerm` content, delivered as
data (same mechanism as Stage 2's `potential_dimensions` and Stage 3A's
`skills` taxonomies). Engineering may not invent new subdimension
constructs to fill the gap — Slice 1 builds the mechanism (taxonomy
tables already exist from Stage 2) without needing the final term list;
`fit/` component scorers that need specific subdimension terms are a
later-slice concern once content lands.

**MDR-4 — Deterministic confidence function. RESOLVED (rule); content pending.**
Confidence is deterministic (unchanged principle). Internal raw value is
`0.0–1.0`, explicitly `EXPERIMENTAL` until Methodology calibrates
coefficients. Only the derived band — `LOW`/`MEDIUM`/`HIGH` — ever
reaches a client-facing surface (mirrors Stage 2's `confidence_bucket`).
Exact coefficients/thresholds remain a Slice-2+/Methodology-calibration
concern; Slice 1 builds the interface and band-mapping mechanism with
conservative placeholder coefficients, clearly marked experimental.

**MDR-5 — Fit component set + scoring semantics. RESOLVED (rule); content pending.**
Fit is computed **only from compatible structured person↔career data**;
a component with no comparable pair on both sides resolves to `None`/
`NOT_APPLICABLE`, never a guessed or zeroed score. The exact component
list and weights remain Methodology content (weights already established
as experimental/not-approved); Slice 1 builds the `FitComponent`
protocol + registry mechanism, not the final component roster.

**MDR-6 — Fit aggregation method. RESOLVED (rule).**
Weighted mean over **available** (`SCORED`) components only; missing/
`INSUFFICIENT_EVIDENCE` components reduce coverage and are reflected in
`fit_score_is_partial` and in the (separate) confidence calculation —
never treated as a zero in the weighted mean.

**MDR-7 — Hard-constraint definition + vocabulary. RESOLVED (rule); content pending.**
The hard-block rule is fully specified in §7 (binding, tested per §16).
The `constraint_vocabulary` term list and its mapping to
`CareerRequirement`/`CareerWorkContext` fields is Methodology content,
delivered as data later — the gate mechanism does not need it to exist
yet to be correctly built and tested (it will simply have zero real
vocabulary entries, and therefore zero live matches, until content
lands — matching §5.3's stated consequence for `ProfileConstraint.is_hard`).

**MDR-8 — Minimum-input threshold. RESOLVED (rule and values).**
A `DirectionRun` may proceed past the minimum-input gate only when: the
user has a current/`READY` `PotentialProfile`, **and** it has ≥4
`SUPPORTED` claims, **and** those claims cover ≥3 distinct canonical
dimensions (§0, via the adapter). Otherwise:
`status=INSUFFICIENT_INFORMATION` + `ClarificationRequest[]`, zero
directions.

**MDR-9 — Critic pass/fail bars. RESOLVED (rule and classification).**
`BLOCKER` (a direction/run cannot proceed): hard constraint violation
(per §7's rule); nonexistent or unpublished career reference; invented
evidence/source (a claim/fact id that doesn't resolve); a `BLOCKED`
career appearing in the ranking; an explanation referencing nonexistent
provenance. `WARNING` (persisted, visible to the reviewer, never blocks):
low coverage; a weak explanation; an unresolved contradiction; low
confidence; duplicate/diversity issues; weak KB provenance (incl. a
`SOFT_SIGNAL` hard-constraint match, §7). Numeric similarity/anomaly
thresholds themselves remain a later-slice calibration detail.

**MDR-10 — MAIN vs ALTERNATIVE split rule. RESOLVED (rule).**
Eligible (non-`BLOCKED`, non-`REJECTED_BY_CRITIC`, non-`DEDUPED`)
candidates are sorted by `fit_score` descending, with `confidence` as the
tie-breaker. The first 3 become `MAIN`, the next 3 become `ALTERNATIVE`.
**Never padded to six** — fewer than 6 eligible candidates means fewer
than 6 directions are returned, with a diversity/coverage
`DirectionCriticFinding(WARNING)` surfaced instead of a manufactured
sixth direction (§5, §16).

**MDR-11 — Consultant correction reason-code taxonomy. RESOLVED (rule); content pending.**
Corrections use an approved, closed reason-code list delivered as data
(mirrors the taxonomy-as-data precedent). The `ConsultantCorrection`
schema (§5.2) already carries `reason_code` as a plain string column —
no engineering change is needed once the list is delivered; Slice 1 does
not need the final list to build the append-only correction mechanism.

**MDR-12 — Golden-case ground-truth ownership. RESOLVED (rule).**
Golden-case ground truth (which directions are acceptable/unacceptable
for a given synthetic profile) requires sign-off from a career expert/
panel **and** the Methodology Owner. Until that happens, all
`scenario_generation` golden cases remain `status: draft`,
`provenance.type: synthetic`, and are explicitly engineering fixtures
proving the mechanism — never cited as validated ground truth (unchanged
from the original golden-dataset governance rules in
`evals/golden/README.md`).

**No methodology decision remains unresolved as a blocker to starting
Slice 1.** Several (MDR-3, MDR-4's coefficients, MDR-5, MDR-7's
vocabulary, MDR-11) still await *content* delivery as versioned data —
this is normal, ongoing methodology work that continues in parallel
without gating the engineering mechanism Slice 1 builds, exactly as
Stage 2's taxonomy and Stage 3A's skills/KB content did.
