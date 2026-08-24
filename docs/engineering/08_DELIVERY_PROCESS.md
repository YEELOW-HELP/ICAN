# Engineering Delivery Process

## Branching

- `master` — protected production branch.
- Feature branches: `feat/<issue>-short-name`.
- Fixes: `fix/<issue>-short-name`.
- Docs: `docs/<issue>-short-name`.
- No direct production feature commits to `master` after branch protection is enabled.

## Pull request template

Every PR must contain:
1. Problem / user value.
2. Scope.
3. Acceptance criteria checked.
4. API/data changes.
5. AI prompt/model changes.
6. Privacy/security impact.
7. Test evidence.
8. Screenshots for UI.
9. Rollback / feature flag.

## CI pipeline

Required jobs:
- format/lint;
- unit tests;
- integration tests;
- migration check;
- secret scan;
- dependency/security scan;
- AI eval subset when AI-related files change;
- build/package check.

Later:
- E2E browser tests;
- accessibility checks;
- staging smoke test;
- performance regression.

## Environments

### Local
Developer machine; fake/isolated integrations.

### Staging
Production-like DB schema and workers; test payment provider; separate Telegram bot; no production secrets/data.

### Production
Protected credentials and DB; monitored migrations; controlled AI/prompt rollout.

## Database migrations

- Alembic remains canonical for Python backend.
- Every schema change is migration-based.
- Never edit an applied migration; create a new one.
- Backfill large data asynchronously when possible.
- Migrations must be safe for rolling deploys where possible.

## Issue lifecycle

`Backlog → Ready → In Progress → In Review → Staging QA → Done`

A ticket is **Ready** only if it contains:
- user story/problem;
- acceptance criteria;
- design/API reference where required;
- dependencies;
- analytics event;
- priority/release.

## Release cadence

- Continuous staging deployment.
- Production release at least weekly while early-stage, but gated by quality.
- AI model/prompt changes can release independently via registry + flags after eval.

## Incident severity

- **SEV1**: data exposure, payments, auth breach, widespread unusable core flow.
- **SEV2**: significant feature failure, AI produces unsafe/incorrect published outputs at scale.
- **SEV3**: degraded UX or isolated bug.

For SEV1/2: stop/disable feature, preserve evidence, assign incident lead, document timeline and corrective actions.

## Team rituals

- Monday: 30 min release/backlog alignment.
- Daily: short engineering standup focused on blockers.
- Friday: product demo on staging + metrics + user learnings.
- Every 2 weeks: architecture/tech debt review.
- Every AI release: eval report review.

## Founder/Product gate

Founder does not approve implementation details. Founder/Product owns:
- problem priority;
- user promise;
- release gate;
- key UX/outcome decisions.

Tech Lead owns architecture, security and engineering quality. Methodology Lead owns assessment claims and validation.
