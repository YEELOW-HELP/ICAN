# DEVELOPMENT WORKFLOW

Short operating rules for NAPRIAM development.

## 1. Roles

- **Founder / Product Owner — Mykola Minaiev**
  - sets product priorities and Founder decisions;
  - approves UX, methodology and release scope;
  - gives final approval for merge.

- **Product Architect / Technical Coordinator**
  - maintains architecture and Source of Truth;
  - decomposes work into isolated contracts;
  - checks cross-module consistency and PR risk;
  - prevents duplicate Person / Career / Matching / Market domains.

- **Claude / implementation agent**
  - implements bounded tasks on a dedicated feature branch;
  - adds tests and docs;
  - never merges without Founder approval.

- **Frontend owner**
  - customer UI, design system, routing, responsive states, accessibility;
  - must not change backend domain rules or matching methodology independently.

- **Backend / Data owner**
  - FastAPI, services, DB, migrations, validation, security, import/export;
  - must not change product methodology independently.

- **Matching / QA / Data owner**
  - matching implementation, golden tests, evals, fixtures and data adapters;
  - works only from Founder-approved matching contracts.

## 2. Canonical branch

`product-system-v3.1` is the single canonical development / integration branch.

Rules:

1. Never develop directly on `product-system-v3.1`.
2. Every task starts from a fresh `product-system-v3.1`.
3. One task = one short-lived feature branch = one PR.
4. No developer creates another permanent integration branch.
5. Merge only after CI, review and Founder approval.

Example branch names:

- `frontend-profile-polish-v1`
- `person-capability-adapter-v1`
- `matching-capability-fit-v1`
- `market-kb-ua-foundation-v1`

## 3. Module ownership

| Module | Primary owner | Architecture approval required for |
|---|---|---|
| Product UI / frontend | Frontend | route structure, new product concepts, customer data semantics |
| Person KB | Backend / Data | schema, evidence semantics, duplicate Person models |
| Career KB | Backend / Data | schema, status rules, canonical content model |
| Matching | Matching / QA | scoring, ranking, weights, eligibility, fit definitions |
| Market KB | Backend / Data | source hierarchy, market metrics, salary/demand semantics |
| Admin | Frontend + Backend | destructive actions, permissions, canonical edits |
| Security / Auth | Backend | session/auth model, permissions, sensitive-data handling |

## 4. Definition of Done

A task is done only when:

- implementation matches the approved scope;
- no unrelated scope creep is included;
- relevant focused tests pass;
- full regression passes when the task can affect shared runtime;
- migrations are additive and migration CI is green when schema changes;
- no fake production data or misleading live UI is introduced;
- docs / Source of Truth are updated when architecture or behavior changes;
- PR clearly states what changed, what did not change, tests run and known limits;
- Founder / architect has reviewed the PR before merge.

## 5. PR rules

Every PR must contain:

- purpose;
- base / feature branch;
- files / modules changed;
- architecture impact;
- DB / migration impact;
- Person KB impact;
- Career KB impact;
- Matching impact;
- Market KB impact;
- focused tests;
- full regression result;
- known limitations;
- `MERGE: NOT DONE` until Founder approval.

Keep PRs small enough to review. If two developers would edit the same core files for different goals, split or sequence the work first.

## 6. Changes forbidden without architecture approval

Do **not** independently:

- create a second Person model / Person KB;
- create a second Career KB or alternate career source of truth;
- change `I CAN / I AM / I WANT` semantics;
- change Matching formulas, weights, ranking, thresholds or career eligibility;
- auto-publish DRAFT careers;
- change Career publication rules;
- introduce Market KB metrics or external market sources as canonical;
- change evidence semantics;
- change session / auth / permission architecture;
- modify or squash existing migrations;
- replace canonical DB data with Excel imports;
- add fabricated salary, demand, vacancy, score or recommendation data;
- merge another developer's work without review.

If a task appears to require one of these changes: **STOP and request architecture approval.**

## 7. Parallel development rule

Parallel work is encouraged only when contracts are separated.

Preferred pattern:

- Backend developer implements the approved API / data contract.
- Matching developer implements matching logic against the agreed adapter / fixtures.
- Frontend developer implements the approved UI contract using stable response shapes or fixtures.

Do not have multiple developers redesign the same module at the same time.

## 8. Current project state

At the time this workflow was created:

- canonical integration branch: `product-system-v3.1`;
- PR #25 contains the current NAPRIAM Product Shell / Person KB work and is still under Founder review;
- Career KB: 150 careers, 5 ACTIVE, 145 DRAFT;
- public Career UI must expose ACTIVE careers only;
- all 150 careers may be used later for internal Matching development/testing, but DRAFT careers are not public;
- Person KB uses one canonical `MnpPerson` domain;
- `I CAN / I AM / I WANT` are three views of one Person profile, not separate databases;
- production Matching, Market KB, assessment scoring, route engine, progress engine and AI Coach are separate future workstreams.

Update this section when PR #25 is merged and Source of Truth advances.
