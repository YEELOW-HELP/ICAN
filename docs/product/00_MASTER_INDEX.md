# МОЖУ / ICAN — Product Development System v3.1

> Canonical engineering index for **МОЖУ: Мій напрям** and the wider Human Development OS.

## Product loop

`Human Profile → 3 Scenarios → Direction → 90-day Roadmap → Action → Opportunity → Outcome → Replan`

## Engineering principle

Build one excellent closed loop first. Do not implement the full vision in parallel.

## Source of truth

1. `docs/product/00_MASTER_INDEX.md` — this index.
2. `docs/architecture/01_SYSTEM_ARCHITECTURE.md` — system boundaries and runtime architecture.
3. `docs/architecture/02_ERD.md` — canonical domain data model.
4. `docs/architecture/03_API_AND_EVENTS.md` — external/internal contracts.
5. `docs/architecture/04_AI_SYSTEM.md` — AI gateway, prompts, evidence, evals.
6. `docs/product/05_RELEASE_PLAN.md` — R0→R5 gates.
7. `docs/product/06_R0_R1_BACKLOG.md` — immediate engineering scope.
8. `docs/engineering/07_DEFINITION_OF_DONE.md` — quality gate for every ticket.
9. `docs/engineering/08_DELIVERY_PROCESS.md` — branches, PRs, CI/CD, environments.

## Releases

| Release | Goal | Build only if previous gate passed |
|---|---|---|
| R0 Prototype | 10 users complete Profile → Scenarios | yes |
| R1 Alpha | Evidence Graph + Direction + Roadmap + basic Guide CRM | yes |
| R2 Beta | Payments, referrals, Guide dashboard, mentor, analytics | yes |
| R3 Product | Opportunity Graph, automations, QA | yes |
| R4 Institution | Tenants, cohorts, dashboards | yes |
| R5 Scale | Marketplace, advanced aptitude, localization | yes |

## Current team focus

### P0
- Identity + consent
- Adaptive assessment engine
- Structured Human Potential Profile
- Evidence Graph
- Career seed graph
- Scenario Engine
- Direction selection
- 90-day Roadmap
- Guide Client 360
- AI Gateway + evals
- Product analytics
- Admin QA

### Not now
- Native mobile apps
- Full NMT Tutor
- Full marketplace
- Complex B2G integrations
- Autonomous multi-agent swarm
- MLM compensation
- Custom LMS

## Decision rule

Every feature must answer at least one of these questions:
1. Does it improve recommendation quality?
2. Does it move a user to a measurable action/outcome?
3. Does it make a Guide materially more productive?
4. Does it create a reusable data/network moat?

If the answer is **no to all four**, it does not enter the current roadmap.
