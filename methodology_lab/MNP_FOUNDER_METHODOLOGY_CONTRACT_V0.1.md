# MNP Founder Methodology Contract v0.1

> **STATUS: Founder-approved engineering methodology contract v0.1.**
> **NOT a validated psychometric instrument.**
> **Scoring / calibration remains EXPERIMENTAL until evaluated.**

This document records the binding Founder decisions that unblocked Stage 3B
and the hard limits they place on engineering. The other four v0.1
documents implement these decisions in detail. If any of them appears to
contradict this contract, **this contract wins** and the discrepancy is a
bug to fix.

---

## 1. Roles

- **Founder / Product Owner + Methodology Owner** decide *what* the system
  concludes about a person and *what* makes a career fit.
- **Engineering** decides *how* it is computed, stored, versioned, and
  tested — while preserving every rule below.

Engineering **must not** independently: invent Human Potential dimensions;
change dimension semantics; invent final Career Fit weights; invent
psychometric scoring; claim scientific validity; turn hypotheses into
facts; remove evidence/provenance requirements; use LLM confidence as
authoritative; treat missing information as negative evidence; silently
resolve contradictions; bypass hard constraints; let consultant edits
auto-change methodology; or use LLM memory as authoritative career
knowledge.

When implementation needs a methodology decision not covered here or in
the four v0.1 documents, engineering **stops** and raises a
`METHODOLOGY DECISION REQUIRED` note — it does not guess.

---

## 2. Binding decisions (A–M)

### A. Methodology canon
The five v0.1 documents in `methodology_lab/` are the approved source. The
methodology text in the Founder task + brief is the approved content for
v0.1. No methodology beyond that Founder-approved content may be
introduced silently.

### B. Canonical dimensions (MNP-HPM v0.1) — exactly these 12
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

Stage 2's existing 11-value `ProfileDimension` enum is **not** migrated or
redesigned. A **versioned adapter** maps legacy `ProfileClaim`s to
canonical dimension/subdimension. The adapter: versions the mapping;
preserves the original dimension; never rewrites historical claims; may
return `UNMAPPED` / `NEEDS_CLARIFICATION`; and never invents a claim to
fill the 12-dimension model.

### C. Subdimensions
Versioned, config-driven v0.1 taxonomy. Engineering implements **only**
subdimensions specified in the v0.1 documents. No new psychological
constructs.

### D. Confidence
Final confidence is deterministic and auditable. LLM confidence is never
authoritative. Internal raw confidence may be computed in 0..1 but is
flagged **EXPERIMENTAL**. Public/client-facing v0.1 semantics are **LOW /
MEDIUM / HIGH**, never a scientifically-precise percentage. Confidence
inputs may include: claim evidence strength; claim confidence; source
diversity; profile coverage; contradictions; Career KB
completeness/provenance. All constants/thresholds live in versioned
configuration.

### E. Fit components
Fit is deterministic. A component compares only compatible **structured**
profile attribute/claim ↔ career attribute/requirement/context. The LLM
never invents a numeric fit. Mapping rules are versioned/config-driven.
Missing comparable data returns `None` / `INSUFFICIENT_DATA`, **never
zero**.

### F. Fit aggregation
Overall Fit = weighted mean of **available** components only. A missing
component is excluded from numerator and denominator, reduces
coverage/confidence, and is never treated as a mismatch by default.
Weights are **EXPERIMENTAL, VERSIONED, CONFIGURABLE** — never described as
validated.

### G. Hard constraints
A deterministic hard block for V1 requires **both**:
1. an explicit, supported user constraint marked hard; and
2. authoritative, machine-readable, incompatible career data.

`CareerRequirement.certainty == TYPICAL_RECOMMENDATION` **must never**
auto-hard-block. Only `HARD_FACTUAL` (which carries provenance) may
hard-block, and only when directly incompatible with the user's hard
constraint. The Stage 3A seed has almost no authoritative hard-blocking
data — that is acceptable; hard-gate behavior is proven with **synthetic
engineering fixtures**, never fabricated real requirements.

### H. Minimum profile threshold (initial, experimental)
- `PotentialProfile` must be `READY` and current.
- ≥ 4 `SUPPORTED` claims.
- Those supported claims must cover ≥ 3 canonical MNP dimensions.

Below threshold ⇒ `DirectionRun.status = INSUFFICIENT_INFORMATION` and/or a
`ClarificationRequest`. **Never** manufacture TOP 3 + ALT 3. Threshold is
versioned/configurable.

