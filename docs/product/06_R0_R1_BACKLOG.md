# R0/R1 Implementation Backlog

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

### J2 — Golden test set
Acceptance:
- at least 20 representative cases before R1 exit;
- automated checks for hard constraints, fabricated facts and evidence grounding.

## EPIC K — Analytics

Acceptance:
- canonical event envelope;
- funnel from assessment_started → roadmap_activated visible;
- no PII in analytics properties;
- trace ID connects product event and AI generation.

## EPIC L — Admin QA

Acceptance:
- list failed/flagged generations;
- inspect transcript/evidence/output/version;
- regenerate component;
- classify error;
- every admin action audited.

## R0 sprint cut

Build first: **B1, B2, C1, C2, D1, F1, L basic** using existing Telegram/FastAPI foundation. Career data can initially be a curated seed fixture.

## R1 sprint cut

Add: **A cleanup, E1/E2, F2, G, H1/H2/H3, I1/I2, J1/J2, K**.
