# MNP Career Fit / Direction Evaluation Model v0.1

> **STATUS: Founder-approved engineering methodology contract v0.1.**
> **NOT a validated psychometric instrument.**
> **Scoring / calibration remains EXPERIMENTAL until evaluated.**
> **All component weights are EXPERIMENTAL, NON-PRODUCTION placeholders
> (all equal in v0.1). Never presented as validated. No calibrated
> percentage semantics in v0.1/v0.2.**

Defines how a Human Potential Profile is evaluated against a career.
Incorporates the Founder "four-output" methodology update (Research Wave
A). Consumed by `app/services/direction/scoring/*`,
`app/services/direction/constraints.py`,
`app/services/direction/config.py`. Ranking lives in a **separate**
document: `MNP_RANKING_POLICY_V0.1.md`.

Version: `DIRECTION_EVALUATION_MODEL_VERSION = "mnp-direction-evaluation-model:v0.1"`.

---

## 1. Four separate outputs — never one blended score

Stage 3B produces **four structurally separate, separately stored**
outputs per (person, career). It never computes a monolithic career-fit
number and never collapses these into one public percentage.

| Output | Question | Canonical dimensions used |
|---|---|---|
| **Potential Fit** | How well does the career match the person? | Interests, Strengths, Skills (match), Work Style, Work Environment, Values (general), relevant Experience |
| **Goal Alignment** | How well does the career match where the person wants to go? | Goals, Motivation / desired outcomes, decision-relevant Values |
| **Transition Feasibility** | How realistic is the move *now*? | Constraints, Skill gaps (`CONFIRMED_MISSING` only), Abilities & Learning Potential, Career Adaptability / Agency, career requirements (education/credential/legal/time/financial) |
| **Evidence Confidence** | How reliable/sufficient is the evidence behind the three above? | evidence strength E1–E3, claim confidence, source diversity, coverage across the three fit outputs, contradictions, KB completeness/provenance |

Binding rules (Founder decisions N + F):
- separate concepts, separate stored values;
- **missing data reduces coverage/confidence, never Potential Fit**;
- `Potential Fit = HIGH` with `Transition Feasibility = LOW/MEDIUM` is a
  valid, expected combination — as is `Potential Fit = HIGH` with
  `Goal Alignment = LOW`;
- client/reviewer outputs use bands **LOW / MEDIUM / HIGH**;
- internal raw scores (0..1) exist only as versioned, explicitly
  `experimental` values.

---

## 2. Processing order (non-negotiable)

```
Career candidate
      ↓
HARD CONSTRAINT GATE            (§5 — deterministic, BEFORE any scoring; BLOCK is final)
      ↓   (BLOCKED careers are removed from recommendation eligibility)
SCORE COMPONENTS  per output    (§3 — deterministic; each: 0..1 OR INSUFFICIENT_DATA / NOT_APPLICABLE)
      ↓
FAMILY AGGREGATION  ×3          (§4 — weighted mean of AVAILABLE components only, per output)
      ↓
EVIDENCE CONFIDENCE             (§6 — separate deterministic calculation)
      ↓
RANKING POLICY                  (separate versioned layer — MNP_RANKING_POLICY_V0.1.md)
```

The hard gate runs first; a confirmed hard-constraint BLOCK removes the
career from eligibility regardless of any score.

---

## 3. Score components

A component compares **one compatible structured pair**: a profile
attribute/claim ↔ a career attribute/requirement/context. The LLM never
produces a numeric score. Every mapping rule is versioned/config-driven
(`ScoringConfig.enabled_components[output_family]`,
`ScoringConfig.component_weights[output_family]`).

Component result: `status ∈ {SCORED, INSUFFICIENT_DATA, NOT_APPLICABLE}`;
`raw_score ∈ [0,1]` only when `SCORED`; deterministic `rationale`;
`contributing_claim_ids`; `contributing_career_attributes`.
`INSUFFICIENT_DATA` = no comparable pair. `NOT_APPLICABLE` = structurally
does not apply. **Neither is zero.** A profile claim may contribute to
more than one output family through different deterministic calculations
(e.g. a Skills claim → `pf_skills_match` and `tf_skill_gap`).

### 3.1 Potential Fit components

