# Release Plan R0 → R5

## Rule

A release date is not a reason to advance. Advance only after the exit gate is met.

## Relationship to «МОЖУ: Мій Напрям» V1

The Founder Product Reconciliation fixed **«МОЖУ: Мій Напрям» V1**
(`docs/product/14_MIY_NAPRYAM_V1_PRODUCT_DEFINITION.md`) as the concrete
commercial product being built across R0/R1. It is a real, narrower,
paid-from-day-one product, not merely a "prototype" in the sense R0 implies
below — but it is built on exactly this R0/R1 foundation and does not
change the platform's longer-term R2→R5 destination. Where R0's scope below
says "three scenarios," read it as V1's "TOP 3 + Alternative 3 directions"
(doc 14 §11) — the engineering is the same, the product framing evolved.
See `docs/product/15_MIY_NAPRYAM_V1_IMPLEMENTATION_ROADMAP.md` for the
actual build sequence and stage-by-stage exit criteria V1 uses in practice.

## R0 — Prototype

**Goal:** prove the core insight loop.

Scope:
- assessment session;
- answers saved/resumable;
- structured profile;
- evidence links;
- three scenarios;
- founder/admin review UI.

Exit gate:
- 10 founder-reviewed real cases;
- no critical invented facts;
- at least 8/10 median perceived relevance in the small test;
- clear error taxonomy.

## R1 — Alpha

**Goal:** Direction → Roadmap becomes a real product.

Scope:
- consent and identity cleanup;
- Career seed graph;
- scenario scoring/explainability;
- direction decision;
- 90-day roadmap + tasks;
- Client 360 for Guide;
- AI gateway and evals; *(gateway wrapper delivered ahead of schedule in Sprint 0 — `app/ai_gateway.py`, `legacy-screening-v1`, no retries/fallback/schema-validation yet; golden dataset structure exists with 10/20 example cases and no runner — see `docs/engineering/12_SPRINT_0_EXIT_REPORT.md`)*
- event analytics.

Exit gate:
- 30–50 users;
- ≥80% critical claims evidence-linked;
- ≥75% assessment completion;
- median actionability ≥8/10;
- Guide can prepare for a user in <20 min using the system.

## R2 — Beta

Scope:
- payment catalog/checkout;
- referral attribution;
- Guide dashboard;
- session workspace;
- basic AI Mentor;
- automated nudges;
- product dashboards.

Exit gate:
- 100–200 users from both warm and cold traffic;
- first paid conversions;
- 10 active Founding Guides;
- measurable prep-time reduction;
- NPS baseline and CAC baseline established.

## R3 — Product

Scope:
- Opportunity Graph ingestion;
- verified opportunity matching;
- outcome check-ins;
- QA queues;
- billing/commission ledger;
- Guide quality metrics.

Exit gate:
- 500+ cumulative users only if quality gates remain healthy;
- 30+ active Guides;
- outcome data at 30/90 days;
- positive contribution margin on at least one paid flow or documented subsidy model.

## R4 — Institution

Scope:
- tenant model exposed in UI;
- cohorts/programs;
- aggregated privacy-safe analytics;
- organization billing;
- SSO-ready architecture;
- pilot reporting.

Exit gate:
- 3–5 real institutional pilots;
- signed data/privacy model;
- institution user can run a cohort without engineering involvement.

## R5 — Scale

Scope:
- Guide Marketplace;
- advanced aptitude layer after validation;
- NMT/Admission modules where separately validated;
- English localization;
- stronger integrations and data ingestion;
- performance/security hardening.

Scale gate:
- ≥80% completion on target flow;
- usefulness/actionability ≥8/10;
- NPS ≥45 or segment-equivalent justification;
- fabricated external facts = 0;
- evidence grounding target ≥98%;
- 30+ retained active Guides;
- 3–5 successful institutional pilots;
- restore drill + incident process + external security review.
