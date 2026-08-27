# MNP Methodology Backlog v0.2

> **STATUS: Founder-approved methodology-operational document —
> planning artifact for `v0.2+`.**
> **The current canon (`MNP-HPM / Direction Evaluation v0.1`) is frozen as
> the MVP EXPERIMENTAL BASELINE. Nothing in this backlog changes the 12
> dimensions or the four-output model without a full methodology release
> (`MNP_LEARNING_AND_FEEDBACK_PROTOCOL_V0.1.md` §5).**

Priority bands:

| band | meaning | trigger to act |
|---|---|---|
| **P0** | the current MVP is unsafe or invalid — pilot pauses until fixed | a `MNP_PILOT_EVALUATION_PROTOCOL_V0.1.md` alarm fires (esp. §2.8) |
| **P1** | do after the first **20–50** reviewed pilot cases | first full pilot report |
| **P2** | do after **100+** cases | trend view / calibration decision |
| **P3** | future research — no pilot dependency | opportunistic |

Item types: **S1** = Stage 1 assessment change · **KB** = Knowledge Base
content · **CAL** = calibration of existing (experimental) numbers ·
**RES** = research / study · **ENG** = engineering surface.

---

## P0 — only if the MVP proves unsafe/invalid

**None are open today.** The v0.1 baseline is designed to fail safe
(`INSUFFICIENT_DATA` / `NEED_MORE_EVIDENCE` instead of guessing; hard gate
inert rather than wrong; no calibrated % claims). A P0 is *created* if and
only if a pilot metric alarm fires:

| condition (from `MNP_PILOT_EVALUATION_PROTOCOL_V0.1.md`) | P0 that opens | type |
|---|---|---|
| §2.8 Hard Constraint Violation Rate **> 0** | audit + fix the hard-constraint gate / KB `HARD_FACTUAL` data path | ENG + KB |
| §2.3 Unsupported Claim Rate **> 0.05** | audit the Evidence → Claim pipeline (Stage 2) and the claim-synthesis prompt | ENG |
| §2.4 Contradiction Miss Rate **> 0.15/run** | audit contradiction detection (Stage 2) + the adapter | ENG |
| prohibited diagnosis / guarantee / invented-market-fact language reaches a reviewed run | prompt + critic hardening | ENG |
| a fairness/bias red flag surfaces in review (systematic mis-scoring by an inferable group) | pause, investigate (see P1 fairness item) | RES + ENG |

---

## P1 — after the first 20–50 pilot cases

| item | why now | what it is | type | depends on |
|---|---|---|---|---|
| **Confidence calibration (Evidence Confidence + claim confidence bands)** | the first 20–50 reviews give real `overconfidence`/`underconfidence` correction rates per band | re-fit the band cutoffs and the additive bonuses/penalties in `ScoringConfig.thresholds`; publish as a **new non-experimental config**, old runs keep their old config | CAL | pilot data; Methodology Owner sign-off |
| **Constraints elicitation (hard/soft + confirmed)** | the hard gate is inert in production because the assessment never marks a constraint hard+confirmed; this is the biggest *safety-relevant* coverage gap | Stage 1 v2: an explicit constraint block covering all 12 subtypes, each with a "hard limit or preference?" follow-up; define the rule that promotes a constraint to `hard` + `confirmed` (currently undefined — Founder-flagged open question) | S1 + methodology rule | Stage 1 v2 slot |
| **Interest assessment improvement** | Interests is one of only 4 components that can score today, and it drives Potential Fit heavily | Stage 1 v2: behavioural interest prompts + a structured interest-area checklist; reduces self-report ceiling | S1 | Stage 1 v2 slot |
| **Skills: proficiency + explicit negatives + taxonomy alignment** | `tf_skill_gap` can only produce `PRESENT`/`CONFIRMED_MISSING` when the assessment elicits explicit skill states; profile vs career skill taxonomies don't align | Stage 1 v2 structured skill checklist self-rated against the `skills` taxonomy + an explicit "skills you lack / want to avoid" item | S1 + ENG (taxonomy map) | Stage 1 v2 slot |
| **Values trade-offs + decision-relevance marker** | Goal Alignment is entirely `INSUFFICIENT_DATA`; general Values feed only Potential Fit | Stage 1 v2: values forced-ranking + a "which value matters most for THIS decision" item → unlocks `ga_decision_relevant_values` | S1 + methodology rule | Stage 1 v2 slot |
| **Expert consensus study (mini)** | authoritative Golden Cases need inter-rater data; also validates the Consultant Review Standard itself | run 2 consultants independently over 15–20 pilot runs; measure agreement on claims, directions, bands; produces the first authoritative Golden Cases | RES | 2 consultants; `MNP_GOLDEN_CASE_PROTOCOL_V0.1.md` |
| **Client outcome tracking (setup)** | the immediate survey is defined but not instrumented; 30/90-day follow-up needs to start early to have data later | instrument the immediate 3-question survey (§3 of the pilot protocol) + schedule 30/90-day check-ins | ENG | consent copy |

