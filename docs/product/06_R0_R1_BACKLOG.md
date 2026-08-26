# R0/R1 Implementation Backlog

> **V1 scope note (Founder Product Reconciliation):** this backlog is the
> **platform's** long-term epic list — it is not the current build order.
> The currently authorized build order is
> `docs/product/15_MIY_NAPRYAM_V1_IMPLEMENTATION_ROADMAP.md`, scoped by
> `docs/product/14_MIY_NAPRYAM_V1_PRODUCT_DEFINITION.md`. Several epics
> below are narrowed for V1 — each narrowed epic has its own inline note;
> **do not build the full version of a narrowed epic before its V1 slice
> ships and is validated.**

## Priority convention

- **P0** blocks the product loop.
- **P1** improves quality/operations but does not block first closed-loop validation.
- Every story requires acceptance tests and analytics where relevant.

## EPIC A — Identity & Consent

### A1 — Canonical user identity
**Story:** as a user I can authenticate through Telegram or web and remain one canonical user.

Acceptance:
- Telegram identity maps to canonical `User`;
- duplicate identity merge policy documented;
- locale/timezone stored;
- no secrets in client storage beyond standard session tokens.

### A2 — Consent ledger
Acceptance:
- consent has purpose + version + granted/withdrawn timestamp;
- assessment cannot start without required consent;
- withdrawal is auditable.

## EPIC B — Assessment Engine

**V1 scope note:** the architecture supports 4 assessment modes (Structured,
Conversation, Hybrid, CV Assisted) as one system — that is an architecture
requirement, not a claim that all four ship as production flows up front.
**Commercial V1 release requires only Hybrid (default paid flow) with CV
as an evidence-source capability inside it** — built first (Stage 1 of
`docs/product/15_MIY_NAPRYAM_V1_IMPLEMENTATION_ROADMAP.md`). Structured
ships later, at the Commerce/Funnel/Launch stage, as the free lead magnet.
Conversation is not a Commercial V1 release blocker. See
`docs/product/14_MIY_NAPRYAM_V1_PRODUCT_DEFINITION.md` §7–§9 for the full
per-mode table. The acceptance criteria below are unchanged and still
apply to whichever modes actually ship.

### B1 — Assessment state machine
States: `draft → active → paused → complete → processing → ready → failed`.

Acceptance:
- every answer autosaves;
- user resumes at correct state;
- repeated request is idempotent;
- completion blocked until minimum data rule passes.

### B2 — Adaptive next-question service
Acceptance:
- receives current completeness map;
- never asks already-resolved facts without a contradiction reason;
- can request clarification for low-evidence claims;
- next-question decision is traceable.

## EPIC C — Evidence Graph

### C1 — Evidence extraction
Acceptance:
- answer can produce multiple evidence records;
- evidence points to immutable source reference;
- confidence/weight stored;
- reviewer can inspect source.

### C2 — Profile claims
Acceptance:
- each high-impact claim has evidence IDs or explicit `low_confidence`/`hypothesis` status;
- claim stores model/prompt version;
- regeneration does not destroy previous version.

## EPIC D — Human Potential Profile

### D1 — Structured profile schema
Dimensions: strengths, values, motivators, skills, preferences, constraints, goals, experiences.

Acceptance:
- JSON schema validation;
- relational storage for critical searchable fields;
- user-facing summary generated from structured data.

## EPIC E — Career Seed Graph

**V1 scope note:** rescoped to a curated, versioned **Knowledge Base**
sufficient for Direction Intelligence (`14_...md` §12), not a full world
career graph and not automated ingestion — see roadmap Stage 3 (appendix
sub-stage 6). The 50–100
seed-careers target below is a platform-scale figure; V1's actual seed size
is whatever Direction Intelligence needs to produce grounded, non-fabricated
directions, likely smaller at first.

### E1 — Career entity and source provenance
Acceptance:
- seed 50–100 careers for first target cohorts;
- each factual market field has source/date;
- taxonomy mapping supports UA/EN titles and aliases.

### E2 — Career matching v1
Pipeline: hard constraints → candidate retrieval → factor scoring → explainability.

Acceptance:
- hard constraints cannot be overridden;
- scoring weights config-driven;
- top candidates include factor breakdown.

## EPIC F — Scenario Engine

**V1 scope note — REDEFINED, not narrowed:** the Founder Product
Reconciliation redefines this epic as **Direction Intelligence** —
TOP 3 main + 3 alternative directions (6 total). **Safe/Growth/Bold is not
a required V1 product model.** No ERD change is implied
(`SCENARIO.scenario_type` was already a free string). See
`docs/product/14_MIY_NAPRYAM_V1_PRODUCT_DEFINITION.md` §11 and
`15_..._ROADMAP.md`'s Stage 3 (appendix sub-stage 5) and its Issue #3
reconciliation entry for full rationale. F1's acceptance criteria below still apply with
"Safe/Growth/Bold" read as "however Direction Intelligence's methodology
labels its 3 main + 3 alternative directions."

### F1 — Three scenarios
Acceptance:
- Safe, Growth and Bold are materially distinct;
- each has fit, confidence, strengths already present, gaps, trade-offs, risks and first steps;
- no unsupported salary/market claims.

