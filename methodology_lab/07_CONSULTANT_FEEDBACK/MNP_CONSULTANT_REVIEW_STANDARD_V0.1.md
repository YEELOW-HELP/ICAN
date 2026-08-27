# MNP Consultant Review Standard v0.1

> **STATUS: Founder-approved methodology-operational document v0.1 —
> MVP EXPERIMENTAL BASELINE.**
> **NOT a validated psychometric instrument. Scoring/calibration EXPERIMENTAL.**
> Frozen against `MNP-HPM / Direction Evaluation v0.1`. Does not redefine
> the 12 dimensions or the four-output model.

Defines exactly how a career consultant reviews one `DirectionRun` before
it can become a client report, and how every correction is recorded so it
feeds the controlled learning loop
(`MNP_LEARNING_AND_FEEDBACK_PROTOCOL_V0.1.md`).

**Non-negotiable:** without an `APPROVED` `DirectionReview`, a report is
never shown to a client. The consultant's edits are **append-only
overlays** — the AI original is immutable and always addressable.

---

## 1. Review order (fixed)

Review mirrors the production pipeline, bottom-up — never start from the
directions:

```
A. Profile Claims
      ↓
B. Potential Fit     C. Goal Alignment     D. Transition Feasibility
      ↓
E. Evidence Confidence
      ↓
F. Career Direction placement (MAIN / ALTERNATIVE)
      ↓
G. Constraints & gaps
      ↓
H. Explanation / Narrative
      ↓
RUN-LEVEL DECISION
```

A consultant may not `APPROVE` the run until every A–H item has a
recorded action.

---

## 2. Structured actions

### 2.1 Item-level actions (A–E, G, H)

| action | meaning | leads to |
|---|---|---|
| `ACCEPT` | the item is correct as generated | no correction row |
| `EDIT` | the item is kept but its value/wording is changed | one `ConsultantCorrection` (overlay) |
| `REJECT` | the item is wrong and must be removed / not shown | one `ConsultantCorrection`; item excluded from the report |
| `NEED_MORE_EVIDENCE` | the item cannot be judged — the profile lacks the evidence to confirm or deny it | one `ConsultantCorrection` (`reason_code = other_with_comment` unless a better code fits) + a `ClarificationRequest`; the run cannot be `APPROVED` as-is |

### 2.2 Direction-level actions (F)

| action | meaning | leads to |
|---|---|---|
| `ACCEPT_MAIN` | keep this direction in the MAIN pool at (or near) its rank | no correction row (a rank nudge within MAIN is `MOVE`) |
| `ACCEPT_ALTERNATIVE` | keep this direction in the ALTERNATIVE pool | no correction row |
| `MOVE` | change the direction's pool and/or rank (MAIN↔ALTERNATIVE, or reorder) | one `ConsultantCorrection`, `target_type = RANKING` |
| `REJECT` | this direction must not appear in the report at all | one `ConsultantCorrection`, `target_type = DIRECTION` |
| `NEED_MORE_DATA` | the direction cannot be judged — profile coverage or KB data is too thin | `ConsultantCorrection` + `ClarificationRequest`; run not `APPROVED` as-is |

`MOVE` and `REJECT` never renumber ranks by hand in prose — the consultant
states the target pool/position and the overlay layer recomputes display
order deterministically.

---

## 3. What the consultant checks, per target

### A. Profile Claims

