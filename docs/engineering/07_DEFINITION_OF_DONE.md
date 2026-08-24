# Definition of Done

A ticket is not Done because code was written. It is Done only when every applicable item below passes.

## Product
- Acceptance criteria are demonstrably met.
- Empty/loading/error/retry states exist.
- Copy is localized through translation mechanism, not hard-coded where user-facing.
- Analytics event(s) are emitted and validated.

## Backend
- API/schema migration is versioned.
- Permission and tenant ownership are enforced server-side.
- Input validation and stable error codes exist.
- Idempotency exists for retried side effects.
- No direct production DB workaround is required.

## AI
- Output uses a validated schema.
- Prompt/model version is recorded.
- Unsupported external facts are impossible or blocked by QA.
- Relevant eval cases are added/updated.
- Cost/latency trace is visible.

## Data / privacy
- PII collection is necessary for the feature.
- No PII leaks into logs or analytics.
- Consent purpose is respected.
- Delete/export behavior is understood.

## Frontend
- Mobile critical path tested.
- Keyboard/accessibility basics tested.
- Network failure/retry works.
- Permission-denied state is handled.

## Testing
- Unit tests for business rules.
- Integration test for persistence/API boundary.
- Critical E2E path where appropriate.
- Regression test for every fixed production bug.

## Operations
- Structured logs use trace IDs.
- Errors are observable/alertable where critical.
- Feature can be disabled/rolled back if risky.
- Runbook/admin action exists if human recovery is expected.

## Review
- PR has clear scope and screenshots/API examples where relevant.
- At least one reviewer other than author for production changes.
- CI green.
- Migration rollback/forward strategy considered.

## Release
- Staging verified.
- Feature flag/canary used for AI or high-risk changes.
- Product owner confirms acceptance criteria.
