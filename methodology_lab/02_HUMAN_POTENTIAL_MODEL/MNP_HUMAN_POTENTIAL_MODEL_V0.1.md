# MNP Human Potential Model (MNP-HPM) v0.1

> **AMENDED BY MATCHING V1 FOUNDER DEFINITION (2026-08-28):** Work Style
> (§3.1) and Work Environment (§3.2) subdimensions below are **reused
> unchanged** by the new BASIC V1 deterministic Golden Test. Work Values
> (§3.4, previously top-level-only) gains a new 8-scale subdimension set
> under Matching V1 — see `methodology_lab/05_GOLDEN_TEST/MNP_GOLDEN_TEST_V0.1.md`
> §11 and Open Question A. This is a light-touch pointer amendment; the
> dimension/subdimension definitions below are not rewritten and remain
> the canonical reference for both the historical (Stage 3B) and new
> (Matching V1) methodologies.

> **STATUS: Founder-approved engineering methodology contract v0.1.**
> **NOT a validated psychometric instrument.**
> **Scoring / calibration remains EXPERIMENTAL until evaluated.**

**Miy Napryam Human Potential Model.** A multidimensional model of a
person's *career potential* — not a personality type, not a personality
test, not a clinical instrument. It defines *what the system tries to
understand about a person* and how those understandings are represented so
they stay auditable.

Consumed by: `app/services/direction/` (Direction Intelligence). Governs:
`app/services/direction/dimensions.py`,
`app/services/direction/dimension_mapping.py`.

---

## 1. The four levels of truth (non-negotiable)

Every statement the system holds about a person sits at exactly one level.
Levels are never silently promoted.

| Level | Definition | Example | Represented as |
|---|---|---|---|
| **FACT** | Something the person stated or a document verifiably shows. | "Worked as a department head for 5 years." | `Answer` / `CVUpload` (Stage 1) → `Evidence` (Stage 2), `source_type` + `source_id` |
| **EVIDENCE** | A normalized, source-referenced observation derived from raw data. | "Has managed people." | `Evidence` row |
| **CLAIM / HYPOTHESIS** | A statement *about the person* grounded in ≥1 evidence item, carrying its own status + confidence. A CLAIM with `SUPPORTED` status is a working conclusion; anything weaker is a HYPOTHESIS. | "Is probably comfortable in high-responsibility roles." | `ProfileClaim` (+ `ProfileClaimEvidence`) |
| **INTERPRETATION** | A methodology-level reading that combines claims. | "Leadership-capable profile." | computed in `app/services/direction/`, never stored as a `ProfileClaim` |
| **RECOMMENDATION** | A suggested career direction. | "Project Manager may be a promising direction." | `Direction` (Stage 3B) |

`FACT ≠ EVIDENCE ≠ CLAIM ≠ INTERPRETATION ≠ RECOMMENDATION`. They must
remain distinguishable in data structures and logic. Stage 2 already
enforces the first three boundaries; Stage 3B keeps INTERPRETATION and
RECOMMENDATION as separate objects and never writes them back as claims.

---

## 2. The 12 canonical dimensions (v0.1)

Exactly these twelve, in this order. This list is **architectural** (a
stable enum, `CanonicalDimension`), not open content.

| # | Dimension | Defining question |
|---|---|---|
| 1 | **Interests** | What does the person genuinely want to *do*? |
| 2 | **Strengths** | In what kinds of activity does the person show strength? |
| 3 | **Skills** | What can the person already do? |
| 4 | **Abilities & Learning Potential** | What could the person learn quickly? |
| 5 | **Work Style** | How is the person comfortable operating? |
| 6 | **Work Environment** | In what setting does the person do their best work? |
| 7 | **Values** | What matters to the person in work and life? |
| 8 | **Motivation** | What makes the person act? |
| 9 | **Experience** | What experience can already be leaned on? |
| 10 | **Goals** | Where does the person want to get to? |
| 11 | **Constraints** | What actually limits the choice? |
| 12 | **Career Adaptability / Agency** | How ready is the person to change direction and learn? |

