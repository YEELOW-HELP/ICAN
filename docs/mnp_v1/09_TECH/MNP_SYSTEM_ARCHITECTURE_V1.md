# MNP SYSTEM ARCHITECTURE V1

## Recommended modular monolith for V1
Avoid premature microservices.

Modules:
- Identity/Auth
- Documents/Resume Parser
- Career Card
- Taxonomy/Skills
- Career KB
- Matching Engine
- Feasibility
- Transition/Gap/Route
- Market Data
- Opportunities/Learning
- Admin
- Analytics/Audit

## Boundaries
Matching engine is pure/deterministic where possible and accepts immutable snapshots.
External sources are adapters.
Career KB updates do not require engine code changes.

## Background jobs
data import, market refresh, file extraction, recalculation, scheduled review flags.

## Storage
relational DB for canonical/versioned data; object storage for CVs; optional search index only when catalog/search scale justifies it.

## Observability
structured logs, job status, parser diagnostics, engine version, data versions, error tracking.
