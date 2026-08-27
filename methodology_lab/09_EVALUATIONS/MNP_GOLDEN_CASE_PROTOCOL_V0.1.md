# MNP Golden Case Protocol v0.1

> **STATUS: Founder-approved methodology-operational document v0.1 —
> MVP EXPERIMENTAL BASELINE.**
> **NOT a validated psychometric instrument. Scoring/calibration EXPERIMENTAL.**

Defines the standard template and the review lifecycle for a **future
authoritative Golden Case**. Complements `MNP_EVALUATIONS_V0.1.md` (which
defines *what* a Golden Case is); this document defines *how one is
authored, reviewed, and approved*.

**Synthetic engineering fixtures remain explicitly NON-authoritative.**
Files under `evals/golden/v1/scenario_generation/` and anything in
`tests/` are engineering fixtures proving the mechanism — they are never
scientific ground truth, regardless of how realistic they look. Only a
case that has completed the lifecycle in §2 is authoritative.

---

## 1. What an authoritative Golden Case is for

- It is the reference the methodology-release process
  (`MNP_EVALUATIONS_V0.1.md` §4) evaluates a candidate `v0.2` against.
- It is **not** a CI gate on every commit (real model calls cost money and
  are non-deterministic — same reasoning as `evals/golden/README.md`).
- It encodes expert consensus on: which claims a correct profile must
  contain, which directions are acceptable, which are unacceptable, and
  why.

Pilot target: **20–30 authoritative cases** covering the segments in
`docs/architecture/04_AI_SYSTEM.md` (18–24 first career, 25–35 change,
35–50 transition, low-information, contradictory answers, strict
constraints, UA/EN language).

---

## 2. Lifecycle (a case is authoritative only at the end)

```
DRAFT
  → author writes the case from a de-identified real or synthetic-but-realistic input
REVIEWER 1  (career consultant / expert)
  → independently fills expected claims / directions / constraints WITHOUT seeing reviewer 2
REVIEWER 2  (a different career consultant / expert)
  → independently fills the same
CONSENSUS
  → the two reviewers reconcile disagreements; unresolved points become "ambiguity notes",
    not forced agreement
METHODOLOGY OWNER APPROVAL
  → signs off that the consensus is coherent with the v0.1 canon
AUTHORITATIVE  (status: approved, immutable — a correction is a new case id)
```

- Reviewers 1 and 2 must be different people and must fill the expected
  fields **independently** before seeing each other's answers — this is
  what makes inter-rater agreement measurable.
- A case with an unresolved substantive disagreement is **not** discarded
  — it is approved with the disagreement recorded under "ambiguity notes"
  and flagged as a low-confidence case (still usable, weighted lower in
  release evaluation).
- No sign-off ⇒ `status: draft`, gates nothing.

---

## 3. De-identification (mandatory)

Reuses `evals/golden/README.md`'s anonymization rules:

- No real name, phone, email, handle, employer, or identifying
  combination of city + role + timeframe.
- Replace with synthetic-but-plausible equivalents (a fictional city of
  similar size/region is fine; the real one is not).
- `deidentification_notes` must state what was changed from the source.
- When in doubt, rewrite fully synthetic ("inspired by a pattern", not
  traceable to a person). A `consented-anonymized` case additionally
  requires documented consent from that person.

---

## 4. Template

One case = one file, `evals/golden/v1/scenario_generation/<case_id>.json`
(engineering owns the file location; methodology owns the content
standard). The methodology-facing fields:

```yaml
case_id: gc_<segment>_<nnn>            # stable, never reused
status: draft | approved | retired
provenance:
  type: synthetic | consented-anonymized
  deidentification_notes: "<what was changed from the source>"
segment: first_career_18_24 | career_change_25_35 | transition_35_50 |
         low_information_user | contradictory_answers | strict_constraints |
         language_variant | other
locale: uk | en | mixed
methodology_version: "mnp-hpm:v0.1"

# --- INPUT (de-identified) ---
input:
  assessment_answers: [ ... structured + open answers, de-identified ... ]
  cv_text: "<de-identified CV text, or null>"
  evidence_notes: "<optional: what a correct Evidence extraction should surface>"

# --- EXPECTED PROFILE ---
required_claims:                       # claims a correct profile MUST contain
  - dimension: <canonical MNP dimension>
    subdimension: <or null>
    normalized_value: "<statement>"
    min_status: supported | hypothesis
unacceptable_claims:                   # claims a correct profile MUST NOT contain (with reason)
  - normalized_value: "<statement>"
    reason: "<why it is unsupported / wrong>"

# --- EXPECTED DIRECTIONS ---
acceptable_main_directions: [ <career_code | domain>, ... ]
acceptable_alternative_directions: [ <career_code | domain>, ... ]
unacceptable_directions:
  - direction: <career_code | domain>
    reason: "<why this must not be surfaced for this person>"

# --- CONSTRAINTS ---
hard_constraints:
  - subtype: <one of the 12>            # time|financial|geography|mobility|work_schedule|
                                        # work_format|language|education|credential|legal|
                                        # family_logistics|functional
    normalized_value: "<statement>"
    expected_blocks: [ <career_code>, ... ]   # careers the hard gate must BLOCK (given HARD_FACTUAL KB data)
soft_constraints:
  - subtype: <one of the 12>
    normalized_value: "<statement>"
    expected_effect: "trade-off note / feasibility consideration"

# --- EXPECTED REASONING ---
expected_reasoning_characteristics:
  - "cites the specific claims behind each MAIN direction"
  - "names the coverage gaps (which fit outputs are unknown) explicitly"
  - "distinguishes Potential Fit from Evidence Confidence"
  - "does not assert any market/credential fact not present in the KB"
expected_insufficient_information: false   # true if the profile is below the minimum threshold

ambiguity_notes:
  - "<point the two reviewers could not fully agree on, kept as an open question>"

# --- REVIEW TRAIL ---
reviewer_1: { role: "career consultant", name_or_id: "<...>", date: "YYYY-MM-DD",
              agreement_with_r2: full | partial | low }
reviewer_2: { role: "career consultant", name_or_id: "<...>", date: "YYYY-MM-DD" }
consensus:  { date: "YYYY-MM-DD", unresolved_points: [ ... ] }
methodology_owner_approval: { name_or_id: "<...>", date: "YYYY-MM-DD",
                              case_confidence: high | low }
```

---

## 5. Retirement, not deletion

A case that no longer reflects the current methodology is set
`status: retired` — it stays in the historical record and stays
reproducible against its own `methodology_version`. Delete only for a
real-data incident (`evals/golden/README.md` "Governance").

---

## 6. Ownership

- **Author:** anyone (engineering or methodology) may draft.
- **Reviewers 1 & 2:** career consultants / domain experts, independent.
- **Approval:** Methodology Owner only.
- **File maintenance / schema:** engineering (`evals/golden/schema.json`).
