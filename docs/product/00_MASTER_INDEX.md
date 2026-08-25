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
10. `docs/engineering/09_MIGRATION_AND_TEAM_OWNERSHIP.md` — migration sequencing and role ownership.
11. `docs/engineering/10_CURRENT_TO_TARGET_MIGRATION_MAP.md` — every current ICAN 1.1 table mapped to its target ERD counterpart.
12. `docs/engineering/11_TECHNICAL_DEBT_REGISTER.md` — tracked debt/risk inventory (severity, blast radius, owner).
13. `docs/engineering/12_SPRINT_0_EXIT_REPORT.md` — Sprint 0 completion status and GO/NO-GO recommendation for Issue #1.

## Sprint 0 baseline (as of exit — see `docs/engineering/12_SPRINT_0_EXIT_REPORT.md` for full detail)

- ICAN 1.1 (Telegram bot + FastAPI + CRM) is the current, working baseline — evolution, not rewrite (`docs/engineering/09_MIGRATION_AND_TEAM_OWNERSHIP.md`).
- An AI Gateway (`app/ai_gateway.py`) now sits between all business logic and the LLM provider; the existing screening call is registered as prompt version `legacy-screening-v1`. No other AI behavior has changed.
- A golden-dataset structure exists (`evals/golden/`) with 10 synthetic example cases for screening. No automated eval runner exists yet.
- `docs/engineering/10_CURRENT_TO_TARGET_MIGRATION_MAP.md` and `docs/engineering/11_TECHNICAL_DEBT_REGISTER.md` exist and should be read before starting any Issue #1–#10 work — several real blockers and open spec gaps are tracked there and are not yet resolved.

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
