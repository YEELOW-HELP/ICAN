# MNP Ranking Policy v0.1

> **STATUS: Founder-approved engineering methodology contract v0.1.**
> **EXPERIMENTAL. NOT calibrated.**
> **Ranking is a SEPARATE versioned decision layer — it is NOT part of
> the definition of Potential Fit, and it does NOT define a hidden
> composite career score (Founder decisions A + G + O).**

Governs `app/services/direction/ranking.py` and the `RankingPolicy`
entity. Version: `RANKING_POLICY_VERSION = "mnp-ranking-policy:v0.1"`.

---

## 1. What a RankingPolicy is

A versioned decision policy that turns the four independent outputs
(Potential Fit, Goal Alignment, Transition Feasibility, Evidence
Confidence — each a band + an experimental raw + coverage) plus the hard
constraint gate result into a MAIN pool, an ALTERNATIVE pool, and an
order within each.

It defines: eligibility rules; qualitative band gates; lexicographic sort
precedence; tie-breakers; MAIN maximum; ALTERNATIVE maximum; missing-output
semantics; evidence-confidence requirements; dedup/diversity rules;
`is_experimental`; `methodology_version`.

It does **not**: compute a blended score; weight the four outputs into one
number; alter any output; or belong inside the scoring engine.

---

## 2. RankingPolicy v0.1 — the rules (Founder decision A)

### 2.1 Eligibility — hard constraint gate

A direction whose hard constraint gate produced a `BLOCK` (confirmed hard
constraint × `HARD_FACTUAL` career fact) is **excluded from all
recommendation eligibility**. It appears in the run as
`placement = BLOCKED` with its explanation, never in MAIN or ALTERNATIVE.

### 2.2 MAIN eligibility

A direction may enter the MAIN pool when **all** hold:

| gate | rule |
|---|---|
| hard gate | `PASS` (no confirmed hard BLOCK) |
| Potential Fit | band `≥ MEDIUM` |
| Goal Alignment | band `≠ LOW` **when known**; `unknown` (raw `None`) is allowed but records a coverage warning |
| Transition Feasibility | band `≠ LOW` **when known**; `unknown` allowed + coverage warning |
| Evidence Confidence | band `≥ MEDIUM` |

**Unknown Goal Alignment / Transition Feasibility is NOT equivalent to
`LOW`.** It does not disqualify a MAIN candidate. It reduces
coverage/confidence and surfaces a `ClarificationRequest` /
`DirectionCriticFinding(WARNING)`.

### 2.3 MAIN ordering — lexicographic, no composite

Sort MAIN-eligible directions by, in strict precedence:

1. Potential Fit raw — **DESC**
2. Goal Alignment raw — **DESC**, `None` sorts **last**
3. Transition Feasibility raw — **DESC**, `None` sorts **last**
4. Evidence Confidence raw — **DESC**
5. `career_code` — **ASC** (final deterministic tie-breaker)

No step combines values into a single number.

### 2.4 ALTERNATIVE pool

A non-MAIN, non-BLOCKED direction may enter ALTERNATIVE when:

- hard gate `PASS`; and
- Potential Fit band `≥ MEDIUM`.

An ALTERNATIVE may carry `LOW` Goal Alignment or `LOW` Transition
Feasibility — this is recorded as an explicit **trade-off** on the
direction, surfaced to the reviewer/report. ALTERNATIVE ordering uses the
same lexicographic rule as §2.3.

### 2.5 Pool sizes — never pad

`MAIN maximum = 3`, `ALTERNATIVE maximum = 3`. If fewer credible
directions exist, **return fewer** — 2 MAIN + 2 ALTERNATIVE returns 4,
never a manufactured 3 + 3. A direction is "credible" only if it passes
the eligibility rules above.

### 2.6 Missing-output semantics

- A `None` raw / `None` band on Goal Alignment or Transition Feasibility
  means "unknown", handled per §2.2 (allowed for MAIN, warned).
- A `None` Potential Fit or Evidence Confidence band **fails** MAIN and
  ALTERNATIVE eligibility (these two are required to be known and
  `≥ MEDIUM`).

### 2.7 Evidence-confidence requirement

MAIN requires `Evidence Confidence ≥ MEDIUM`. A direction with strong
Potential Fit but `LOW` Evidence Confidence is not a MAIN recommendation
in v0.1 — it may still appear as an ALTERNATIVE (if Potential Fit
`≥ MEDIUM`) flagged "we don't yet know this person well enough".

### 2.8 Dedup / diversity

v0.1 has **no numeric similarity threshold** (Founder decisions I + J).
Near-duplicate directions and low domain diversity are **critic
WARNINGS**, not a re-rank and not a silent drop. The RankingPolicy
records the warning; it never removes a direction for diversity.

### 2.9 Versioning

`RankingPolicy.is_experimental = true` for v0.1. `methodology_version`
pinned. A `DirectionRun` stamps `ranking_policy_id` +
`ranking_policy_version`. A policy is immutable once referenced by a run.

---

## 3. What ranking never does

- never mutates Potential Fit / Goal Alignment / Transition Feasibility /
  Evidence Confidence;
- never produces a single public percentage;
- never pads a pool to a target size;
- never blocks a career (only the hard gate does);
- never overrides the hard gate.