### I. Critic
v0.1 critic is **deterministic first**.
- **BLOCKER**: hard-constraint violation; direction references a
  nonexistent/unpublished career; invented profile evidence;
  invented/unsupported career fact; a BLOCKED career appearing in
  MAIN/ALT ranking; explanation references evidence/source not actually
  linked.
- **WARNING**: low profile coverage; weak explanation; low direction
  confidence; unresolved contradiction; duplicate/near-duplicate
  direction; insufficient diversity; weak KB provenance.

No arbitrary semantic-similarity thresholds. An LLM critic may later give
**advisory** findings only, behind a feature flag.

### J. TOP 3 / ALT 3 (v0.1 ranking)
1. remove BLOCKED candidates;
2. sort eligible candidates by `fit_score` descending;
3. `confidence` is the deterministic tie-breaker;
4. first 3 → MAIN; next 3 → ALTERNATIVE.

Fit is never silently altered for diversity (diversity is a critic
WARNING in v0.1). If fewer than 6 credible directions exist, return
fewer — **never pad**.

### K. Consultant correction reason codes — exactly this closed set
`wrong_inference`, `missing_inference`, `wrong_dimension`,
`overconfidence`, `underconfidence`, `contradiction_missed`,
`constraint_missed`, `unsupported_fact`, `wrong_direction_priority`,
`career_knowledge_problem`, `evidence_extraction_problem`, `wording_only`,
`other_with_comment`.

`ConsultantCorrection` is append-only; the original artifact is immutable.

### L. Golden cases
Synthetic fixtures are engineering tests only — not scientific ground
truth. A production Golden Case becomes authoritative only after review by
a career consultant / expert panel **and** the Methodology Owner, with
expected claims, acceptable/unacceptable recommendations, hard
constraints, rationale, and ambiguity notes preserved.

### M. Additional decisions
1. **`Direction*` naming** is used for V1; the legacy ERD `SCENARIO`
   terminology is superseded for this product slice.
2. **Persist `AI_TRACE`** if it can be a clean additive change; no
   secrets/PII in traces.
3. A Stage 3B `ClarificationRequest` may be created, but the **Stage 1
   assessment state machine is not reopened** in this stage.
4. `request_changes` preserves immutable history. Regeneration creates a
   **new** `DirectionRun`/version. Consultant corrections are
   overlays/history, never destructive updates.
5. Stage 3B may run **synchronously** for the pilot; orchestration stays
   queue-ready; no queue infrastructure is built solely for this slice.

---

---

## 2A. Research Wave A addendum (Founder methodology update — binding)

Refines, does not replace, decisions E / F / J above. Where this addendum
and 2.E/2.F/2.J differ, **the addendum wins**.

### N. Four separate scoring outputs — never a monolithic Career Fit

Stage 3B does **not** compute one blended career-fit score from all 12
dimensions. It computes four structurally separate, separately stored
outputs:

| Output | Question | Inputs (canonical dimensions) |
|---|---|---|
| **Potential Fit** | how well does the career match the person? | Interests, Strengths, Skills (match), Work Style, Work Environment, Values (general), relevant Experience |
| **Goal Alignment** | how well does the career match where the person wants to go? | Goals, Motivation / desired outcomes, Values *relevant to the current decision* |
| **Transition Feasibility** | how realistic is the move *now*? | Constraints, Skill gaps (`CONFIRMED_MISSING` only), Abilities & Learning Potential, Career Adaptability / Agency, career requirements (education/credential/legal/time/financial) |
| **Evidence Confidence** | how reliable/sufficient is the evidence behind the three above? | evidence strength (E1–E3), claim confidence, source diversity, coverage across the three fit outputs, contradictions, Career KB completeness/provenance |

Binding rules:
- separate concepts, separate stored values, **never collapsed into one
  public percentage**;
- missing data reduces **coverage / confidence**, never Potential Fit;
- a career may be `Potential Fit = HIGH` with `Transition Feasibility =
  LOW/MEDIUM`, or `Potential Fit = HIGH` with `Goal Alignment = LOW`;
- no calibrated percentage semantics in v0.1/v0.2 — client/reviewer
  outputs prefer bands **LOW / MEDIUM / HIGH**;
- internal experimental raw scores (0..1) may exist only if versioned and
  explicitly marked experimental.

### O. Ranking is a separate, versioned decision layer

