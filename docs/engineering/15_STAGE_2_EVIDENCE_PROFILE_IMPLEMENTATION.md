# Stage 2: Evidence + Human Potential Profile — Implementation Reference

Branch: `stage-2-evidence-potential-profile-v1` (based on `product-system-v3.1`
@ merged PR [#17](https://github.com/YellowHub-Ukraine/ICAN/pull/17)).
Implements Issue #2: turns a COMPLETE Hybrid assessment into an
auditable, versioned Human Potential Profile grounded in evidence. Does
**not** build Direction Intelligence, TOP3/Alternative3, the Knowledge
Base, Route Builder, the client report, or Consultant Review — that is
Stage 3 (see brief §31).

This document is a reference for engineers and reviewers — see
`docs/product/14_MIY_NAPRYAM_V1_PRODUCT_DEFINITION.md` §10 for product
scope and `docs/architecture/02_ERD.md` for the target entity shapes this
implementation narrows.

## 1. The pipeline (brief §2)

```
Assessment (COMPLETE)
  -> Evidence Extraction        (app/services/profile/evidence_extraction.py)
  -> Evidence normalization     (Evidence rows, deduplicated by source)
  -> Profile Claims             (app/services/profile/claim_synthesis.py)
  -> Confidence / provenance    (compute_claim_confidence -- deterministic)
  -> Potential Profile version  (app/services/profile/generation.py)
  -> Profile Summary            (app/services/profile/summary.py)
```

RAW DATA (`Answer`/`CVUpload`, Stage 1) is never presented as EVIDENCE
directly — every `Evidence` row is a normalized, source-referenced
observation. EVIDENCE is never presented as a CLAIM — a claim only exists
grouped/labeled and confidence-scored via `ProfileClaim`. A CLAIM is never
presented as the whole PROFILE — a `PotentialProfile` is a versioned
collection of claims plus a presentation-only summary.

## 2. New tables (`app/db/models_profile.py`)

| Table | Purpose |
|---|---|
| `taxonomies` / `taxonomy_versions` / `taxonomy_terms` | ERD's `TAXONOMY`/`TAXONOMY_VERSION`/`TAXONOMY_TERM`, exactly — no parallel system. |
| `evidence` | Normalized, source-referenced observations. |
| `potential_profiles` | One versioned generation attempt per row. |
| `profile_claims` | Claims about the person, grounded in evidence. |
| `profile_claim_evidence` | Many-to-many join: which evidence grounds which claim. |

Migration: `0c9abc704162` (additive, FK-ordered, downgrade reverses
exactly). No existing Stage 1 table is altered.

## 3. Evidence model

`Evidence` (brief §4): `id`, `user_id`, `session_id` (the
"profile-generation context"), `source_type`
(`structured_answer`/`open_answer`/`cv`/`derived`), `source_id` (a
polymorphic reference to `Answer.id` — no DB-level FK, same rationale as
the ERD's `source_ref`), `evidence_type` (a short tag, ideally a seeded
`TaxonomyTerm.term_key`), `normalized_text`, `confidence`,
`extraction_method` (`deterministic` | `llm_extraction`),
`taxonomy_version_id` (nullable), `trace_id` (nullable — AI Gateway
provenance, null for deterministic evidence which made no AI call),
`created_at`.

**Never duplicates raw text.** `normalized_text` is the extracted
observation, not a copy of `Answer.answer_text`/`CVUpload.extracted_text`
— the original is one `source_id` lookup away. `InterviewMessage` is
never read as a Stage 2 evidence source at all (see §11, source
precedence).

**Idempotent by construction**: `UNIQUE(session_id, source_type,
source_id, evidence_type)`. Re-running generation for a session that
already has evidence for a given answer skips it entirely — evidence is
extracted once and reused across every later regeneration, never
re-spending an AI Gateway call on an already-processed answer.

**Structured vs open/CV** (brief §16): a `structured` question's Answer
becomes exactly one deterministic Evidence row
(`extraction_method="deterministic"`, `confidence` = the Answer's own
confidence, no AI call, `trace_id=None`). An `open` or `cv`-sourced
Answer goes through `EvidenceExtractor` (AI Gateway task
`evidence_extraction`, `prompt_version="evidence-extraction-v1"`), which
can produce **0–5 normalized evidence items from one answer** — a richer
pass than Stage 1's own single-value `AnswerExtractor`, since one open
answer can carry several distinct signals (brief §17's worked example:
"I've always enjoyed organizing events" → 3 separate observations).

**Explicit fact vs inferred claim** (brief §15): a CV fact like "Worked
at Siemens 2011–2015" is extracted as direct `Evidence`
(`source_type=cv`) — never pre-baked into a personality conclusion at
extraction time. Only claim synthesis may turn it into something like "has
enterprise engineering experience," and only as a `ProfileClaim`, with
the CV evidence linked, not asserted as fact on its own.

## 4. Claim model

`ProfileClaim` (brief §5): `id`, `profile_id`, `dimension` (the 11
structural categories below), `taxonomy_version_id`/`term_key`
(nullable — a claim may use a free label before full taxonomy coverage
exists), `label`, `normalized_value`, `score` (nullable — reserved for a
future strength/intensity value, not used by Stage 2 logic itself),
`confidence`, `status`, `generated_by`, `trace_id`, plus
`superseded_by_claim_id`/`correction_reason` (nullable, unused by Stage 2
— see §10, human-editing prep).

**`ProfileDimension`** (Python enum — architectural, not methodology
content): `strength`, `interest`, `value`, `motivation`, `skill`,
`trait`, `work_preference`, `constraint`, `goal`, `experience`,
`contextual_factor`. These are the 11 categories the brief requires
(§3); the actual *terms within* a dimension are seeded `TaxonomyTerm`
rows (§7 below), never a Python enum.

**`ClaimStatus`**: `supported`, `hypothesis`, `contradicted`,
`insufficient_evidence`. A claim is **never persisted with zero
supporting evidence** — `compute_claim_confidence` returns `None` for
that case and the caller drops the proposal entirely (defense in depth:
both `claim_synthesis.py`'s own output validation and
`generation.py::_persist_claims` independently bounds-check evidence
indices, since `ClaimSynthesizer` is a pluggable interface and must not
be trusted blindly by the orchestrator).

**Many-to-many evidence linkage** (brief §6): `ProfileClaimEvidence`.
`explain_claim(session, claim_id=...)` in `generation.py` answers "why do
we think this is true?" directly — the exact evidence rows behind one
claim.

## 5. Confidence model (deterministic, brief §8)

`compute_claim_confidence` (`app/services/profile/claim_synthesis.py`) —
a pure function, **not an LLM-reported number**:

```
if no supporting evidence:        None (claim is dropped, never emitted)
if is_contradictory:              confidence = min(evidence confidences) * 0.6
                                   status = CONTRADICTED
else:
    base = average(evidence confidences)
    + up to 0.15 corroboration bonus (more independent evidence items)
    + 0.10 direct-evidence bonus (any deterministic/structured evidence present)
    status = SUPPORTED        if confidence >= 0.6 and (>=2 evidence items OR direct evidence)
             HYPOTHESIS       if confidence >= 0.25
             INSUFFICIENT_EVIDENCE  otherwise
```

**Contradictions are never averaged away** (brief §7): two conflicting
evidence items grouped under one claim are BOTH retained
(`ProfileClaimEvidence` links to both), `is_contradictory=true` forces
`CONTRADICTED` regardless of how confident either individual signal was,
and confidence is driven down, never smoothed into a false middle ground.

**Source certainty vs claim confidence stay conceptually separate**
(brief §16): a structured answer's `Evidence.confidence` is typically
1.0 (direct, deterministic), but the `ProfileClaim` grounded in it can
still legitimately be `HYPOTHESIS` if it's the only signal and the
dimension usually needs corroboration — direct evidence earns a
confidence *bonus*, not an automatic `SUPPORTED` verdict, except when it
is genuinely the kind of fact that needs no further corroboration
(handled by the `has_direct_evidence` branch in the SUPPORTED threshold).

**No fake precision** (brief §8): `app/services/profile/summary.py`'s
`confidence_bucket()` maps `ClaimStatus` → `high`/`medium`/`low`/
`contradictory` before anything reaches a prompt or a user — the raw
float never does.

## 6. Taxonomy versioning (brief §9)

`app/services/profile/taxonomy.py::ensure_seed_taxonomy` — idempotent,
application-level seeding (get-or-create), **not** baked into the
Alembic migration. One `Taxonomy` (`key="potential_dimensions"`), one
`TaxonomyVersion` (`version=1`, `status=active`), ~32 `TaxonomyTerm` rows
spread across the 11 dimensions — a minimal seed to validate the
pipeline, explicitly not the final МОЖУ methodology
(`docs/engineering/11_TECHNICAL_DEBT_REGISTER.md` Item 11 remains the
real methodology work). Application-level seeding (vs. migration-level,
Stage 1's `product_plans` precedent) was a deliberate choice: taxonomy
*content* is expected to evolve as data long before the next schema
migration, unlike Stage 1's genuinely-fixed `BASIC`/`PREMIUM` plan
config.

`ClaimSynthesizer` receives the full seeded vocabulary
(`term_key`/`dimension`/`label_uk`) as a closed list and is instructed to
prefer a real `term_key` over inventing one; `term_key=null` is legal
when nothing in the seed genuinely fits.

## 7. Profile versioning (brief §10)

`PotentialProfile.version` is scoped **per `user_id`, not per session**
(`UNIQUE(user_id, version)`) — the Human Potential Profile is a
per-person concept that can span multiple assessment sessions over time
(matches the ERD's `USER ||--|| POTENTIAL_PROFILE`), with `session_id`
recording which specific assessment produced a given version.

`is_current` is enforced to at most one `true` row per user via a
**partial unique index** (`uq_one_current_profile_per_user`, Postgres
`WHERE is_current = true` / SQLite `WHERE is_current = 1`) — the same
idiom as Stage 1's `uq_one_unfinished_session_per_user`. A superseded
version is never deleted or edited — only its `is_current` flag flips to
`false`.

Regeneration (`generate_potential_profile` called again after a `READY`
version already exists) creates `version = max(existing) + 1`, reuses
already-extracted `Evidence` (no re-spent AI calls for already-processed
answers), and marks the new version current once it succeeds — the
previous version's row is untouched otherwise.

## 8. Processing state — two separate state machines (brief §11/§12)

This is the single most important design decision in Stage 2, spelled
out in full in `app/services/profile/generation.py`'s module docstring:

- **`InterviewSession.status`** transitions `COMPLETE -> PROCESSING ->
  READY` **exactly once** per session, marking "this assessment's data
  collection has concluded and produced at least one profile." Stage 1's
  state machine (`app/services/assessment/state_machine.py`) makes
  `READY` and `FAILED` fully terminal — a hardened, tested invariant this
  module never touches. Once `READY`, `InterviewSession.status` never
  changes again, even across many later regenerations.
- **`PotentialProfile.status`** (`GENERATING` → `READY` | `FAILED`) is
  the per-attempt, per-version lifecycle. Every attempt — first, retry,
  or regeneration — is its own permanent row.

**Founder decision (Stage 2 review, approved):** a transient/ordinary
profile-generation failure does **not** move `InterviewSession` to
`FAILED`. It is deliberately left at `PROCESSING` — mirroring Stage 1's
own `submit_answer` precedent (a provider failure must not move the
session to a dead-end state; it stays put for the next attempt). This is
what makes retry actually possible: a session sitting at `PROCESSING` is
exactly eligible to call `generate_potential_profile` again. Each failed
attempt is fully and correctly recorded as its own permanent
`PotentialProfile(status=FAILED)` row — the failure is never lost or
hidden, just not projected onto the assessment's own coarse status.

`InterviewSession.status -> FAILED` is reserved **exclusively** for an
explicit administrative give-up / fatal termination (Stage 1's
`fail_session()`) — never invoked automatically from a profile-generation
exception. This keeps Stage 1's hardened, tested invariant intact
(`test_failed_is_terminal_no_outgoing_transition_exists`: `FAILED` has
zero outgoing transitions on `InterviewSession`) while still making
retry genuinely possible: the retry lifecycle lives entirely on
`PotentialProfile.status`, which is designed to cycle through
`GENERATING -> FAILED` on every unsuccessful attempt without that ever
touching the assessment's own terminal states.

Concurrency: only one profile-generation attempt may be `GENERATING` per
user at a time (`ProfileGenerationInProgressError` otherwise) — this is
what "do not accidentally create multiple uncontrolled profile versions"
means concretely, alongside the `is_current` partial unique index.

## 9. AI pipeline (brief §13, Issue #7)

Three independent AI Gateway tasks, never one giant prompt:

| Task | Module | `prompt_version` | Input | Output |
|---|---|---|---|---|
| Evidence Extractor | `evidence_extraction.py` | `evidence-extraction-v1` | one answer's raw text | 0–5 normalized evidence items |
| Claim Synthesizer | `claim_synthesis.py` | `claim-synthesis-v1` | a session's full evidence set + taxonomy vocabulary | claim groupings + contradiction flags (confidence computed deterministically afterward, not by this call) |
| Profile Summarizer | `summary.py` | `profile-summary-v1` | a profile's final claims, confidence-bucketed | Ukrainian summary text |

All three go through `app.ai_gateway.AIGateway.call_tool` — no direct
provider SDK call exists anywhere in `app/services/profile/`. Each
returns its AI Gateway `trace_id` alongside its result, persisted on the
`Evidence`/`ProfileClaim`/`PotentialProfile` row it produced (database
rule #7's "trace_id reference" pattern — no `AI_TRACE` table exists yet,
matching Stage 1's precedent; see `02_ERD.md`'s note that `AI_TRACE` is
not persisted in production yet).

**Structured output validation** (brief §14): every tool response is
validated field-by-field before use. A malformed *individual* item is
dropped without discarding the rest of a response; a fully malformed
response degrades to "nothing extracted this round" rather than
crashing generation or persisting garbage. A provider-level failure
(exception from `call_tool` itself) is never swallowed — it propagates
to `generate_potential_profile`, which marks that attempt `FAILED` (see
§8) and re-raises.

## 10. Human-editing preparation (brief §20)

`ProfileClaim.superseded_by_claim_id`/`correction_reason` exist as
architecture-ready hooks — unused by any Stage 2 logic, so a future
Stage 3 "AI claim → human correction → final claim → reason" workflow
doesn't require a schema migration to represent. No admin editing UI is
built now.

## 11. Source precedence (brief §26)

Stage 2 evidence extraction reads **`Answer` rows exclusively** — never
`InterviewMessage`. `InterviewMessage`'s Stage 1 role (raw transcript,
audit/reprocessing only, never read by the next-question service either)
is preserved unchanged; Stage 2 simply never adds a new reader for it.
This sidesteps the "InterviewMessage can theoretically duplicate under a
rare concurrent submission" concern entirely rather than adding
deduplication logic for a source Stage 2 doesn't consume.

## 12. Stale-pending-answer recovery (brief §25)

`app/services/assessment/sessions.py::recover_stale_pending_answers`
(new Stage 1-module function, since it operates on the `Answer` table
Stage 1 owns): deletes any `Answer` row with `extracted_value IS NULL`
older than `settings.pending_answer_stale_after_seconds` (default 300s)
for a session — safe because the candidate's raw text survives
independently in `InterviewMessage`. Called automatically at the start
of `generate_potential_profile`, before any evidence is read, so a stale
reservation from a Stage 1 process crash is swept before it could ever be
mistaken for "no answer" forever or (via `compute_completeness`'s
existing `extracted_value IS NULL` → `"missing"` handling) for real
evidence. Never treated as evidence at any point — belt-and-suspenders
via both the read-time filter (`extracted_value.isnot(None)`) and the
active sweep.

## 13. Privacy (brief §24)

- No raw answer/CV text is ever logged — `app/services/profile/*.py`
  contains zero `logger.*` calls.
- `Evidence.normalized_text` is the only text stored by this module
  beyond what Stage 1 already stores; it is a short, extracted
  observation, never a copy of the source.
- On a generation failure, only `type(exception).__name__` is persisted
  as `PotentialProfile.failure_reason` — never `str(exception)` verbatim,
  since a provider exception could in rare cases echo request content.
- Events (`emit_event`) carry only IDs, counts, and enum/type values —
  never evidence/claim text.

## 14. Events

`profile_generation_started`, `evidence_extracted` (with
`new_evidence_count`), `profile_generated` (with `claim_count`),
`profile_generation_failed` (with `error_type`). No `profile_regenerated`
event was added separately from `profile_generation_started`/
`profile_generated` — a regeneration is simply another generation
attempt from the emitting code's point of view; the `version` number on
`profile_generation_started`/`profile_generated` already distinguishes a
first generation from a regeneration for any consumer that needs to.

## 15. API/service surface

`generate_potential_profile(session, *, session_id, user_id, ...)`,
`get_current_profile(session, *, user_id)`, `get_owned_profile(session,
*, profile_id, user_id)`, `explain_claim(session, *, claim_id)`,
`ensure_seed_taxonomy(session)`,
`recover_stale_pending_answers(session, session_id)` (Stage 1 module).

## 16. Known limitations / deferred tech debt

- No Telegram/API adapter surfaces the generated profile to a user yet —
  Stage 2 is the domain/service layer only, per the brief's explicit
  scope (no client report, no admin console — that's Stage 3's Human
  Review + Report work).
- `PotentialProfile.score` on `ProfileClaim` is defined but unused by any
  Stage 2 logic (reserved for a future strength/intensity value distinct
  from confidence).
- No `AI_TRACE` table is persisted (matches Stage 1 and the ERD's own
  documented state) — `trace_id` strings are stored on generated rows,
  structured logs remain the source of full trace detail.
- The seed taxonomy (~32 terms) is intentionally minimal — real
  methodology content is separate future work.
- `_await_pending_answer`-style waiting is not needed here since Stage 2
  never races two callers over the same Answer; the analogous concurrency
  guard for Stage 2 (`ProfileGenerationInProgressError`) is a hard reject,
  not a wait-and-retry, since profile generation is a heavier, explicitly
  user/operator-triggered action rather than a Telegram message retry.

## 17. Acceptance criteria (Issue #2) — status

- Every high-impact claim has evidence IDs or is legitimately dropped
  before persistence (no zero-evidence claims exist) — ✅, enforced twice
  (validation layer + orchestrator defense-in-depth).
- Reviewer can open the exact source behind a claim — ✅, `explain_claim`.
- Regeneration creates a new version and preserves history — ✅, tested.
- Structured schema validates before persistence — ✅, both AI tasks
  validate before any DB write.
- No invented facts are accepted into evidence — ✅, malformed/ungrounded
  items are dropped, never persisted.
