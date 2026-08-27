# MNP Evaluations v0.1

> **STATUS: Founder-approved engineering methodology contract v0.1.**
> **NOT a validated psychometric instrument.**
> **Scoring / calibration remains EXPERIMENTAL until evaluated.**

Defines the difference between an engineering fixture and an authoritative
Golden Case, and how a Golden Case earns authority.

---

## 1. Two kinds of test data (never confused)

### 1.1 Engineering fixtures (`evals/golden/v1/scenario_generation/`, `tests/`)

- `provenance.type: synthetic` — invented, no real person.
- Purpose: prove the **mechanism** (hard-constraint gate blocks; missing
  data does not zero a component; fit ≠ confidence; ranking is
  reproducible; contradictions are not averaged).
- **Not scientific ground truth.** A fixture asserting "career X is a good
  match for profile Y" asserts only that *the engine behaves as specified*
  on that input — not that a career expert agrees.
- Engineering may create, edit, and rely on these freely, provided they
  are labelled synthetic and non-validated.

### 1.2 Authoritative Golden Cases

A Golden Case is authoritative **only after**:

- review by a **career consultant / expert panel**, **and**
- sign-off by the **Methodology Owner**;

and only if it preserves:

- expected important claims;
- acceptable recommendations;
- unacceptable recommendations;
- hard constraints;
- rationale;
- ambiguity notes.

Until both sign-offs exist, a case is `status: draft` and does not gate
anything.

---

## 2. Golden case schema (extends `evals/golden/schema.json`)

Stage 3B adds, for `target = scenario_generation` (direction generation):

| field | meaning |
|---|---|
| `acceptable_directions` | career codes / domains that a correct run may surface as MAIN/ALT |
| `unacceptable_directions` | career codes / domains a correct run must **not** surface (with reason) |
| `expected_constraint_blocks` | `(constraint_vocab_key, career_code)` pairs the hard gate must BLOCK |
| `expected_insufficient_information` | `true` when the profile is below the minimum threshold and the run must decline |
| `expected_reasoning_characteristics` | natural-language properties the explanation must have (cites claims, names gaps, distinguishes fit from confidence) |

`required_claims` / `forbidden_claims` (already reserved in the schema)
carry the expected/never-allowed profile claims.

---

## 3. Critical eval checks (v0.1, from `docs/architecture/04_AI_SYSTEM.md` + Founder decisions)

Exact (pass/fail):

- hard-constraint adherence: 100% (no `BLOCKED` career in MAIN/ALT);
- zero fabricated market facts;
- every MAIN/ALT direction has ≥ 1 supporting claim + a KB version;
- schema validity: 100% after retries;
- no prohibited diagnosis/guarantee language;
- below-threshold profiles return `INSUFFICIENT_INFORMATION`, never a
  padded 6.

Graded (need a human / later an LLM-judge):

- explanation actually distinguishes fit from confidence;
- gaps and risks are named honestly;
- directions are materially distinct.

---

## 4. Model / methodology release process (unchanged from `04_AI_SYSTEM.md`)

change → offline eval on authoritative Golden Cases → compare to baseline
→ human review of critical cases → canary → monitor → promote or rollback.

A new methodology version or non-experimental `ScoringConfig` may be
promoted only through this process, with Methodology Owner sign-off
(Learning & Feedback Protocol §5).
