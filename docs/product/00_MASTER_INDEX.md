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
14. `docs/engineering/13_FOUNDER_ARCHITECTURE_REVIEW.md` — target-architecture hardening (AuthIdentity, Consent, versioned taxonomy, ClientAssignment, InterviewMessage, AuditLog, AiTrace) ahead of Issue #1.
15. **`docs/product/14_MIY_NAPRYAM_V1_PRODUCT_DEFINITION.md` — source of truth for the first commercial product, «МОЖУ: Мій Напрям» V1.**
16. **`docs/product/15_MIY_NAPRYAM_V1_IMPLEMENTATION_ROADMAP.md` — V1's staged implementation sequence and the Issue #1–#10 scope reconciliation.**
17. **`docs/product/25_MNP_PRODUCT_MOAT_AND_POSITIONING_V1.md` — Founder / Product Source of Truth for MNP positioning, competitive moat, strategic product boundaries, Person KB → Career KB → Market KB sequence, and long-term Career Decision/Transition strategy.**

## Platform architecture vs. V1 implementation scope

Everything in `docs/architecture/*` and the rest of this index describes
the **platform target architecture** — the full, global, multi-channel
Human Development OS. It remains the destination and is not reduced by the
V1 pivot below.

**`docs/product/14_MIY_NAPRYAM_V1_PRODUCT_DEFINITION.md` is the current
commercial scope** — a deliberately narrow, intentionally-shippable first
product built as a subset of this same architecture. If a capability is in
`docs/architecture/*` but not listed in doc 14's scope, **do not build it
yet** — see doc 14 §23 ("Explicitly NOT in V1") and
`docs/product/06_R0_R1_BACKLOG.md`'s V1 scope notes.

`docs/product/25_MNP_PRODUCT_MOAT_AND_POSITIONING_V1.md` governs **why the
product exists, where its competitive boundary sits, what should become the
data/product moat, and the Founder-approved sequence Career KB → Person KB →
Matching/Transition validation → Market KB Ukraine → Opportunities**. It does
not override the approved matching methodology or canonical engineering
contracts.

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

**As of the Founder Product Reconciliation, "current team focus" means
building `docs/product/14_MIY_NAPRYAM_V1_PRODUCT_DEFINITION.md`, staged per
`docs/product/15_MIY_NAPRYAM_V1_IMPLEMENTATION_ROADMAP.md`.** The P0 list
below is the platform's long-term priority list; it is not a build order,
and several of its items are explicitly narrowed for V1 (see doc 14 §26 and
doc 15's reconciliation) — "Scenario Engine" ships as Direction
Intelligence (TOP 3 + Alternative 3, not necessarily Safe/Growth/Bold),
"90-day Roadmap" ships as the high-level Route Builder only, "Guide Client
360" ships as the Consultant Review Workspace only, "Career seed graph"
ships as a curated Knowledge Base, not a full graph.

**Founder-approved data/product build order for the current MNP workstream:**

`Career KB V1 (5 careers) → Founder Acceptance → Person KB V1 → Founder Acceptance → Matching/Transition Validation → Market KB Ukraine → Opportunity/Action Layer → Scale.`

Do not skip forward to Market KB or Opportunities before the preceding layer is validated, except for separate research/data due-diligence work that does not change production scope.

### P0 (platform, long-term)
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

For the MNP career-navigation workstream, additionally ask:
5. Does it materially improve the Person, Career, Market or Transition model?
6. Does it help the user make a better career decision or execute the next step?

If the answer is **no to all applicable questions**, it does not enter the current roadmap.