A `RankingPolicy` is a distinct versioned entity. It does **not** define a
hidden composite career score. It defines: eligibility rules; qualitative
band gates; lexicographic sort precedence; tie-breakers; MAIN maximum;
ALTERNATIVE maximum; missing-output semantics; evidence-confidence
requirements; dedup/diversity rules; `is_experimental`;
`methodology_version`. Ranking logic is never baked into the definition of
Potential Fit. See `04_CAREER_FIT_MODEL/MNP_RANKING_POLICY_V0.1.md`.

RankingPolicy v0.1 (Founder decision A):
1. hard-constraint gate — BLOCKED careers are excluded from eligibility;
2. **MAIN eligibility**: `Potential Fit ≥ MEDIUM`; `Goal Alignment ≠ LOW`
   when known; `Transition Feasibility ≠ LOW` when known; `Evidence
   Confidence ≥ MEDIUM`. **Unknown Goal Alignment / Feasibility is NOT
   LOW** — it does not disqualify, but reduces coverage/confidence and
   raises a warning;
3. **MAIN ordering**: lexicographic — Potential Fit raw DESC, then Goal
   Alignment raw DESC (None last), then Transition Feasibility raw DESC
   (None last), then Evidence Confidence raw DESC. **No composite
   number.**
4. **ALTERNATIVE pool**: hard gate PASS and `Potential Fit ≥ MEDIUM`. An
   Alternative may carry `LOW` Goal Alignment or `LOW` Transition
   Feasibility — surfaced as a trade-off;
5. **never pad** — if only 2 credible MAIN + 2 credible ALTERNATIVE
   exist, return 4;
6. RankingPolicy is versioned and experimental.

### P. Skill-state semantics — `PRESENT` / `CONFIRMED_MISSING` / `UNKNOWN`

`UNKNOWN ≠ NEGATIVE`. For each `required` `CareerSkill`, classify the
user's knowledge:

- **`PRESENT`** — a supported matching Skill claim/evidence exists;
- **`CONFIRMED_MISSING`** — explicit evidence shows the user lacks the
  skill or has an insufficient level;
- **`UNKNOWN`** — not enough evidence either way.

A required skill **absent from profile claims is `UNKNOWN`, never
`CONFIRMED_MISSING`.** Only `CONFIRMED_MISSING` skills are true Skill
Gaps. `UNKNOWN` required skills become `skills_to_verify` / information
gaps and raise a clarification, not a penalty. The Transition Feasibility
skill component is computed **only** from sufficiently-assessed skill
evidence; otherwise it returns `INSUFFICIENT_DATA` and exposes coverage
separately. Never infer lack of competence from missing profile data.

### Q. Constraints — 12 subtypes, no 13th dimension

Time and financial barriers are **subtypes of the canonical `Constraints`
dimension**, not new top-level dimensions. The v0.1 constraint taxonomy
represents: `time`, `financial`, `geography`, `mobility`,
`work_schedule`, `work_format`, `language`, `education`, `credential`,
`legal`, `family_logistics`, `functional`. Each constraint carries
`hard` / `soft` plus evidence/status/provenance semantics. A hard block
still requires a `HARD_FACTUAL` career-side counterpart (decision G,
unchanged).

### H (Wave A). Transition Feasibility coverage expectation

Transition Feasibility will initially have limited coverage in many pilot
cases (Abilities has no legacy claim source; skill verification, time and
financial constraint evidence are thin in v0.1). This is acceptable.
Missing inputs return `INSUFFICIENT_DATA` / partial coverage — data is
never invented to compensate. Precision improves as Stage 1 and the
methodology improve.

---

## 3. What v0.1 explicitly does NOT decide

Recorded so a later version, not an implementer, closes them:

- The real (non-experimental) per-output component weights (all-equal,
  experimental in v0.1).
- The calibrated confidence coefficients / band cutoffs.
- Whether curated `CareerWorkContext` attributes (not just
  `HARD_FACTUAL` requirements) may ever become a hard-block basis.
- How a constraint claim is automatically classified as *hard* and
  *confirmed* from assessment data alone (v0.1: it is not —
  hardness/confirmation come from an explicit signal only).
- Subdimension taxonomies for the dimensions left "top-level only" in
  v0.1 (see MNP-HPM §4).
- Numeric duplicate/diversity thresholds for the critic / RankingPolicy.
- The explicit "decision-relevant Value" evidence marker that would let a
  Value claim also feed Goal Alignment (v0.1: absent — Goal-Alignment
  Values = `INSUFFICIENT_DATA`; decision B).
- Structured career-side data for Goal Alignment and most Transition
  Feasibility components (v0.1: `INSUFFICIENT_DATA`; decision H).
