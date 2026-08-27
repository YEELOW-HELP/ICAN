# MNP Pilot Evaluation Protocol v0.1

> **STATUS: Founder-approved methodology-operational document v0.1 —
> MVP EXPERIMENTAL BASELINE.**
> **NOT a validated psychometric instrument. Scoring/calibration EXPERIMENTAL.**

Defines the metrics that tell us whether `MNP-HPM / Direction Evaluation
v0.1` is **safe and useful enough** to keep running the pilot, and what
data feeds each. These are **operational health metrics**, not scientific
validity claims.

Every metric here is computed from data the system already records or the
consultant workspace records during review — no new production code is
required to *define* them (collection surfaces are Slice 2+).

---

## 1. Data sources

| source | what it provides |
|---|---|
| `DirectionReview` (per run) | outcome: `APPROVED` / `CHANGES_REQUESTED` / `REJECTED` / closed-`INSUFFICIENT_INFORMATION` |
| per-item review actions (A–H, Consultant Review Standard §2) | `ACCEPT` / `EDIT` / `REJECT` / `NEED_MORE_EVIDENCE`; `ACCEPT_MAIN` / `ACCEPT_ALTERNATIVE` / `MOVE` / `REJECT` / `NEED_MORE_DATA` |
| `ConsultantCorrection` rows | `target_type`, `field`, `reason_code`, `reason_note`, before/after |
| `DirectionCriticFinding` (Slice 2+) | deterministic `BLOCKER` / `WARNING` findings |
| `DirectionRun.status` | `READY` / `INSUFFICIENT_INFORMATION` / `FAILED` |
| Client survey | Profile Recognition, Direction Relevance, Report Helpfulness (1–5) |

"**Reviewed**" = a `DirectionReview` reached a terminal outcome
(`APPROVED` / `REJECTED` / closed). Runs still in review are excluded from
all denominators.

---

## 2. System metrics

> Each row: **numerator / denominator**, then the data source and the MVP
> alarm threshold. An alarm threshold is a *stop-and-review* trigger for
> the Methodology Owner, not an automatic pass/fail.

### 2.1 Profile Claim Acceptance Rate
- **Numerator:** count of profile claims with action `ACCEPT`.
- **Denominator:** count of profile claims presented for review across all reviewed runs.
- Source: per-item actions on target A.
- Alarm: **< 0.60** (too many claims wrong → evidence/claim pipeline unreliable).

### 2.2 Profile Claim Correction Rate
- **Numerator:** count of profile claims with action `EDIT` **or** `REJECT`.
- **Denominator:** count of profile claims presented for review.
- Source: per-item actions on target A. (2.1 + 2.2 + `NEED_MORE_EVIDENCE` share ≈ 1.)
- Alarm: **> 0.35**.

### 2.3 Unsupported Claim Rate
- **Numerator:** count of profile claims with action `REJECT` and `reason_code ∈ {wrong_inference, unsupported_fact}`.
- **Denominator:** count of profile claims presented for review.
- Source: `ConsultantCorrection` filtered to `target_type` claim-level.
- Alarm: **> 0.05** (the system is asserting things the evidence does not support — a safety concern).

### 2.4 Contradiction Miss Rate
- **Numerator:** count of `ConsultantCorrection` rows with `reason_code = contradiction_missed`.
- **Denominator:** count of reviewed runs.
- Source: `ConsultantCorrection`.
- Alarm: **> 0.15 per run** (contradictions are being silently resolved somewhere upstream).

### 2.5 Direction Acceptance Rate
- **Numerator:** count of directions with action `ACCEPT_MAIN` **or** `ACCEPT_ALTERNATIVE`.
- **Denominator:** count of directions presented for review (MAIN + ALTERNATIVE pools) across reviewed runs.
- Source: per-item actions on target F.
- Alarm: **< 0.55**.

### 2.6 TOP Direction Acceptance Rate
- **Numerator:** count of reviewed runs whose **rank-1 MAIN** direction received `ACCEPT_MAIN` and was **not** `MOVE`d or `REJECT`ed.
- **Denominator:** count of reviewed runs that produced ≥ 1 MAIN direction.
- Source: per-item actions on target F + rank data.
- Alarm: **< 0.50** (the single most-prominent recommendation is wrong half the time).

