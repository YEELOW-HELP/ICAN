# MNP Evidence Standard v0.1

> **STATUS: Founder-approved engineering methodology contract v0.1.**
> **NOT a validated psychometric instrument.**
> **Scoring / calibration remains EXPERIMENTAL until evaluated.**

Defines *when the system is allowed to assert something about a person* and
*how confident it is allowed to sound*.

Consumed by: `app/services/direction/confidence.py`,
`app/services/direction/threshold.py`. Complements — does not replace —
Stage 2's already-deterministic `compute_claim_confidence`.

---

## 1. Evidence levels E0–E3

A **level** describes the strength of the support behind a statement.

| Level | Name | Meaning | Allowed use |
|---|---|---|---|
| **E0** | No evidence | An inference with no grounding observation. | **Never** an assertion. In this system E0 cannot exist as an `Evidence` row (every row is source-referenced) and cannot exist as a persisted `ProfileClaim` (Stage 2 drops zero-evidence claims). E0 = "would have to be dropped". |
| **E1** | Weak evidence | A single self-description or one soft signal. E.g. "I think I'm a leader." | May seed a **HYPOTHESIS**. Never on its own reaches `SUPPORTED`. |
| **E2** | Moderate evidence | A concrete described situation, or two consistent soft signals. E.g. the person describes a specific time they organised a team. | May support a claim; corroboration still preferred before `SUPPORTED`. |
| **E3** | Strong evidence | Multiple independent behavioural examples, or CV confirmation, or structured + open answers agreeing, or long tenure. | May support a `SUPPORTED` claim with higher confidence. |

**E0 is not an evidence tier — it is a claim outcome.** The tier scale
that attaches to real support is E1–E3. This matches Stage 2's existing
behaviour: a claim whose only "support" is ungrounded inference is not
persisted (`ClaimStatus.INSUFFICIENT_EVIDENCE` / dropped).

### 1.1 How the level is determined

The level is **computed**, never assigned by an LLM. v0.1 inputs
(available from existing data):

- `Evidence.source_type` (`structured_answer` / `open_answer` / `cv` / `derived`)
- `Evidence.extraction_method` (`deterministic` / `llm_extraction`)
- number of independent evidence items behind the claim
- agreement/among them (Stage 2's `is_contradictory`)

Mapping (v0.1, in `app/services/direction/confidence.py`, all constants in
versioned config):

| condition | level |
|---|---|
| ≥ 2 independent items, ≥ 1 direct (`structured_answer`/`cv`/`deterministic`), no contradiction | E3 |
| exactly 1 direct item, or ≥ 2 consistent `open_answer` items | E2 |
| exactly 1 `open_answer`/`llm_extraction` item | E1 |
| contradiction present | not levelled — handled as CONTRADICTED (§4) |

---

## 2. Confidence is deterministic and auditable

The final confidence value attached to any conclusion is produced by
deterministic code. **An LLM-reported confidence number is never
authoritative** and is never persisted as the value.

### 2.1 Two confidences, kept separate

- **Claim confidence** (Stage 2, `compute_claim_confidence`) — how well an
  individual `ProfileClaim` is grounded.
- **Evidence Confidence** (Stage 3B, `compute_evidence_confidence`) — the
  fourth Direction output: how reliable/sufficient the evidence *and* the
  career knowledge behind Potential Fit / Goal Alignment / Transition
  Feasibility are.

Neither is **Fit**. The three fit outputs are compatibility (Career Fit /
Direction Evaluation Model). Evidence Confidence is
reliability/sufficiency. They are separate fields and separate
calculations and are never multiplied into one number before all are
independently visible.

### 2.2 Evidence-Confidence inputs (v0.1)

Permitted inputs, per Founder decision D:

1. claim evidence strength (E1–E3, §1)
2. claim confidence (Stage 2 value)
3. source diversity (distinct `Evidence.source_type` behind the supporting claims)
4. coverage across the three fit outputs (how many of Potential Fit / Goal
   Alignment / Transition Feasibility produced a non-`None` raw)
5. contradictions (count of `CONTRADICTED` claims among the relevant set)
6. Career KB completeness/provenance (fraction of compared career attributes that were actually curated, not null; presence of `KnowledgeSource` on used facts)

The exact combination formula (additive + bounded, the
`compute_claim_confidence` style) and every coefficient/cutoff live in
`ScoringConfig.thresholds` (`is_experimental = true` for all v0.1
configs). The raw 0..1 value is computed for internal use and **flagged
EXPERIMENTAL** everywhere it appears. See Career Fit / Direction
Evaluation Model §6 for the v0.1 formula.

### 2.3 Public semantics: LOW / MEDIUM / HIGH

Anything a consultant or end user sees uses a **band**, never a precise
percentage:

| band | v0.1 cutoff (config, experimental) |
|---|---|
| HIGH | raw ≥ `confidence_high_cutoff` (default 0.66) |
| MEDIUM | raw ≥ `confidence_medium_cutoff` (default 0.33) |
| LOW | otherwise |

"87.4% confident" is a forbidden phrasing — it implies a precision the
model does not have.

---

## 3. Missing information ≠ negative evidence

If the system has no data for a dimension or a comparison:

- it **reduces confidence / coverage**;
- it marks the affected component `INSUFFICIENT_DATA`;
- it may raise a `ClarificationRequest`;
- it **never** produces a low/zero score as if the person *failed* that
  dimension.

"Unknown" is reported as unknown. It is never quietly converted into "bad
fit".

---

## 4. Contradictions are never silently averaged

Consistent with Stage 2:

- both supporting and contradicting evidence are retained;
- the claim's status is `CONTRADICTED`;
- confidence is driven **down**, never smoothed to a false middle.

Stage 3B additions:

- a `CONTRADICTED` claim is excluded from positive Fit contribution;
- it is surfaced as a **risk/gap** on any direction it is relevant to;
- an important unresolved contradiction is eligible for a
  `ClarificationRequest` (`reason = UNRESOLVED_CONTRADICTION`);
- the Stage 1 assessment state machine is **not** reopened for it in this
  stage (Founder decision M3) — the clarification request is recorded for
  a future mechanism.

---

## 5. Minimum evidence to make a recommendation at all

Direction Intelligence does not produce directions from an
under-evidenced profile. v0.1 threshold (Founder decision H, all values in
versioned config):

- `PotentialProfile` is `READY` and current;
- ≥ 4 `SUPPORTED` claims;
- those supported claims cover ≥ 3 canonical MNP dimensions (via the
  legacy→canonical adapter).

Below threshold ⇒ `DirectionRun.status = INSUFFICIENT_INFORMATION`, plus
`ClarificationRequest`s naming the missing/weak dimensions. The system
does **not** manufacture TOP 3 + Alternative 3 to have something to show.
