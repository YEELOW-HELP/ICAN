# Golden Dataset

Sprint 0, Part 5 (Issue #12), extended in Stage 2 (Issue #2). Structure
plus a growing set of synthetic example cases: ten for `screening`
(`legacy-screening-v1`), four for `evidence_extraction`
(`evidence-extraction-v1`), and five for `profile_synthesis`
(`claim-synthesis-v1`) — see each target folder's own README for what its
cases demonstrate. No eval runner exists yet; see "Future CI use" below
for what that will look like once built.

## Purpose

Golden cases exist to catch two different kinds of regression before they
reach real candidates:

1. **Behavioral regression** — a prompt/model/gateway change makes a
   previously-correct case fail (misses a fact, invents one, drops a hard
   constraint, confirms too early/late).
2. **Silent drift** — nothing "breaks" in the test-suite sense, but output
   quality degrades in ways only a held-out, human-reviewed case set would
   catch (per `docs/architecture/04_AI_SYSTEM.md`'s evaluation system).

This directory does **not** replace `tests/` — `tests/` proves the code
does what it's supposed to given a scripted, fake AI response; golden cases
(once a runner exists) prove the *actual model* behaves correctly against
realistic input.

## Governance

- **No real production data, ever.** No PII copied from Neon, Telegram, the
  CRM, application logs, or screenshots — enforced by requirement, not by
  tooling, so every contributor is personally responsible for this.
- Every case's `provenance.type` must be either:
  - **`synthetic`** — entirely invented; no real person behind it. This is
    the only provenance type used in this initial structure and the
    expected default going forward.
  - **`consented-anonymized`** — derived from a real interaction with
    explicit consent from that person *and* full anonymization (no name,
    contact info, employer, or other identifying detail survives).
    `reviewer_notes` must document how it was anonymized. Given
    Item 13 in the technical debt register (no consent tracking exists in
    ICAN 1.1 yet), this provenance type should not be used in practice
    until that gap closes — recorded here as a rule for when it does, not
    an invitation to use it now.
- A case with real user data discovered after merge must be deleted (not
  retired — see "Reproducibility" below for why retired is normally
  preferred) and reported, same as any other data incident.

## Anonymization rules

If/when `consented-anonymized` cases are ever added:

- No real name, phone, email, Telegram handle, employer name, or specific
  identifying combination of city + role + timeframe.
- Replace with a synthetic-but-plausible equivalent (a fictional city
  standing in for a real one of similar size/region is fine; the real city
  name is not).
- `reviewer_notes` must state what was changed from the source interaction.
- When in doubt, prefer rewriting the case as fully `synthetic` — inspired
  by a real pattern without being traceable to a real person.

## Structure

```
evals/golden/
  README.md              this file
  schema.json             JSON Schema every case must satisfy
  v1/
    screening_legacy_v1/  10 example cases for target=screening
    evidence_extraction/  4 example cases (Stage 2)
    profile_synthesis/    5 example cases (Stage 2)
    scenario_generation/  reserved, empty until that AI System component exists (Stage 3)
    roadmap_generation/   reserved, empty (Stage 3+)
    opportunity_matching/ reserved, empty (not in V1)
```

One case = one JSON file, validated against `schema.json`. File name should
be `<case_id>.json` with the same `case_id` inside.

## Versioning

- `v1/`, `v2/`, ... are **dataset versions**, matching each case's
  `dataset_version` field.
- A dataset version is immutable once any case in it reaches `status:
  approved` — corrections happen by creating a new case (new `case_id`) or a
  new dataset version, never by silently editing an approved case's
  expectations in place. Fixing an obvious typo in `reviewer_notes` on a
  still-`draft` case is fine; changing `expected_facts`/`acceptable_outputs`
  on an `approved` case is not.
- A new dataset version is warranted when: the methodology/taxonomy version
  changes (Decision 2 — taxonomies are versioned, starting at Taxonomy v1),
  the prompt/model registered under a `prompt_version` changes in a way that
  changes expected behavior, or enough individual case corrections
  accumulate that re-basing is clearer than a pile of one-off edits.
- Old dataset versions are never deleted. They stay reproducible (see
  below) as a historical record of what "correct" meant at the time.

## Reproducibility

- Every case pins the exact `prompt_version` (and optionally `model_version`)
  it was written against, plus `methodology_version` for when a real
  taxonomy exists. Given those three, a case from any past dataset version
  can be re-run against its original configuration even after the current
  `prompt_version`/taxonomy has moved on.
- Prefer `status: retired` over deletion for a case that's no longer
  representative — it stays in the historical record and reproducible, just
  excluded from active CI gating (see below). Delete only for the real-data
  incident case described under Governance.

## Review process (human review — no automation yet)

1. A case starts as `status: draft` with `reviewed_by.role: null`.
2. A qualified human reviewer — **Methodology Lead** for
   `expected_facts`/`expected_constraints`/`required_claims`/`forbidden_claims`
   correctness, **QA** for `acceptable_outputs`/`unacceptable_outputs`
   phrasing and coverage, either for `screening` cases specifically since no
   taxonomy is involved yet — reads the case, confirms it's realistic,
   correctly labeled, and free of real data, then sets `status: approved`
   and fills in `reviewed_by.role` (and `name` if the team wants
   attribution).
3. Only `approved` cases are meant to gate anything once a runner exists
   (see below) — `draft` cases are visible and usable for manual testing but
   shouldn't block CI on their own say-so.
4. The ten example cases in `v1/screening_legacy_v1/` are `status: draft`
   in this commit — they demonstrate the format but have not been through
   the review in step 2 yet. Marking them `approved` is a follow-up action
   for whoever is assigned the Methodology/QA review role, not something
   this Sprint 0 change does unilaterally.

## Future CI/regression use (not built yet)

Deliberately not built in this change — noted here so the intent is clear
before it exists:

- An eval runner would load all `approved` cases for a given `target`, feed
  each `input` through the real component (e.g.
  `ScreeningAgent.process_message` via the AI Gateway for `target=screening`),
  and check the output against `expected_facts` / `expected_constraints` /
  `acceptable_outputs` / `unacceptable_outputs`.
- Per `docs/architecture/04_AI_SYSTEM.md`'s "Critical evals" list, some
  checks are exact (schema validity, hard-constraint adherence, zero
  fabricated facts) and some need a QA Critic / LLM-as-judge grader
  (actionability, tone) — this structure supports both by keeping
  `expected_*` fields for the former and `acceptable_outputs`/
  `unacceptable_outputs` as natural-language criteria for the latter.
- This would run against the real Anthropic API (unlike `tests/`, which is
  explicitly forbidden from doing that — see `pytest.ini`'s
  `--disable-socket`). It belongs in its own CI job, on its own schedule
  (not on every commit — real API calls cost money and are non-deterministic),
  separate from the regression suite in `tests/`.
- `docs/architecture/04_AI_SYSTEM.md`'s Model release process (change →
  offline eval → compare to baseline → human review → canary → monitor →
  promote/rollback) is exactly the process this dataset is meant to feed
  once the runner exists.

## `screening` / `legacy-screening-v1` case coverage

The ten example cases in `v1/screening_legacy_v1/` are designed to
demonstrate coverage of every behavior Sprint 0 Part 5 was asked to
structure for:

| # | case_id | Demonstrates |
|---|---|---|
| 1 | `case_001_first_career_basic_facts` | Correct fact extraction on a clean, unambiguous message |
| 2 | `case_002_career_change_relocation_constraint` | Hard constraint (cannot relocate) stated once and must be preserved |
| 3 | `case_003_transition_35_50_multiple_positions` | Extraction across a longer, multi-fact message (older-candidate segment) |
| 4 | `case_004_low_information_user` | No invented facts when the candidate gives almost nothing; must ask, not guess |
| 5 | `case_005_contradictory_answers` | Contradiction between turns handled by asking, not silently overwriting |
| 6 | `case_006_strict_constraint_childcare_hours` | A different hard constraint (fixed hours), preserved across turns |
| 7 | `case_007_ready_for_confirmation` | Correct `ready_for_confirmation=true` + summary once enough is known |
| 8 | `case_008_no_invented_salary` | Salary never mentioned → must stay null, never fabricated |
| 9 | `case_009_forbidden_diagnosis_and_guarantee_language` | Output must never contain a diagnosis or an employment guarantee |
| 10 | `case_010_english_message_ukrainian_reply` | Candidate writes in English → reply must still be Ukrainian (system prompt rule) unless the candidate explicitly asked to switch |

All ten: `provenance.type: synthetic`, `dataset_version: v1`,
`prompt_version: legacy-screening-v1`, `methodology_version:
pre-taxonomy-legacy`, `status: draft`.

## `evidence_extraction` / `evidence-extraction-v1` case coverage (Stage 2)

| # | case_id | Demonstrates |
|---|---|---|
| 1 | `case_001_straightforward_coherent_evidence` | Clean single-signal extraction |
| 2 | `case_002_cv_heavy_profile_direct_facts_not_traits` | CV facts stay direct evidence, never pre-baked into a trait |
| 3 | `case_003_open_answer_heavy_multiple_distinct_signals` | One answer -> multiple separable evidence items (brief §17's worked example) |
| 4 | `case_004_sparse_evidence_low_information_user` | No signal -> zero evidence, never fabricated |

All four: `provenance.type: synthetic`, `dataset_version: v1`,
`prompt_version: evidence-extraction-v1`, `methodology_version:
potential_dimensions:v1`, `status: draft`.

## `profile_synthesis` / `claim-synthesis-v1` case coverage (Stage 2)

| # | case_id | Demonstrates |
|---|---|---|
| 5 | `case_005_contradictory_answers_retained_not_averaged` | Contradiction flagged, confidence lowered, never silently averaged |
| 6 | `case_006_hard_constraint_never_softened` | A hard constraint's claim preserves its hardness |
| 7 | `case_007_no_hallucinated_salary_or_market_data` | No invented salary/market facts anywhere in a claim |
| 8 | `case_008_no_diagnosis_or_clinical_language` | No clinical/diagnostic labels in claim text |
| 9 | `case_009_no_unsupported_personality_claim_from_weak_evidence` | A single weak evidence item cannot reach `supported` status |

All five: `provenance.type: synthetic`, `dataset_version: v1`,
`prompt_version: claim-synthesis-v1`, `methodology_version:
potential_dimensions:v1`, `status: draft`.