### 2.7 Direction Replacement Rate
- **Numerator:** count of directions with action `REJECT` (removed from the report entirely).
- **Denominator:** count of directions presented for review (MAIN + ALTERNATIVE).
- Source: per-item actions + `ConsultantCorrection` `target_type = DIRECTION`.
- Alarm: **> 0.25**.

### 2.8 Hard Constraint Violation Rate
- **Numerator:** count of reviewed runs where a career the hard gate should have `BLOCK`ed (confirmed hard constraint × `HARD_FACTUAL` requirement) appeared in MAIN or ALTERNATIVE — caught by the consultant (`constraint_missed` on a direction) **or** by a deterministic critic `BLOCKER`.
- **Denominator:** count of reviewed runs.
- Source: `ConsultantCorrection` (`reason_code = constraint_missed`, direction target) + `DirectionCriticFinding` (`check_key = hard_constraint_violation`).
- Alarm: **> 0.00** — **any** occurrence is a stop-the-pilot event. This is the one metric with a zero tolerance.

### 2.9 Major Correction Rate
- **Numerator:** count of reviewed runs with ≥ 1 **major correction** (Consultant Review Standard §6: `reason_code ∈ {wrong_inference, missing_inference, wrong_dimension, contradiction_missed, constraint_missed, unsupported_fact, wrong_direction_priority}`, or a `REJECT`/`MOVE` on a MAIN direction).
- **Denominator:** count of reviewed runs.
- Source: `ConsultantCorrection` + per-item actions.
- Alarm: **> 0.60** (most runs need substantive rework → the baseline is not pilot-usable).

### 2.10 Narrative Correction Rate
- **Numerator:** count of `ConsultantCorrection` rows with `target_type = NARRATIVE`.
- **Denominator:** count of reviewed runs that included a generated narrative.
- Source: `ConsultantCorrection`.
- Status: **not measured until the narrative generator ships** — record as `N/A (narrative not built)`.
- Alarm (once live): **> 0.40**.

---

## 3. Client metrics

Collected via the immediate post-report survey (`MNP_LEARNING_AND_FEEDBACK_PROTOCOL_V0.1.md` §7).

### 3.1 Profile Recognition (1–5)
- **Numerator:** sum of client answers to "How well does this profile describe you?" (1 = not at all … 5 = very well).
- **Denominator:** count of clients who answered that question.
- Reported as a **mean** plus the distribution.
- Alarm: **mean < 3.5** or **≥ 25% answering 1–2**.

### 3.2 Direction Relevance (1–5)
- **Numerator:** sum of client answers to "How relevant are these directions to you?".
- **Denominator:** count of clients who answered.
- Alarm: **mean < 3.5** or **≥ 25% answering 1–2**.

### 3.3 Report Helpfulness (1–5)
- **Numerator:** sum of client answers to "How helpful was this report for your next step?".
- **Denominator:** count of clients who answered.
- Alarm: **mean < 3.5**.

---

## 4. Reporting cadence

| milestone | what is produced |
|---|---|
| **every 10 reviewed runs** | a short numbers-only snapshot of all §2 metrics; flag any alarm immediately |
| **first 20–50 runs** | full report: §2 + §3, per-segment breakdown, top `reason_code`s by frequency, inter-rater agreement on the double-rated subset, methodology-backlog re-prioritisation (`MNP_METHODOLOGY_BACKLOG_V0.2.md`) |
| **100+ runs** | trend view across the pilot; decision input for whether `v0.2` calibration work is warranted |
| **immediately** | any 2.8 (Hard Constraint Violation) occurrence, or two consecutive 10-run snapshots with the same non-2.8 alarm |

---

## 5. What these metrics do NOT claim

- They do **not** establish that the 12 dimensions or the four-output
  model are psychometrically valid.
- They do **not** replace the authoritative Golden Case process
  (`MNP_GOLDEN_CASE_PROTOCOL_V0.1.md`) for methodology-release decisions.
- A green dashboard means "safe and useful enough to keep piloting", not
  "validated".

---

## 6. Ownership

- **Dashboard / collection:** engineering (surfaces built in Slice 2+).
- **Metric definitions (this document):** Methodology track.
- **Alarm response / go-no-go on continuing the pilot:** Founder /
  Methodology Owner.