| key | profile side | career side | v0.1 status |
|---|---|---|---|
| `pf_interests` | Interests claims | `Career.domain`, characteristics (`works_with_people/data/technology`, `creative_component`) | **implemented** |
| `pf_strengths` | Strengths claims | `Career` characteristics / activities | `INSUFFICIENT_DATA` (no structured mapping in v0.1) |
| `pf_skills_match` | Skills claims (`term_key`) | `CareerSkill` terms | **implemented** (`PRESENT` overlap only — never a gap penalty) |
| `pf_work_style` | Work Style subdimension claims | *(no structured career counterpart in KB v1)* | `INSUFFICIENT_DATA` |
| `pf_work_environment` | Work Environment claims (mapped) | `CareerWorkContext` (`setting`, `teamwork_level`, `schedule_predictability`) | **implemented** |
| `pf_values_general` | general Values claims | *(no structured career-side values data in KB v1)* | `INSUFFICIENT_DATA` |
| `pf_experience_relevance` | Experience claims | `CareerRelation`, `CareerSkill` overlap | `INSUFFICIENT_DATA` (no structured user experience in v0.1) |

### 3.2 Goal Alignment components

| key | profile side | career side | v0.1 status |
|---|---|---|---|
| `ga_goals` | Goals claims | `Career`, `CareerRelation` | `INSUFFICIENT_DATA` |
| `ga_motivation` | Motivation claims | *(no structured career counterpart)* | `INSUFFICIENT_DATA` |
| `ga_decision_relevant_values` | Values claims **with explicit decision-relevance evidence** | career | `INSUFFICIENT_DATA` — legacy Value claims carry no decision-relevance marker (Founder decision B); general Values feed Potential Fit only, never double-counted |

Goal Alignment is entirely `INSUFFICIENT_DATA` in legacy v0.1. Per the
RankingPolicy this reduces coverage/confidence and raises a warning — it
does **not** equal `LOW` and does not disqualify a MAIN candidate.

### 3.3 Transition Feasibility components

| key | profile side | career side | v0.1 status |
|---|---|---|---|
| `tf_skill_gap` | Skills claims classified `PRESENT`/`CONFIRMED_MISSING`/`UNKNOWN` (§7) | `CareerSkill(requirement_type=required)` | **implemented — computed only from sufficiently-assessed skill evidence; else `INSUFFICIENT_DATA`. Only `CONFIRMED_MISSING` counts as a gap.** |
| `tf_abilities_learning` | Abilities & Learning Potential claims | `CareerRequirement(education/certification)` | `INSUFFICIENT_DATA` (no legacy claim source — MNP-HPM §4.3) |
| `tf_career_adaptability` | Career Adaptability / Agency claims | `CareerRequirement` load, `CareerRelation` reachability | `INSUFFICIENT_DATA` |
| `tf_constraint_load` | confirmed **non-hard** Constraints (12 subtypes, §5) | `CareerWorkContext` soft mismatches, `CareerRequirement(TYPICAL_RECOMMENDATION)` | `INSUFFICIENT_DATA` in v0.1 (soft-constraint scoring is a later slice) |
| `tf_requirement_barriers` | user evidence of meeting education/credential/legal/time/financial requirements | `CareerRequirement` | `INSUFFICIENT_DATA` — a requirement existing is not evidence the user cannot meet it (`UNKNOWN ≠ NEGATIVE`) |

Transition Feasibility will have **limited coverage** in many pilot cases
(Founder decision H). That is acceptable; missing inputs return
`INSUFFICIENT_DATA` / partial coverage — never invented data.

### 3.4 Implemented scorer rules (v0.1)

- **`pf_interests`** — map each Interests claim's `term_key`/label to a
  career signal (`people_facing_work→works_with_people`,
  `technical_problem_solving→works_with_technology`,
  `creative_expression→creative_component`). Score = mean alignment over
  pairs where the career value is present. No mappable claims / all signals
  null ⇒ `INSUFFICIENT_DATA`.
- **`pf_skills_match`** — fraction of the career's `CareerSkill` terms
  covered by profile Skills claims classified `PRESENT` (§7), weighting
  `required` above `preferred`/`useful`. This measures overlap **only**;
  it never subtracts for skills the user is not known to have. No profile
  Skills claims with resolvable `term_key`, or the career has no
  `CareerSkill` rows ⇒ `INSUFFICIENT_DATA`. (v0.1 limitation: profile
  skill claims and `CareerSkill` reference different taxonomies; only exact
  `term_key` coincidence matches. Documented, not hidden.)