### F2 — Scenario compare
Acceptance:
- user can compare factor-by-factor;
- evidence/explanation opens from UI;
- compare event emitted.

## EPIC G — Direction Decision

Acceptance:
- user selects one scenario;
- rationale/trade-off answers stored;
- change of direction creates history, not destructive overwrite.

## EPIC H — Roadmap Engine

**V1 scope note:** **not built in V1.** V1 ships only the high-level Route
Builder (`14_...md` §13, roadmap Stage 3 / appendix sub-stage 8: CURRENT
STATE → GAPS → NEXT STEPS → TARGET DIRECTION) — no milestones, task execution states, effort
estimation, or replanning. Do not start H1/H2/H3 below until the platform
explicitly moves past V1 — see `15_..._ROADMAP.md`'s Issue #5
reconciliation.

### H1 — 90-day roadmap
Acceptance:
- three phases / milestones;
- 6–12 concrete tasks;
- each task has definition of done and reason;
- effort respects user constraints.

### H2 — Task execution
Acceptance:
- todo/doing/blocked/done/skipped states;
- optional evidence attachment;
- completion emits analytics event.

### H3 — Replanning
Acceptance:
- new constraint or direction creates new roadmap version;
- old version remains viewable/auditable.

## EPIC I — Guide Client 360

**V1 scope note:** **not built in V1.** V1 needs only the Consultant Review
Workspace required for the mandatory Human Review gate
(`14_...md` §14–§15, roadmap Stage 3 / appendix sub-stage 10) — client basic info, assessment,
transcript, CV, structured answers, evidence, profile, proposed directions,
routes, and the approve/edit/regenerate/reject controls. Full Client 360
(session booking, long-term relationship tooling, timeline beyond what
review needs) is deferred — see `15_..._ROADMAP.md`'s Issue #6
reconciliation. I1–I3 below describe the full future Guide OS, not V1.

### I1 — Client list
Acceptance:
- Guide sees only assigned/consented clients;
- search/filter by stage and risk;
- direct ID access to another Guide's client is denied server-side.

### I2 — Client 360
Shows:
- profile;
- evidence;
- scenarios;
- direction;
- roadmap/tasks;
- timeline;
- Guide notes.

### I3 — Session prep v1
Acceptance:
- AI generates brief from changes/tasks/profile;
- Guide must review before client-facing recap.

## EPIC J — AI Gateway & Evals

### J1 — Gateway wrapper
Acceptance:
- no direct provider calls outside gateway;
- model/prompt/task/latency/tokens/cost/trace logged;
- schema validation + retry/fallback.

**Status (Sprint 0 exit):** partially satisfied ahead of schedule. `app/ai_gateway.py` is the only call site to the provider (`ScreeningAgent` goes through it), and every call logs task/prompt_version/model/latency/tokens/cost/trace_id, including on provider failure. Not yet done: structured-output schema validation inside the gateway itself, and retry/fallback (explicitly deferred by decision, not an oversight). See `docs/engineering/12_SPRINT_0_EXIT_REPORT.md`.

### J2 — Golden test set
Acceptance:
- at least 20 representative cases before R1 exit;
- automated checks for hard constraints, fabricated facts and evidence grounding.

**Status (Sprint 0 exit):** structure started, not satisfied yet. `evals/golden/` has a versioned schema and 10 synthetic, unreviewed (`status: draft`) example cases for `screening` only — half the required count, and none of the automated checks exist since no eval runner was built (out of scope for Sprint 0). See `docs/engineering/12_SPRINT_0_EXIT_REPORT.md`.

## EPIC K — Analytics

Acceptance:
- canonical event envelope;
- funnel from assessment_started → roadmap_activated visible;
- no PII in analytics properties;
- trace ID connects product event and AI generation.

## EPIC L — Admin QA

**V1 scope note:** extended, not narrowed — this epic is the engineering
home for V1's **non-negotiable mandatory Human Review gate**
(`14_...md` §14, roadmap Stage 3 / appendix sub-stage 10): every paid report requires an
`approved` state, enforced server-side, before it can reach a user. See
`15_..._ROADMAP.md`'s Issue #9 reconciliation.

Acceptance:
- list failed/flagged generations;
- inspect transcript/evidence/output/version;
- regenerate component;
- classify error;
- every admin action audited.

## R0 sprint cut / R1 sprint cut — superseded for current work

These two sections describe the platform's original, pre-V1 sequencing and
are kept for historical reference. **Current sequencing is
`docs/product/15_MIY_NAPRYAM_V1_IMPLEMENTATION_ROADMAP.md`'s staged plan**,
which covers similar ground (assessment → evidence → direction →
review/QA) but adds Product Access/payment, the mandatory human review
gate, and explicitly excludes H1/H2/H3 and I1–I3's full scope from V1
entirely rather than deferring them to "R1."

Original text, unchanged:

Build first: **B1, B2, C1, C2, D1, F1, L basic** using existing Telegram/FastAPI foundation. Career data can initially be a curated seed fixture.

Add: **A cleanup, E1/E2, F2, G, H1/H2/H3, I1/I2, J1/J2, K**.
