# MNP Methodology → Technical Debt Recommendation v0.1

> **STATUS: recommendation from the Methodology track to the Technical
> Debt Register owner (Tech Lead + Methodology Lead).**
> This document does **not** edit `docs/engineering/11_TECHNICAL_DEBT_REGISTER.md`
> or any production code. It records what the Methodology track believes
> the register should now say, for the owner to accept and apply.

---

## Item 11 — "Versioned taxonomy architecture not yet specified"

Register today: **PARTIALLY RESOLVED** (architecture specified, content
still open; Severity High; blocks R1; owner: Methodology Lead for content).

### Recommended new status

> **RESOLVED FOR MVP v0.1** — the versioned taxonomy architecture plus
> enough Founder-approved content to run the pilot now exists and is
> under version control.
> **OPEN FOR VALIDATION / CALIBRATION v0.2+** — the enumerated
> sub-taxonomies (Strengths, Interests, Values, Motivation), subdimensions
> for 9 of the 12 dimensions, and all numeric calibration remain open and
> are tracked in `MNP_METHODOLOGY_BACKLOG_V0.2.md`.

### What now exists (was the blocker)

| Register concern | Delivered by v0.1 |
|---|---|
| dimension content | 12 canonical dimensions, Founder-frozen, as `CanonicalDimension` (`app/services/direction/dimensions.py`) + `methodology_lab/02_HUMAN_POTENTIAL_MODEL/MNP_HUMAN_POTENTIAL_MODEL_V0.1.md` |
| work preferences | split into **Work Style** (10 subdimensions, fully enumerated) + **Work Environment** (5 matchable facets) |
| constraints | **12-subtype constraint taxonomy**, versioned (`mnp-constraint-taxonomy:v0.1`) |
| evidence types | **E0–E3** evidence levels + deterministic classification (`MNP_EVIDENCE_STANDARD_V0.1.md` §1) |
| profile claim types | `ClaimStatus` (supported / hypothesis / contradicted / insufficient_evidence) — already in Stage 2, unchanged |
| skills | `skills` taxonomy (~36 terms) from Stage 3A |
| career taxonomy | `CareerDomain` (16) from Stage 3A |
| traceability of a generated claim to the taxonomy version that produced it | `PROFILE_CLAIM.taxonomy_version_id` (Stage 2) + `DirectionRun` stamps 8 version strings + the versioned legacy→canonical adapter (`legacy-to-mnp:v0.1`) |
| "no single permanent frozen taxonomy" | every layer is versioned: `TaxonomyVersion`, `ScoringConfig`, `RankingPolicy`, and the `methodology_lab/*` docs are `v0.1` with a defined release process |

The Stage 2 `potential_dimensions` seed (~32 terms, historically labelled
"not final methodology") is **superseded for Stage 3B purposes** by the
canonical model + the versioned adapter — Stage 3B never depends on that
seed being the final vocabulary.

### What stays open (does not block the pilot)

- **Strengths / Interests / Values / Motivation** are canonical
  *dimensions* but have **no enumerated term taxonomy** — claims attach at
  the dimension level. Backlog P1/P2.
- **Subdimensions for 9 of the 12 dimensions** (all except Work Style,
  Work Environment, Constraints). Backlog P2.
- **Calibration** of every experimental number (band cutoffs, component
  weights, confidence coefficients). Backlog P1 (confidence) / P2
  (weights).
- **Abilities & Learning Potential** has no assessment source at all
  (`MNP_ASSESSMENT_GAP_MAP_V0.1.md` #4). Backlog P2.

### Why "RESOLVED FOR MVP" is defensible

R1's deliverable is an *evidence-linked, auditable* Direction pipeline —
not a psychometrically validated one. The v0.1 canon + code produce
evidence-linked claims across a fixed, versioned dimension set, map them
deterministically to four separate outputs, and **say "we don't know"
(`INSUFFICIENT_DATA` / `NEED_MORE_EVIDENCE`) wherever the taxonomy content
is thin** rather than guessing. That is enough to run a supervised pilot
with mandatory consultant review. It is explicitly **not** enough to drop
the "EXPERIMENTAL" label or make calibrated claims — hence the second half
of the status.

### Suggested register field updates

- **Status:** `RESOLVED FOR MVP v0.1 / OPEN FOR VALIDATION-CALIBRATION v0.2+`
- **Severity:** High → **Medium** (no longer blocks R1's engineering
  deliverable; remaining work is calibration + enrichment, not a spec gap)
- **Current evidence:** add a pointer to `methodology_lab/` and
  `app/services/direction/{dimensions,dimension_mapping,constraints}.py`
- **Owner role:** Methodology Lead (validation/calibration, ongoing) +
  Tech Lead (schema, done)
- **When must be resolved:** the *content-completeness* part is now a
  post-pilot calibration effort, not a pre-R1 blocker

---

## Item 16 — "`AI_TRACE` not persisted in production"

Register today: **open, Severity Low, "not urgent while call volume is
low", owner AI Engineer / Backend.**

### Recommendation: **keep OPEN, no change**

This is now also a **binding Founder decision** on the Stage 3B side:
`MNP_FOUNDER_METHODOLOGY_CONTRACT_V0.1.md` §2B (superseding Wave A
decision M2) — Stage 3B Slice 1 introduces **no** `ai_traces` table and
**no** `AITrace` model; only safe string trace / prompt / model / version
identifiers are stored on `DirectionRun`. Full persisted `AI_TRACE` is
deferred to a separate, dedicated architecture decision (store, retention,
cost).

Suggested register note: cross-reference the contract §2B so the two
documents agree, and record that Stage 3B **deliberately** did not resolve
this by side effect.

---

## Not in scope of this recommendation

- Items 1–10, 12–15 — outside the Methodology track.
- Any edit to `docs/engineering/11_TECHNICAL_DEBT_REGISTER.md` itself —
  that is the register owner's action; this document is the input.