- **`pf_work_environment`** — compare mapped Work Environment claims to
  `CareerWorkContext` per facet (`setting`, `collaboration_context` vs
  `teamwork_level`, `schedule_predictability`). Score = mean per-facet
  alignment over facets present on both sides. None present ⇒
  `INSUFFICIENT_DATA`.
- **`tf_skill_gap`** — see §7. Score = `1 − (confirmed_missing_required /
  assessed_required)` where `assessed_required` counts only required
  skills classified `PRESENT` or `CONFIRMED_MISSING`. If
  `assessed_required == 0` (all required skills `UNKNOWN`, or the career
  lists no required skills) ⇒ `INSUFFICIENT_DATA` + `skills_to_verify`
  list. Coverage = `assessed_required / total_required`.

`CONTRADICTED` claims are never a positive input to any scorer.

---

## 4. Family aggregation (Founder decisions F + N)

For each of Potential Fit, Goal Alignment, Transition Feasibility:

```
raw = Σ(weightᵢ · raw_scoreᵢ) / Σ(weightᵢ)   over components with status == SCORED only
coverage_ratio = scored_component_count / enabled_component_count
```

- `INSUFFICIENT_DATA` / `NOT_APPLICABLE` components are **excluded from
  numerator and denominator**;
- they are **never** treated as a mismatch (score 0);
- if `scored_component_count < min_scored_components[family]` (config,
  v0.1 default 1 for each), `raw = None` and `band = None` — the output is
  "unknown", which is **not** `LOW`;
- band: `raw ≥ high_cutoff → HIGH`; `raw ≥ medium_cutoff → MEDIUM`; else
  `LOW`. Cutoffs are config (`is_experimental = true`).

Weights: `ScoringConfig.component_weights[family]` — **all equal in v0.1**
(the honest representation of "no validated weighting"). Weights are
`EXPERIMENTAL`, `VERSIONED`, `CONFIGURABLE`; never described as validated.

---

## 5. Hard constraint gate (Founder decisions G + Q)

Runs **before** all scoring. Deterministic. No LLM decides a violation.

### 5.1 A hard block requires BOTH

1. an explicit, **supported** user constraint marked hard **and
   confirmed** — `ProfileConstraint.is_hard == true AND is_confirmed ==
   true`; AND
2. an authoritative, machine-readable, incompatible career fact — a
   `CareerRequirement` with `certainty == HARD_FACTUAL` (which carries a
   `source_id` by the Stage 3A write-path contract) whose `category`
   matches the constraint subtype.

`CareerRequirement.certainty == TYPICAL_RECOMMENDATION` **never**
hard-blocks. Every requirement in the Stage 3A seed is
`TYPICAL_RECOMMENDATION`, so the gate issues **zero** blocks on current
seed data — acceptable (Founder decision G); the gate is proven with
synthetic `HARD_FACTUAL` fixtures.

### 5.2 The 12-subtype constraint taxonomy (v0.1)

`time`, `financial`, `geography`, `mobility`, `work_schedule`,
`work_format`, `language`, `education`, `credential`, `legal`,
`family_logistics`, `functional`. Each `ProfileConstraint` carries
`hard`/`soft` + confidence + `source_claim_id` provenance.
`CONSTRAINT_TAXONOMY_VERSION = "mnp-constraint-taxonomy:v0.1"`.

Hard-block-capable subtypes (have a `HARD_FACTUAL` career-side
counterpart): `education` ↔ `RequirementCategory.EDUCATION`; `credential`
↔ `CERTIFICATION` / `LICENSE`; `legal` ↔ `LEGAL_REGULATORY`; `language`
↔ `LANGUAGE`; `functional` ↔ `PHYSICAL_ENVIRONMENTAL`.
Soft-only in v0.1 (career-side is `CareerWorkContext`, not a
`HARD_FACTUAL` requirement): `time`, `financial`, `geography`,
`mobility`, `work_schedule`, `work_format`, `family_logistics`.

