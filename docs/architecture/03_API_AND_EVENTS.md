# API & Event Contracts v3.1

> Platform target contracts. «МОЖУ: Мій Напрям» V1
> (`docs/product/14_MIY_NAPRYAM_V1_PRODUCT_DEFINITION.md`) implements the
> Identity, Discovery, and Profile/Evidence sections below, a Direction
> Intelligence endpoint set replacing "Careers / Scenarios" 1:1 in shape
> (TOP 3 + Alternative 3 instead of an arbitrary scenario list), and a new
> Product Access/payment surface not yet listed here. Roadmap, Opportunities,
> Guide OS, and Billing/Referral sections below are not implemented in V1.

## Principles

- OpenAPI 3.1 is the source of truth for HTTP endpoints.
- Async jobs/events have versioned schemas.
- Idempotency is mandatory for payments, invitations, generation jobs and retries.
- No endpoint may trust client-side role/tenant claims without server validation.

## Core HTTP API

### Identity
- `POST /v1/auth/telegram`
- `POST /v1/auth/email/start`
- `POST /v1/auth/email/verify`
- `GET /v1/me`
- `PATCH /v1/me`
- `GET /v1/me/consents`
- `POST /v1/me/consents`
- `DELETE /v1/me`
- `GET /v1/me/export`

Each `/v1/auth/{provider}` endpoint creates or matches an `AUTH_IDENTITY`
row (`docs/architecture/02_ERD.md`) and resolves it to a canonical `USER` —
a Telegram id (or any other provider id) authenticates a channel, it never
*is* the user. `POST /v1/me/consents` writes a `CONSENT` row per the
hardened Consent architecture (versioned, purpose-specific, traceable to
`granted_by_user_id`, withdrawable).

### Discovery
- `POST /v1/assessments`
- `GET /v1/assessments/{id}`
- `GET /v1/assessments/{id}/next-question`
- `POST /v1/assessments/{id}/answers`
- `POST /v1/assessments/{id}/pause`
- `POST /v1/assessments/{id}/complete`

### Profile / Evidence
- `GET /v1/me/potential-profile`
- `GET /v1/me/potential-profile/claims/{claim_id}`
- `GET /v1/me/evidence/{evidence_id}`
- `POST /v1/me/potential-profile/recompute`

### Careers / Scenarios
- `GET /v1/careers`
- `GET /v1/careers/{id}`
- `POST /v1/me/scenarios/generate`
- `GET /v1/me/scenarios`
- `POST /v1/me/direction`

### Roadmap
- `POST /v1/me/roadmaps`
- `GET /v1/me/roadmaps/active`
- `POST /v1/me/roadmaps/{id}/replan`
- `PATCH /v1/me/tasks/{task_id}`
- `POST /v1/me/tasks/{task_id}/evidence`

`{task_id}` here refers to `ROADMAP_TASK` (`docs/architecture/02_ERD.md`) —
a candidate-facing roadmap execution step. It is unrelated to the CRM's own
internal `Task` (staff operational reminders); the URL segment name is kept
as `tasks` for a clean public API, the entity behind it is not ambiguous in
the ERD.

### Opportunities
- `GET /v1/me/opportunities`
- `GET /v1/opportunities/{id}`
- `POST /v1/me/opportunity-matches/{id}/feedback`
- `POST /v1/me/opportunity-matches/{id}/applications`

### Mentor
- `POST /v1/me/mentor/messages`
- `POST /v1/me/mentor/actions/{action}`

### Guide OS
- `GET /v1/guide/dashboard`
- `GET /v1/guide/leads`
- `GET /v1/guide/clients`
- `GET /v1/guide/clients/{client_id}`
- `POST /v1/guide/clients/{client_id}/sessions`
- `POST /v1/guide/clients/{client_id}/tasks`
- `POST /v1/guide/clients/{client_id}/notes`
- `GET /v1/guide/earnings`

### Billing / Referral
- `POST /v1/checkout`
- `POST /v1/webhooks/payments/{provider}`
- `GET /v1/me/subscription`
- `POST /v1/referrals`

## Event envelope

```json
{
  "event_id": "uuid",
  "event_name": "direction_selected",
  "event_version": 1,
  "occurred_at": "2026-08-24T10:00:00Z",
  "user_id": "uuid-or-null",
  "tenant_id": "uuid-or-null",
  "session_id": "uuid-or-null",
  "trace_id": "uuid",
  "source": "web|telegram|api|worker|admin",
  "properties": {}
}
```

## Minimum product events

`landing_view`, `signup_completed`, `consent_granted`, `assessment_started`, `answer_submitted`, `assessment_paused`, `discovery_completed`, `profile_generation_started`, `profile_generated`, `profile_viewed`, `evidence_expanded`, `scenario_generated`, `scenario_viewed`, `scenario_compared`, `direction_selected`, `roadmap_generated`, `roadmap_activated`, `task_started`, `task_completed`, `task_blocked`, `opportunity_viewed`, `opportunity_saved`, `opportunity_applied`, `guide_invited`, `session_booked`, `session_completed`, `outcome_recorded`, `payment_succeeded`, `refund_completed`, `referral_converted`.

## Error model

All API errors:

```json
{
  "error": {
    "code": "ASSESSMENT_NOT_COMPLETE",
    "message": "Human-readable localized message",
    "trace_id": "uuid",
    "details": {}
  }
}
```

## Contract tests

Every P0 endpoint must have:
- auth/permission test;
- valid request test;
- invalid schema test;
- tenant isolation test where applicable;
- retry/idempotency test where applicable;
- analytics event assertion for key product actions.
