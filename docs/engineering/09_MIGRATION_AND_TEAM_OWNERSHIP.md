# Migration from ICAN 1.1 + Team Ownership

## Current baseline

The existing repository already has useful foundations:
- Telegram bot;
- FastAPI API;
- SQLAlchemy/PostgreSQL;
- Alembic migrations;
- CRM entities and RBAC;
- admin frontend;
- tests with external AI mocked.

The correct strategy is **evolution, not rewrite**.

## Migration sequence

### Step 1 — Freeze current behavior with tests
Owner: Backend + QA
- Add regression tests for current screening/profile confirmation flow.
- Add regression tests for CRM client creation bridge.
- Document current DB tables and relationships.

### Step 2 — Introduce canonical identity and assessment domains
Owner: Backend
- Keep current Telegram IDs for compatibility.
- Add canonical User/AuthIdentity/Consent/AssessmentSession structures.
- Create migration adapters from current screening records.
- Do not delete old columns until new flow is verified.

### Step 3 — Extract AI access behind AI Gateway
Owner: AI Engineer + Backend
- Wrap current Claude call without changing user behavior first.
- Add prompt version, trace, schema validation, cost/latency fields.
- Then split Evidence Extractor and Profile Synthesizer.

### Step 4 — Add Evidence/Profile v2 alongside current profile
Owner: Backend + AI + Methodology
- Dual-write or migration-based transition.
- Compare old vs new output on same cases.
- Switch reads only after QA gate.

### Step 5 — Build Scenario/Direction/Roadmap modules
Owner: Backend + Frontend + AI
- New domain tables and APIs.
- Telegram can expose simple cards/buttons; web becomes richer product UI.

### Step 6 — Evolve CRM into Guide OS
Owner: Frontend + Backend
- Reuse existing Client/RBAC foundation where it does not conflict with canonical User/ClientRelationship model.
- Avoid two competing client sources of truth.

## Role ownership matrix

| Workstream | Accountable | Responsible | Reviewers |
|---|---|---|---|
| Product promise / scope | Founder | Head of Product | Tech Lead, Methodology |
| Architecture / DB / API | Tech Lead | Backend | AI, QA |
| Assessment methodology | Methodology Lead | Methodology + AI | Product |
| AI Gateway / evals | AI Lead | AI Engineer | Tech Lead, Methodology |
| B2C web/PWA | Head of Product | Frontend | Design, QA |
| Guide OS | Head of Product | Frontend + Backend | Guides, QA |
| Analytics | Product | Data/Backend | Founder, Tech Lead |
| Security/privacy | Tech Lead | Backend + external reviewer | Product |
| CI/CD/infra | Tech Lead | DevOps/Backend | QA |

## Sprint 0 — 1 week

**Tech Lead**
- review PR #11 architecture;
- map current tables to target ERD;
- approve migration strategy;
- confirm modular-monolith folder boundaries.

**Backend**
- inventory current models/routes/services;
- add missing regression tests;
- draft Alembic migrations for canonical User/Assessment/Evidence skeleton.

**AI Engineer**
- inventory all direct Anthropic calls;
- design gateway interface;
- capture current prompts as version `legacy-screening-v1`;
- create first 10 golden test cases.

**Frontend**
- audit current dashboard;
- prototype User report: Profile → 3 Scenario cards → Direction CTA;
- prototype Guide Client 360 information architecture.

**Methodology**
- freeze v1 dimensions and claim taxonomy;
- define evidence rubric and confidence rubric;
- review the first 10 golden cases manually.

**QA**
- define critical E2E scenarios;
- verify current screening and CRM as baseline.

### Sprint 0 status at exit (see `docs/engineering/12_SPRINT_0_EXIT_REPORT.md` for full detail)

Actually completed, against the task list above:

- **Tech Lead:** table→ERD mapping done (`10_CURRENT_TO_TARGET_MIGRATION_MAP.md`). PR #11 architecture review, migration-strategy approval, and folder-boundary confirmation are still Mykola's own pending actions, not something this work could complete on his behalf.
- **Backend:** model/route/service inventory and regression tests done (61→117 tests). Canonical User/Assessment/Evidence Alembic migrations were **not** drafted — deliberately deferred; `AuthIdentity`'s shape is still unspecified (`11_TECHNICAL_DEBT_REGISTER.md` Item 5), and no schema/migration was authorized for Sprint 0.
- **AI Engineer:** Anthropic call inventory, gateway interface, and `legacy-screening-v1` registration all done (`app/ai_gateway.py`). Ten synthetic example cases exist (`evals/golden/`) — draft, not yet the "first 10 golden test cases" in the sense of real reviewed cases, since no real/consented data was available and none should be used yet (see `11_TECHNICAL_DEBT_REGISTER.md` Item 13, no consent tracking exists).
- **Frontend:** not touched — out of scope for the engineering-only Sprint 0 work that actually ran; still open.
- **Methodology:** taxonomy freeze **not** done. Founder/Product instead decided (recorded in `11_TECHNICAL_DEBT_REGISTER.md`) that taxonomies will be versioned starting at v1, with the actual v1 design still to come — a real, tracked blocker for R1, not a completed step.
- **QA:** E2E baseline done (Part 1); a dedicated migration regression checklist was not produced as a separate artifact — the debt register and migration map serve that purpose today.

## Sprint 1 — 2 weeks

Target issues: #1, #2, #7 + minimal #9.

Deliverable:
`real user → resumable assessment → evidence-backed structured profile → admin QA`

No Scenario/Roadmap scope until this works reliably.

## Sprint 2 — 2 weeks

Target issues: #3, #4, #5, #8.

Deliverable:
`profile → 3 scenarios → direction → 90-day roadmap` with product analytics.

## Sprint 3 — 2 weeks

Target issues: #6, #10 + hardening.

Deliverable:
`Guide → Client 360 → session prep → roadmap execution` with correct consent/RBAC.

## Founder weekly dashboard

- active test users;
- completion rate;
- median relevance/actionability;
- critical AI error count;
- evidence grounding rate;
- direction selection rate;
- roadmap activation rate;
- meaningful actions completed;
- Guide prep-time saved;
- open P0 blockers.

Founder should not manage developer subtasks. Tech Lead owns technical breakdown and delivery; Founder owns priorities and release gates.