Check each `SUPPORTED` / `HYPOTHESIS` / `CONTRADICTED` claim against the
linked evidence (open the evidence, don't trust the label).

| finding | action | `reason_code` |
|---|---|---|
| claim asserts more than the evidence supports | `EDIT` / `REJECT` | `wrong_inference` |
| evidence clearly supports a claim the system did not make | `EDIT` (add) | `missing_inference` |
| claim is filed under the wrong canonical dimension | `EDIT` | `wrong_dimension` |
| confidence band too high for the evidence tier (E1–E3) | `EDIT` | `overconfidence` |
| confidence band too low | `EDIT` | `underconfidence` |
| two evidence items conflict but no `CONTRADICTED` flag | `EDIT` | `contradiction_missed` |
| the evidence itself was mis-extracted upstream (Stage 2) | `EDIT` / `REJECT` | `evidence_extraction_problem` |
| wording only; the structured claim is fine | `EDIT` | `wording_only` |
| cannot judge — no evidence either way | `NEED_MORE_EVIDENCE` | `other_with_comment` |

### B. Potential Fit / C. Goal Alignment / D. Transition Feasibility

For each output, review the **band**, the **component list**, and the
**coverage ratio** — not a single number.

- Confirm every `SCORED` component's rationale matches the linked claims +
  career attributes.
- Confirm every `INSUFFICIENT_DATA` / `NOT_APPLICABLE` component is
  genuinely unknowable from the profile — **not** something the consultant
  can see is a poor match. If it *is* judgeable and wrong, that is
  `wrong_inference` on the underlying claim, not a fit edit.
- `UNKNOWN ≠ NEGATIVE`: a low coverage ratio is a `NEED_MORE_EVIDENCE`
  situation, never a reason to hand-set the band to `LOW`.

| finding | action | `reason_code` |
|---|---|---|
| a component is `SCORED` but its rationale is not supported by the claims | `EDIT` component | `wrong_inference` |
| a component should have been scorable and was skipped | `EDIT` | `missing_inference` |
| the band is defensible but the consultant would place it one step higher/lower on the same evidence | `EDIT` band + note | `overconfidence` / `underconfidence` |
| the output is `None`/unknown and the consultant agrees it is genuinely unknown | `ACCEPT` (with coverage note) | — |
| the output is `None` because a claim was mis-extracted / mis-mapped | `EDIT` upstream claim | `evidence_extraction_problem` / `wrong_dimension` |

### E. Evidence Confidence

- Confirm the band reflects: evidence tier mix, source diversity,
  contradiction load, coverage across the three fit outputs, KB
  completeness.
- A direction with strong Potential Fit but `LOW` Evidence Confidence is
  **expected** and correct — it means "promising, but we don't know this
  person well enough yet". Do not "fix" it by inflating confidence.

| finding | action | `reason_code` |
|---|---|---|
| band overstates how well the person is understood | `EDIT` | `overconfidence` |
| band understates it (strong, diverse, consistent evidence rated LOW) | `EDIT` | `underconfidence` |
| a contradiction that should have lowered it was missed | `EDIT` | `contradiction_missed` |

### F. Career Direction placement

- Confirm no `BLOCKED` direction appears in MAIN or ALTERNATIVE.
- Confirm the MAIN/ALTERNATIVE split follows the lexicographic
  RankingPolicy (Potential Fit → Goal Alignment → Transition Feasibility →
  Evidence Confidence, `None` last) and that any consultant reorder is a
  deliberate, noted judgement.
- Confirm pools were **not padded** — fewer than 3+3 is acceptable.

| finding | action | `reason_code` |
|---|---|---|
| a direction is ranked too high / too low | `MOVE` | `wrong_direction_priority` |
| a direction should not be shown to this client at all | `REJECT` | `wrong_direction_priority` (or `career_knowledge_problem` if the KB entry is the cause) |
| a `BLOCKED` career leaked into MAIN/ALTERNATIVE | `REJECT` + escalate | `constraint_missed` |
| a strong direction is missing entirely (should have been a candidate) | `NEED_MORE_DATA` + note | `career_knowledge_problem` |

### G. Constraints & gaps

- Review each `ProfileConstraint`: correct subtype (one of the 12), correct
  `hard`/`soft`, correct `confirmed` flag.
- Review `DirectionConstraintCheck` rows: every `BLOCK` must trace to a
  confirmed hard constraint × a `HARD_FACTUAL` career requirement.
- Review `skills_to_verify` (UNKNOWN required skills) — confirm these are
  genuine information gaps, not confirmed gaps.

| finding | action | `reason_code` |
|---|---|---|
| a real constraint (hard or soft) is not represented | `EDIT` (add `ProfileConstraint`) | `constraint_missed` |
| a constraint is mis-typed or wrongly marked hard/soft/confirmed | `EDIT` | `constraint_missed` |
| the career requirement backing a `BLOCK` is not actually authoritative | `EDIT` (clear the block) | `career_knowledge_problem` |
| an `UNKNOWN` skill is actually confirmed-missing (client stated it) | `EDIT` (reclassify) + note | `missing_inference` |

### H. Explanation / Narrative

> In Slice 1 there is no LLM narrative yet. This section applies once the
> narrative generator ships; until then the consultant reviews the
> deterministic explanation bundle only.

- Confirm the narrative references only claims / fit components / KB facts
  that actually exist in the run.
- Confirm no invented salary / demand / credential / institution fact.
- Confirm no diagnosis, no guarantee, no clinical language.
- Confirm `CONTRADICTED` / `LOW`-confidence items are phrased tentatively.

| finding | action | `reason_code` |
|---|---|---|
| narrative asserts a fact not in the structured inputs | `EDIT` / `REJECT` | `unsupported_fact` |
| tone / phrasing only; substance is fine | `EDIT` | `wording_only` |
| narrative contradicts the actual scores | `EDIT` | `wrong_inference` |

---

## 4. Correction → reason-code map (complete)

Every `ConsultantCorrection` carries exactly one `reason_code` from the
closed set (`MNP_LEARNING_AND_FEEDBACK_PROTOCOL_V0.1.md` §4). Quick map:

| reason_code | typical target(s) |
|---|---|
| `wrong_inference` | Profile Claim, fit component, narrative-vs-score mismatch |
| `missing_inference` | Profile Claim (add), skipped scorable component, skill reclassification |
| `wrong_dimension` | Profile Claim mis-filed |
| `overconfidence` | claim confidence, any output band, Evidence Confidence |
| `underconfidence` | claim confidence, any output band, Evidence Confidence |
| `contradiction_missed` | Profile Claim, Evidence Confidence |
| `constraint_missed` | `ProfileConstraint`, a leaked `BLOCKED` direction |
| `unsupported_fact` | narrative, career fact used in a direction |
| `wrong_direction_priority` | direction rank / pool (`MOVE`), direction shown at all (`REJECT`) |
| `career_knowledge_problem` | KB entry wrong/incomplete (surfaced via a direction or a block) |
| `evidence_extraction_problem` | claim whose *evidence* was mis-extracted upstream |
| `wording_only` | narrative / claim label phrasing |
| `other_with_comment` | anything else; `reason_note` mandatory; used for most `NEED_MORE_EVIDENCE` / `NEED_MORE_DATA` |

---

## 5. Run-level decision (roll-up)

| condition across A–H | `DirectionReview` outcome |
|---|---|
| every item `ACCEPT`, or `EDIT`s that are cosmetic (`wording_only`) only | **APPROVE** |
| substantive `EDIT`s exist but no `REJECT`, no `NEED_MORE_*`, and the corrected run is coherent | **APPROVE** (overlay applied) |
| any `NEED_MORE_EVIDENCE` / `NEED_MORE_DATA` on a MAIN direction or on ≥ 2 dimensions | **REQUEST_CHANGES** → regenerate or collect clarification |
| any `REJECT` that removes a MAIN direction and leaves < 2 MAIN | **REQUEST_CHANGES** → regenerate |
| a `BLOCKED` career leaked into MAIN/ALT, or an invented market fact, or diagnosis/guarantee language | **REJECT** + escalate to Methodology Owner |
| the run is `INSUFFICIENT_INFORMATION` and the consultant agrees | close as `INSUFFICIENT_INFORMATION`; send clarification set to the client, no report |

`REQUEST_CHANGES` never edits the run destructively — a regeneration
produces a **new** `DirectionRun`/version, which gets its own review.

---

## 6. "Major correction" (feeds pilot metrics)

A **major correction** = any `ConsultantCorrection` with `reason_code` in
`{wrong_inference, missing_inference, wrong_dimension, contradiction_missed,
constraint_missed, unsupported_fact, wrong_direction_priority}` **or** any
`REJECT` / `MOVE` on a MAIN direction. `wording_only` and single-step
`overconfidence`/`underconfidence` band nudges are **minor**.

This split is the numerator for `Major Correction Rate`
(`MNP_PILOT_EVALUATION_PROTOCOL_V0.1.md`).

---

## 7. MVP time budget (guidance, not a rule)

Target ≤ 25–35 minutes per `DirectionRun` review for the pilot. If a
review consistently exceeds this, that is itself a finding — record it as
`other_with_comment` on the run with a note, and it feeds the methodology
backlog (usability of the review surface).
