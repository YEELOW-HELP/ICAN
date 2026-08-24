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