---

## P2 — after 100+ cases

| item | why | what it is | type |
|---|---|---|---|
| **Scoring-weight calibration (per-output component weights)** | 100+ cases + consensus data are enough to move off "all weights equal" | re-fit `component_weights[output_family]` from consultant corrections + Golden Cases; publish a new non-experimental `ScoringConfig` | CAL |
| **Work Style refinement** | needs both a Stage 1 block (10 subdimensions) AND matching KB career attributes | Stage 1 v2 Work Style block + KB curation of career work-style attributes; then a real `pf_work_style` scorer | S1 + KB + ENG |
| **ESCO / O*NET enrichment** | Goal Alignment and most of Transition Feasibility are `INSUFFICIENT_DATA` for lack of structured career-side data | map careers to ESCO/O*NET; import structured requirements, work activities, skill importance; lands as a new **DRAFT** KB version, never auto-trusted | KB |
| **Adaptability / agency measurement** | `tf_career_adaptability` is always `INSUFFICIENT_DATA` | Stage 1 v2 adaptability block; consider a light validated scale; then a real scorer | S1 + RES |
| **Ability assessment** | Abilities & Learning Potential has no source at all | decide: learning-history questions only, or a light external aptitude module (cost/UX trade-off) | S1 + RES |
| **Language validation (UA / EN, later RU / DE)** | the product ships Ukrainian-first; prompts, scales, and constraint keyword-matching are not validated across languages | translate + back-translate all assessment items and methodology-facing text; check the keyword classifiers in `constraints.py` for each locale | RES + ENG |

---

## P3 — future research (no pilot dependency)

| item | what it is | type |
|---|---|---|
| **Fairness / bias evaluation (full)** | systematic study: does the pipeline mis-score by age, gender, region, first language, education level? requires enough outcome data and a study design | RES |
| **Client outcome study (6–12 month)** | did people actually move toward the recommended direction? did it help? the only real external validity signal | RES |
| **Psychometric validation of the 12-dimension model** | the model is an "engineering methodology contract", not a validated instrument; a proper construct-validity study is a large, separate effort | RES |
| **Interest inventory / RIASEC-style structure** | replace or augment the checklist with a validated interest framework | RES |
| **Narrative quality rubric** | once the LLM narrative ships, a graded rubric beyond "no invented facts / no diagnosis" | RES |
| **Route Builder methodology** | out of scope for Direction Evaluation entirely; its own methodology track when Route Builder is built | RES |

---

## How an item leaves this backlog

1. It is picked up (P1/P2 trigger met, or a P0 opens).
2. Work is done in the appropriate track (S1 = main dev worktree;
   KB = knowledge curation; CAL/methodology = this track).
3. If it changes any methodology *content or number*, it goes through the
   release process (`MNP_LEARNING_AND_FEEDBACK_PROTOCOL_V0.1.md` §5):
   propose → evaluate against authoritative Golden Cases → Methodology
   Owner sign-off → new versioned release. Old runs stay reproducible.