### 5.3 Results

| situation | `DirectionConstraintCheck.result` | effect |
|---|---|---|
| both conditions in §5.1 met | `BLOCK` | career removed from recommendation eligibility, regardless of any score |
| hard constraint present, career-side `HARD_FACTUAL` data absent/unknown | `INSUFFICIENT_DATA` | not blocked; may raise a clarification; recorded |
| constraint not hard, or not confirmed | *(not processed by the hard gate)* | soft handling only (a later slice) |

### 5.4 How a constraint becomes `hard` + `confirmed` in v0.1

v0.1 does **not** auto-classify a constraint from assessment text.
`is_hard` / `is_confirmed` default `false` and are set only by an
explicit signal (a future consultant confirmation / structured assessment
field). The gate fully supports `is_hard = true` (fixtures); on current
data it is inert. Open question for v0.2: the explicit hardness/
confirmation rule.

---

## 6. Evidence Confidence (output #4)

Separate deterministic calculation
(`app/services/direction/scoring/evidence_confidence.py`). Inputs
(Evidence Standard §2.2): evidence strength E1–E3 of the supporting
claims; their claim confidence; distinct `Evidence.source_type` count;
coverage across the three fit outputs (how many produced a non-`None`
raw); count of `CONTRADICTED` claims among the relevant set; fraction of
compared career attributes that were curated (not null).

v0.1 combination (additive + bounded, the `compute_claim_confidence`
style; all constants in `ScoringConfig.thresholds`, `is_experimental`):

```
base   = mean(claim_confidence of supporting SUPPORTED claims)
       + tier_bonus       (0 / +0.05 / +0.10 by dominant E-tier E1/E2/E3)
       + diversity_bonus  (0 / +0.05 / +0.10 for ≥2 / ≥3 distinct source types)
       + coverage_bonus   ((fit_outputs_with_raw − 1) · 0.05, capped +0.10)
       − contradiction_penalty  (min(cap, count · per_item))
       − kb_incompleteness_penalty  ((1 − kb_completeness) · 0.15)
raw    = clamp(base, 0, 1)          # EXPERIMENTAL
band   = HIGH if raw ≥ high_cutoff else MEDIUM if raw ≥ medium_cutoff else LOW
```

No supporting SUPPORTED claims ⇒ `raw = None`, `band = None`
(insufficient — not `LOW`).

---

## 7. Skill-state semantics — `PRESENT` / `CONFIRMED_MISSING` / `UNKNOWN` (Founder decision P)

`UNKNOWN ≠ NEGATIVE`. For each `required` `CareerSkill`:

| state | condition |
|---|---|
| `PRESENT` | a `SUPPORTED` Skills claim whose `term_key` matches the required skill exists |
| `CONFIRMED_MISSING` | an explicit claim/evidence states the user lacks the skill or has an insufficient level (v0.1: a `CONTRADICTED` or explicitly-negative Skills claim on that `term_key`) |
| `UNKNOWN` | none of the above — including "no claim mentions this skill at all" |

- A required skill **absent from all profile claims is `UNKNOWN`**, never
  `CONFIRMED_MISSING`.
- Only `CONFIRMED_MISSING` skills are true Skill Gaps.
- `UNKNOWN` required skills become `skills_to_verify` (information gaps →
  a `ClarificationRequest`, never a penalty).
- `tf_skill_gap` is computed **only** from `PRESENT` + `CONFIRMED_MISSING`
  (the "assessed" set); if that set is empty ⇒ `INSUFFICIENT_DATA`.
  Coverage (`assessed / total_required`) is exposed separately.

---

## 8. Explainability

Every eligible direction must answer **"why this direction?"** with, per
output: the components (key, status, raw, rationale); supporting claims
(+ evidence + E-tier); career facts used (+ sources); the constraint
checks; gaps (`INSUFFICIENT_DATA` components, `skills_to_verify`,
clarifications); risks (`CONTRADICTED` claims, soft-constraint conflicts,
stale facts); the four bands; `methodology_version`;
`direction_evaluation_model_version`; `knowledge_base_version_id`;
`scoring_config` (+ experimental flag); `ranking_policy` (+ experimental
flag); engine/prompt/model versions; `generated_at`. A recommendation
without this provenance is invalid.