**v0.1 must not**: add a 13th dimension; rename these; re-scope what one
means; or treat "we have no claims for dimension X" as a negative signal
about the person (it is a coverage gap — see the Evidence Standard and
Career Fit Model).

---

## 3. Subdimensions (v0.1)

Subdimensions are **versioned, config-driven** data
(`app/services/direction/dimensions.py`,
`SUBDIMENSION_TAXONOMY_VERSION = "mnp-hpm-subdimensions:v0.1"`).
Engineering implements **only** what is listed here.

### 3.1 Work Style — full v0.1 subdimension set (Founder-specified)

| key | meaning |
|---|---|
| `autonomy` | preference for independent vs directed work |
| `structure_preference` | preference for structured vs open-ended work |
| `ambiguity_tolerance` | comfort with unclear situations |
| `pace` | preferred tempo of work |
| `collaboration` | preference for working with others vs alone |
| `leadership` | inclination to lead / coordinate |
| `customer_interaction` | comfort with direct customer/client contact |
| `decision_responsibility` | comfort holding decision responsibility |
| `routine_tolerance` | tolerance for repetitive work |
| `initiative` | tendency to act without being prompted |

Each subdimension claim carries `value + confidence + supporting evidence`
(the Stage 2 `ProfileClaim` shape already supports this).

### 3.2 Work Environment — matchable facets (v0.1)

These mirror **already-curated** structured career data
(`CareerWorkContext`) — they are a matching surface, not new psychology.

| key | mirrors career-side |
|---|---|
| `setting` | `CareerWorkContext.setting` (office/remote/field/mixed) |
| `collaboration_context` | `CareerWorkContext.teamwork_level` |
| `schedule_predictability` | `CareerWorkContext.schedule_predictability` |
| `physical_environment` | `CareerWorkContext.physical_intensity`, `indoor_outdoor` |
| `customer_interaction_context` | `CareerWorkContext.customer_interaction_level`, `client_facing` |

### 3.3 Constraints — 12-subtype taxonomy (v0.1, Founder decision Q)

Time and financial barriers are **subtypes of Constraints**, not new
top-level dimensions. The v0.1 taxonomy has exactly these 12 subtypes.
Each `ProfileConstraint` carries `hard`/`soft` + confidence +
`source_claim_id` provenance. `CONSTRAINT_TAXONOMY_VERSION =
"mnp-constraint-taxonomy:v0.1"`.

| subtype | career-side counterpart | hard-block-capable in v0.1? |
|---|---|---|
| `time` | *(soft: schedule / hours load)* | no |
| `financial` | *(soft: no direct career-side signal in KB v1)* | no |
| `geography` | `CareerWorkContext.setting` | no |
| `mobility` | `CareerWorkContext.travel_required` | no |
| `work_schedule` | `CareerWorkContext.shift_work`, `schedule_predictability` | no |
| `work_format` | `CareerWorkContext.setting` (remote/office/field) | no |
| `language` | `CareerRequirement(category=language, certainty=HARD_FACTUAL)` | **yes** |
| `education` | `CareerRequirement(category=education, certainty=HARD_FACTUAL)` | **yes** |
| `credential` | `CareerRequirement(category ∈ {certification, license}, certainty=HARD_FACTUAL)` | **yes** |
| `legal` | `CareerRequirement(category=legal_regulatory, certainty=HARD_FACTUAL)` | **yes** |
| `family_logistics` | *(soft: schedule / travel load)* | no |
| `functional` | `CareerRequirement(category=physical_environmental, certainty=HARD_FACTUAL)` | **yes** |

A hard block still requires **both** a confirmed hard user constraint and
a `HARD_FACTUAL` career-side counterpart (Career Fit / Direction
Evaluation Model §5). Soft-only subtypes never hard-block in v0.1.

### 3.4 All other dimensions

**v0.1: top-level only.** Interests, Strengths, Skills, Abilities &
Learning Potential, Values, Motivation, Experience, Goals, Career
Adaptability / Agency carry **no subdimensions** in v0.1 — claims attach
at the dimension level. Adding subdimensions for any of them is a v0.2
methodology task, not an engineering choice.

