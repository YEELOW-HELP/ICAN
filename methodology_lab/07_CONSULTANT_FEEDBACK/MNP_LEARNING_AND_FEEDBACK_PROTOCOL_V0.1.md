# MNP Learning & Feedback Protocol v0.1

> **STATUS: Founder-approved engineering methodology contract v0.1.**
> **NOT a validated psychometric instrument.**
> **Scoring / calibration remains EXPERIMENTAL until evaluated.**

Defines how a consultant's correction turns into an *improvement of the
system* — safely, without a single edit ever silently changing
methodology.

Consumed by (Slice 2+): `app/services/review/*`. This document is binding
now so the tables and reason codes are built once, correctly.

---

## 1. Two contours (never merged)

**Production МОЖУ:**
`Assessment → Evidence → Profile → Directions → Critic → Consultant Review → Report`

**МОЖУ Methodology Lab (closed):**
`Production cases → Consultant corrections → Structured feedback dataset →
Error analysis → Candidate methodology change → Evaluation → Human approval
→ New methodology release`

Production only ever runs a **released** methodology version
(`mnp-hpm:v0.1`, then `v0.2`, …). A single consultant comment never edits
production methodology.

**Forbidden:** `consultant correction → automatic methodology
modification`. There is no code path from a `ConsultantCorrection` row to a
change in `methodology_lab/*`, `dimensions.py`, `dimension_mapping.py`, or
any `ScoringConfig`.

---

## 2. Consultant actions

A consultant may **approve / correct / reject / comment** on a
`DirectionRun`.

- **Approve** — the run may proceed to a report.
- **Reject** — the run is unusable; regeneration required.
- **Request changes** — preserves immutable history; resolved either by a
  regeneration (new `DirectionRun`/version) or by approved correction
  overlays (Founder decision M4).
- **Correct** — records a structured `ConsultantCorrection`.

The original AI artifact is **immutable**. A correction is an **append-only
overlay**, never a destructive update. The report/read surface applies
approved corrections as an overlay and always keeps the AI original
addressable.

---

## 3. `ConsultantCorrection` — structure

Persisted (Slice 2): `id`, `review_id`, `run_id`, `target_type`
(`DIRECTION` / `FIT_COMPONENT` / `CONSTRAINT_CHECK` / `NARRATIVE` /
`RANKING`), `target_id`, `field`, `original_value` (JSON),
`corrected_value` (JSON), `reason_code`, `reason_note`, `reviewer_admin_id`,
`methodology_version`, `knowledge_base_version_id`, `scoring_config_id`,
`model`, `prompt_version`, `created_at`.

Copying the version fields at creation keeps a correction interpretable
after configs move on.

---

## 4. Reason codes — exactly this closed set (Founder decision K)

| code | when |
|---|---|
| `wrong_inference` | the system inferred something the evidence does not support |
| `missing_inference` | the system missed an inference the evidence does support |
| `wrong_dimension` | the claim/observation was filed under the wrong canonical dimension |
| `overconfidence` | confidence band too high for the evidence |
| `underconfidence` | confidence band too low for the evidence |
| `contradiction_missed` | a real contradiction in the evidence was not flagged |
| `constraint_missed` | a real (possibly hard) constraint was not represented |
| `unsupported_fact` | a career fact / market claim without adequate support |
| `wrong_direction_priority` | a direction is ranked too high or too low |
| `career_knowledge_problem` | the Career Knowledge Base entry itself is wrong/incomplete |
| `evidence_extraction_problem` | Stage 2 extracted evidence incorrectly upstream |
| `wording_only` | phrasing/tone only; the underlying structured conclusion is fine |
| `other_with_comment` | none of the above; `reason_note` is mandatory |

No other codes. `other_with_comment` requires a non-empty `reason_note`.

---

## 5. The learning loop (controlled)

1. **Collect** — approved `ConsultantCorrection` rows accumulate into a
   structured feedback dataset (append-only, versioned by
   `methodology_version`).
2. **Analyse** — periodically, patterns are examined (e.g. "`overconfidence`
   on `career_adaptability_fit` in N% of reviews"). The **first** output
   is never "change v0.1 → v0.2" — it is "flag for methodology review +
   pull a sample for inter-rater checking".
3. **Propose** — a candidate methodology change is written as a diff to
   `methodology_lab/*` and/or a new `ScoringConfig`.
4. **Evaluate** — the candidate is run against the Golden Cases
   (Evaluations v0.1) and compared to the current baseline.
5. **Approve** — the Methodology Owner signs off. Only then.
6. **Release** — a new methodology version / a new non-experimental
   `ScoringConfig` is published. Old runs keep their old versions and stay
   reproducible.

Consultant corrections are **evidence for** step 2. They are never step 6.

---

## 6. Guard against consultant drift

Two consultants may correct in opposite directions. Before any correction
*pattern* is acted on, a double-rated sample must show acceptable
inter-rater agreement. A correction that is itself a judgement call (not
evidence-backed) is recorded as such, so analysis can distinguish "the
system was wrong" from "a consultant disagreed stylistically".

---

## 7. Client feedback (recorded for later, not built in Stage 3B)

Immediate ("how well does this describe you?" 1–5; 👍/👎 per section),
30/90-day, and 6–12-month outcome check-ins feed the same
Methodology-Lab analysis at step 2. Not implemented in Stage 3B; recorded
here so the loop is understood end to end.