---

## 4. Legacy → canonical claim mapping (MDR-2)

Stage 2 persists `ProfileClaim.dimension` using the legacy 11-value
`ProfileDimension` enum (`strength, interest, value, motivation, skill,
trait, work_preference, constraint, goal, experience, contextual_factor`).
Stage 3B reads those claims through a **read-only, versioned adapter**
(`app/services/direction/dimension_mapping.py`,
`DIMENSION_MAPPING_VERSION = "legacy-to-mnp:v0.1"`).

**Rules:** the adapter never writes/rewrites a `ProfileClaim`; it preserves
the legacy dimension on every mapped result; it emits one of
`MAPPED` / `UNMAPPED` / `NEEDS_CLARIFICATION`; it never creates a claim.

### 4.1 Direct dimension mappings

| legacy `dimension` | canonical dimension | status |
|---|---|---|
| `interest` | Interests | MAPPED |
| `strength` | Strengths | MAPPED |
| `skill` | Skills | MAPPED |
| `value` | Values | MAPPED |
| `motivation` | Motivation | MAPPED |
| `goal` | Goals | MAPPED |
| `experience` | Experience | MAPPED |
| `constraint` | Constraints | MAPPED |

### 4.2 Term-specific mappings (rule keyed by `term_key`, falls back to a default)

| legacy `dimension` | `term_key` | canonical | subdimension | status |
|---|---|---|---|---|
| `work_preference` | `remote_work` | Work Environment | `setting` | MAPPED |
| `work_preference` | `team_environment` | Work Environment | `collaboration_context` | MAPPED |
| `work_preference` | `structured_environment` | Work Style | `structure_preference` | MAPPED |
| `work_preference` | *(any other / null)* | — | — | **NEEDS_CLARIFICATION** (Work Style vs Work Environment is ambiguous) |
| `trait` | `adaptability` | Career Adaptability / Agency | — | MAPPED |
| `trait` | *(any other / null)* | — | — | **NEEDS_CLARIFICATION** (a disposition is not a 1:1 canonical dimension) |
| `contextual_factor` | `family_responsibilities` | Constraints | `family_logistics` | MAPPED |
| `contextual_factor` | *(any other / null)* | — | — | **UNMAPPED** |

### 4.3 Canonical dimensions with no legacy source in v0.1

**Abilities & Learning Potential** has no legacy `ProfileDimension`
counterpart. Its Fit components therefore return `INSUFFICIENT_DATA` in
v0.1 (Career Fit Model §3). This is a coverage gap, recorded honestly —
never filled by inventing claims.

### 4.4 Handling of `UNMAPPED` / `NEEDS_CLARIFICATION`

- Such claims are excluded from Fit scoring (they contribute to no
  component).
- They still count toward **profile coverage** reporting so the gap is
  visible.
- `NEEDS_CLARIFICATION` may raise a `ClarificationRequest`
  (`reason = MISSING_DIMENSION` / `LOW_CONFIDENCE_COVERAGE`) — it never
  raises the Stage 1 assessment from a terminal state (Founder decision
  M3).

---

## 5. Contradictions

Stage 2 already flags a contradictory claim as
`ClaimStatus.CONTRADICTED`, retains both supporting and contradicting
evidence, and never averages them. MNP-HPM v0.1 adds:

- A `CONTRADICTED` claim is **never** used as a positive input to a Fit
  component. It is surfaced as a risk/gap and lowers direction confidence
  (Evidence Standard §4, Career Fit Model §7).
- An important unresolved contradiction is eligible to produce a
  `ClarificationRequest` (`reason = UNRESOLVED_CONTRADICTION`).

---

## 6. What "understanding a person" is allowed to produce

The model produces, per person: a set of evidence-grounded claims across
(some of) the 12 dimensions, each at a truth level (§1), each with a
deterministic confidence band (Evidence Standard). It does **not** produce:
a personality type label; a diagnosis; a guaranteed outcome; or a claim
unsupported by evidence. Direction Intelligence reads this structure — it
does not get to add to it.
