# МОЖУ: Мій Напрям — V1 Implementation Roadmap

Companion to `docs/product/14_MIY_NAPRYAM_V1_PRODUCT_DEFINITION.md` (the
product source of truth). This document sequences V1 into vertical,
independently reviewable stages — each stage produces something a founder
can actually look at, not just an abstract epic checkbox. Stage numbering
here is planning order, not GitHub issue numbers; existing Issues #1–#10
map onto these stages per the reconciliation table below, several spanning
more than one stage.

Nothing in this document authorizes implementation by itself — each stage
still goes through its own readiness review and Founder approval, the same
process used for Issue #1 Part 0.

---

## How to read a stage

Every stage lists: **Goal**, **Dependencies**, **Backend**, **Frontend/
Admin**, **AI**, **Data**, **Tests**, **Acceptance criteria**,
**Deliverable**, and **What NOT to build yet**. A stage with nothing
meaningful under a heading omits it rather than padding it.

---

## Stage 0 — Foundation & Governance

**Goal:** the engineering ground V1 is built on is trustworthy before real
schema work starts.
**Dependencies:** none.
**Backend:** PostgreSQL CI verification (Sprint 1 Part 0 — **done**,
`sprint-1-issue-1-part-0-postgres-ci`, merged via PR #15).
**Tests:** Alembic chain applies to real Postgres in CI — done.
**Deliverable:** a CI pipeline that cannot silently accept a broken
migration.
**What NOT to build yet:** any V1 schema — this stage is infrastructure
only.

## Stage 1 — Canonical Identity, Consent, Product Access foundation

**Goal:** every subsequent stage has a real, channel-agnostic user and a
real consent record to hang work off, and a place for entitlement/access
state to live.
**Dependencies:** Stage 0.
**Backend:** `identity_users`/`auth_identities` (already fully specified —
`docs/architecture/02_ERD.md`'s `USER`/`AUTH_IDENTITY`, and already planned
as Issue #1 Part 1); a hardened `Consent` table per the Founder
Architecture Review's design (`granted_by_user_id`, `grantor_role`,
`policy_version`, `source`, `withdrawn_at`); a **new**, not-yet-specified
minimal Product Access / Entitlement schema (organization, package
purchase, promo code, redemption, attribution) — schema design is an
**open founder decision** (`14_...md` §27.3) and must go through its own
short architecture note before this stage's backend work starts, the same
way Identity went through the Founder Architecture Review before Issue #1
Part 1.
**Data:** no production backfill in this stage (per the existing Migration
Map's additive-first principle) — new users only, until a separate
reviewed cutover.
**Tests:** identity resolution, consent versioning/withdrawal, entitlement
redemption idempotency (a promo code must not be redeemable twice).
**Acceptance criteria:** a user can be created via Telegram `AuthIdentity`,
grant consent, and redeem a promo code or complete a payment stub, ending
up with a recorded, queryable "has access" state.
**Deliverable:** the identity + consent + entitlement foundation every
later stage authenticates and authorizes against.
**What NOT to build yet:** a real payment provider integration (Stage 11);
organization-facing self-serve purchasing UI (manual/admin-issued packages
are enough here).

## Stage 2 — Assessment Engine core (state machine + Structured mode)

**Goal:** the channel-agnostic assessment state machine exists and the
cheapest, lowest-risk mode (Structured) proves it end-to-end.
**Dependencies:** Stage 1.
**Backend:** `InterviewSession`/`Answer`/`InterviewMessage` and the
`draft → active → paused → complete → processing → ready → failed` state
machine — already fully specified in the Issue #1 readiness review (Parts
2–3 of that plan). Structured mode's question bank is a fixed, versioned,
deterministic list — minimal/zero LLM calls.
**AI:** none required for Structured mode itself.
**Tests:** full state-transition table (valid + invalid), idempotent
answer submission, resume-after-restart.
**Acceptance criteria:** a user can complete a Structured assessment,
pause and resume it (including across a simulated process restart), and
duplicate submissions never double-record or double-charge AI cost (moot
here, but the mechanism must already be correct for Stage 3).
**Deliverable:** a working, tested Assessment Engine core, exercised by
the mode that has the least AI risk.
**What NOT to build yet:** Hybrid/Conversation/CV modes (Stage 3); Direction
Intelligence; anything report-shaped.

## Stage 3 — Hybrid mode + CV-assisted evidence

**Goal:** the actual V1 default paid experience works.
**Dependencies:** Stage 2; reuses `AIGateway`/`ScreeningAgent`-shaped
extraction unchanged (no new provider integration).
**Backend:** the adaptive next-question service (completeness/evidence/
confidence/contradiction-driven selection, traceable reason — Issue #1
Part 4's design), CV upload wired into the same evidence pipeline as a
source, not a parallel path.
**AI:** extraction logic is the existing legacy-screening-v1-shaped call
through `AIGateway`, evolved to also flag confidence/contradiction signals
into structured fields (`Answer.confidence`, `Answer.contradicts_previous`)
rather than only prose.
**Tests:** already-resolved facts never re-asked; contradiction detection;
low-confidence re-ask; CV facts treated as high-confidence answers; target
duration stays in the 20–30 minute band under realistic question-bank
sizing (a product/UX check, not just a unit test).
**Acceptance criteria:** a user can complete Hybrid with or without a CV,
pausing/resuming freely, and never gets re-asked something they already
told the system (except on a genuine contradiction).
**Deliverable:** the actual assessment experience V1 sells.
**What NOT to build yet:** Direction Intelligence, Knowledge Base,
reporting — Hybrid's output at the end of this stage is a completed,
evidence-linked session, nothing user-facing beyond that yet.

## Stage 4 — Evidence / Human Potential Profile

**Goal:** raw evidence becomes a structured, versioned profile.
**Dependencies:** Stage 3.
**Backend:** `POTENTIAL_PROFILE`/`PROFILE_CLAIM` population from
`Answer`/`Evidence` rows; profile regeneration creates a new version,
never overwrites.
**AI:** a profile-synthesis pass (Issue #2 territory, scoped down to
exactly what a V1 report needs — not the full generalized Evidence Graph
research platform).
**Tests:** every high-impact claim has evidence or an explicit
low-confidence/hypothesis status; regeneration preserves history; schema
validates before persistence.
**Acceptance criteria:** given a completed Hybrid session, the system
produces a structured profile a human could audit claim-by-claim back to
its source.
**Deliverable:** the Human Potential Profile, ready to feed Direction
Intelligence.
**What NOT to build yet:** direction generation itself (Stage 5); the
report (Stage 9).

## Stage 5 — Direction Intelligence foundation

**Goal:** the core intelligence module of V1 exists as its own bounded
component, producing TOP 3 + Alternative 3.
**Dependencies:** Stage 4.
**Backend:** a dedicated Direction Intelligence service (not inline prompt
logic) consuming Profile + Evidence + Constraints (+ a minimal/seed
Knowledge Base from Stage 6, or a stub if sequenced in parallel) and
producing `SCENARIO`/`SCENARIO_SCORE`/`DIRECTION_DECISION`-shaped output —
`SCENARIO.scenario_type` free-text, no ERD change needed to drop Safe/
Growth/Bold.
**AI:** the recommendation pipeline from `04_AI_SYSTEM.md` (`hard
constraints → graph retrieval → scoring → evidence check → scenario
creation → QA critic → narrative`), scoped to V1's simpler retrieval
(curated seed knowledge, not a full graph).
**Tests:** hard constraints never violated; 6 directions returned;
confidence and fit reported as distinct values; no unsupported market
facts; QA critic catches fabrication before persistence.
**Acceptance criteria:** given a profile, the system produces 3 main + 3
alternative directions, each explained per `14_...md` §11's required
fields.
**Deliverable:** the module that actually makes «Мій Напрям» valuable.
**What NOT to build yet:** the full Career Knowledge Graph (Stage 6 is
seed-only); Route Builder (Stage 8); anything vacancy/university-shaped.

## Stage 6 — Knowledge Base (seed + architecture)

**Goal:** Direction Intelligence stops depending on raw LLM memory for
career facts.
**Dependencies:** can start in parallel with Stage 5, must land before
Stage 5 is trusted for real recommendations.
**Data:** a small (tens, not hundreds), manually curated, versioned seed of
career/direction knowledge with provenance — mirroring the already-accepted
`TAXONOMY`/`TAXONOMY_VERSION`/`TAXONOMY_TERM` versioning pattern.
**Backend:** the retrieval interface Direction Intelligence calls — stable
even though the ingestion side behind it stays manual for V1.
**Tests:** every knowledge item used in an output carries source/date;
retrieval is deterministic for a given query + KB version.
**Acceptance criteria:** Direction Intelligence's factual career claims can
all be traced to a specific, dated Knowledge Base entry.
**Deliverable:** the architecture from `14_...md` §12, populated with a
V1-sufficient seed, not a scraping pipeline.
**What NOT to build yet:** automated ingestion from external sources;
community-source integration (Reddit, open datasets) — named as future
work only.

## Stage 7 — Direction evals

**Goal:** Direction Intelligence's quality is measured, not assumed.
**Dependencies:** Stage 5, Stage 6.
**Data:** extend `evals/golden/` with a new `target=scenario_generation`
(already a reserved, empty folder per Sprint 0 Part 5's structure) case
set — synthetic profiles → expected direction-quality criteria.
**Tests:** the golden-dataset schema validation pattern from Sprint 0 Part
5 applies unchanged; no eval runner is required to exist yet (same
scoping call already made for Sprint 0) — but at least a handful of
reviewed cases should exist before Direction Intelligence output reaches
real users.
**Acceptance criteria:** a documented, reviewed set of expected-good and
expected-bad direction outputs exists for regression checking, even if run
manually for V1.
**Deliverable:** the beginning of real quality assurance for the module
that matters most.
**What NOT to build yet:** an automated eval runner (still out of scope,
same as the rest of `evals/golden/`).

## Stage 8 — Route Builder

**Goal:** directions become an understandable next-steps path.
**Dependencies:** Stage 5.
**Backend:** depends on the open founder decision in `14_...md` §27.2 —
either a thin, V1-only structure, or a deliberately minimal usage of the
existing `ROADMAP`/`MILESTONE`/`ROADMAP_TASK` entities. This stage should
not start implementation until that decision is made.
**Tests:** every route has the four required stages (current state, gaps,
next steps, target); no vacancy/university content leaks in.
**Acceptance criteria:** every main direction a user receives comes with a
route matching `14_...md` §13's structure.
**Deliverable:** the last structured-data component before the report.
**What NOT to build yet:** replanning, task execution states, milestone
tracking, effort estimation — that's the full Roadmap Engine, later.

## Stage 9 — Report generation

**Goal:** structured output becomes a report a human can read (in draft
form; approval is Stage 10).
**Dependencies:** Stage 8.
**Backend:** report assembly service turning Profile + Directions + Routes
into the `14_...md` §16 structure; PDF/web rendering capability (format
only — publishing gated by Stage 10).
**Tests:** report renders correctly across all 13 required sections; no
raw JSON ever reaches this layer's output.
**Acceptance criteria:** a draft report exists in a human-readable format,
in `draft` state, not yet visible to the end user.
**Deliverable:** the artifact the review workflow operates on.
**What NOT to build yet:** publishing/delivery to the user — blocked by
Stage 10 by design.

## Stage 10 — Human Review Console

**Goal:** the non-negotiable review gate is real, server-enforced, and
operable by a human.
**Dependencies:** Stage 9; Stage 1 (RBAC roles).
**Backend:** the report review state machine (`14_...md` §14/§27.4 — states
and transitions to be specified in this stage's own short design note,
mirroring how Issue #1's state machine got its own spec); server-side RBAC
for `SUPER_ADMIN`/`ADMIN`/`MANAGER`/`CONSULTANT`/`REVIEWER`.
**Frontend/Admin:** the consultant workspace and admin dashboard from
`14_...md` §15 — new, but structurally similar to the existing
`admin_frontend`/CRM dashboard pattern already in the codebase.
**Tests:** a report cannot reach the user without an `approved` state,
enforced by the state machine itself (attempt-and-fail tests, not just
"the UI doesn't show a button"); every privileged action produces an
`AUDIT_LOG` row.
**Acceptance criteria:** a consultant can review, edit, regenerate a
component, approve, or reject a draft report entirely through this
console; a rejected/unapproved report is provably unreachable by the end
user via any API path.
**Deliverable:** the mandatory human review gate, real and enforced.
**What NOT to build yet:** the full Guide OS (session booking, long-term
relationship tooling, Client 360 beyond what review needs).

## Stage 11 — Payment / Promo Code

**Goal:** V1 can actually take money and distribute organizational access.
**Dependencies:** Stage 1's entitlement schema.
**Backend:** a real payment provider integration behind the Stage 1
entitlement abstraction; promo code generation/redemption UI for
organizations (admin-issued for V1, no self-serve org portal required).
**Tests:** payment success/failure/webhook idempotency; promo code
single-use enforcement; attribution query (which package → which code →
which user) works end-to-end.
**Acceptance criteria:** a real user can pay BASIC or PREMIUM price and
immediately gain assessment access; an organization-issued code redeems
correctly and is attributed.
**Deliverable:** V1's actual monetization path.
**What NOT to build yet:** subscriptions, refund automation, invoicing,
multi-currency — a single one-time-purchase flow per plan is sufficient.

## Stage 12 — Free Structured Test funnel

**Goal:** the top-of-funnel lead magnet is live.
**Dependencies:** Stage 2 (Structured mode), a public website (outside this
repo's current scope unless the team builds it here — flagged as an open
question, not assumed).
**Frontend:** landing page, plan descriptions, FAQ, CTA, free test entry
point, hand-off into Telegram carrying enough context to avoid re-asking
what the free test already established.
**Tests:** free-test evidence actually carries into the paid flow (an
explicit integration test, not an assumption).
**Acceptance criteria:** a first-time visitor can complete the free test
and land in Telegram ready to pay or redeem a code, without re-entering
already-given facts.
**Deliverable:** the free funnel from `14_...md` §17.
**What NOT to build yet:** a full marketing site/CMS — a minimal, honest
landing page is enough for V1.

## Stage 13 — Analytics / QA minimal

**Goal:** V1's funnel and quality are measurable from day one.
**Dependencies:** Stages 2–11 (events exist wherever there's a milestone to
report).
**Backend:** structured event logging in the canonical envelope shape
(already the pattern used for the Assessment Engine's planned events),
review-queue metrics (time-to-review, edit rate, reject rate).
**Tests:** events fire at every named milestone; no PII in event
properties.
**Acceptance criteria:** a founder can see, at minimum, funnel drop-off
from free test → payment → completed assessment → approved report →
delivered report, plus basic AI cost/latency and review-queue health.
**Deliverable:** the minimum visibility needed to run the business, not a
full analytics platform.
**What NOT to build yet:** a dedicated analytics warehouse/BI tool — logs
and simple queries are enough for V1.

## Stage 14 — Closed Pilot

**Goal:** validate the entire funnel with real, small-scale, closely
watched usage before public commercial launch.
**Dependencies:** Stages 1–13 functionally complete.
**Process:** a small cohort (internal team, friendly users, and/or one
partner organization's promo-coded users) runs the full paid flow;
consultants review every report manually; founders read every report
before/alongside consultant review.
**Acceptance criteria:** the V1 Definition of Done (`14_...md` §22) holds
under real (if limited) usage; no report reached a user without approval;
no data-safety incident.
**Deliverable:** a go/no-go decision for commercial launch, backed by real
evidence instead of test-suite green checkmarks alone.

## Stage 15 — Commercial V1 launch

**Goal:** public availability.
**Dependencies:** Stage 14 passed.
**Process:** public website live, payment live, promo-code distribution
live for partner organizations, on-call/monitoring in place per
`docs/engineering/08_DELIVERY_PROCESS.md`'s incident-severity process.
**Deliverable:** «МОЖУ: Мій Напрям» V1, live and sellable.

---

## MVP internal / Closed pilot / Commercial V1

| Milestone | Stages | What's true at this point |
|---|---|---|
| **MVP internal** | 0–9 | The full pipeline works end-to-end technically (assessment → profile → directions → route → draft report). No real payment, no real review console, no real users — a founder/engineer can walk the pipeline manually. |
| **Closed pilot** | 0–14 | Real (small-scale) users, real human review console, real (or promo-only) access, tightly supervised. |
| **Commercial V1** | 0–15 | Public paid launch. |

---

## Realistic estimate

Order-of-magnitude, not a committed schedule — genuine uncertainty exists
around Stage 5 (Direction Intelligence quality) and Stage 10 (review
console UX), which are the two stages most likely to need iteration rather
than one clean pass.

| Track | Stages 0–9 (MVP internal) | Stages 10–13 (review + payment + funnel + analytics) | Stage 14 (pilot) | Total to commercial V1 |
|---|---|---|---|---|
| **AI-assisted solo / very small team** | ~4–6 weeks | ~3–5 weeks | ~2–4 weeks (calendar time, not effort — pilots need real elapsed time to say anything) | **~10–15 weeks** |
| **2–4 engineer team** | ~2–3 weeks | ~2–3 weeks | ~2–4 weeks calendar | **~6–10 weeks** |

These ranges assume: no team member is blocked waiting on the two open
founder decisions in `14_...md` §27 (Product Access schema, Route Builder
shape) — resolving those early is on the critical path, not a footnote.

---

## Issue #1–#10 reconciliation

Full rationale (summary table lives in `14_...md` §26):

### #1 — Assessment
**Decision: V1, scope updated.** Original scope (state machine, resume,
minimum-data rule) stays exactly as already planned in the Issue #1
readiness review. Added: the 4-mode requirement (`14_...md` §7), Hybrid as
default paid mode, optional CV as an evidence source rather than a
separate mode users pick instead of Hybrid, and the 20–30 minute target
duration as a product constraint on the question bank's size, not just an
engineering nicety.

### #2 — Evidence/Profile
**Decision: V1 critical, unchanged in substance.** Scoped down in practice
to exactly what a V1 report needs (Stage 4) rather than a generalized
research platform — the acceptance criteria in the issue text already
support this narrower reading without editing the issue itself.

### #3 — Scenario Engine: Safe / Growth / Bold
**Decision: REDEFINED.** The issue's literal scope ("Safe / Growth / Bold
scenario types") is superseded — Safe/Growth/Bold is not a required V1
product model. The underlying engineering (`SCENARIO`/`SCENARIO_SCORE`/
`DIRECTION_DECISION`, hard constraints, QA critic, schema-valid/versioned
output) carries forward unchanged; only the *labeling/count* of scenario
types changes, to Direction Intelligence's TOP 3 + Alternative 3
(`14_...md` §11). No ERD migration is implied — `scenario_type` was
already a free string.

### #4 — Career Knowledge Graph + matching v1
**Decision: V1-critical intelligence foundation, rescoped.** The issue's
"50–100 curated careers" target and hybrid matching pipeline survive
conceptually, but the framing shifts from "build a career graph" to "build
a curated, versioned Knowledge Base sufficient for Direction Intelligence"
(`14_...md` §12, Stage 6) — explicitly not a full world career graph, and
explicitly not automated ingestion in V1.

### #5 — Direction decision + 90-day Roadmap Engine
**Decision: PARTIAL V1.** Direction decision itself (comparing/selecting
among the 6 directions) stays in scope as designed. The 90-day Roadmap
Engine (milestones, tasks, replanning, execution tracking) is deferred;
V1 ships only the Route Builder's high-level path (`14_...md` §13, Stage
8).

### #6 — Guide OS: Client 360 + session workspace
**Decision: PARTIAL V1.** Only the Consultant Review Workspace needed for
the mandatory Human Review gate (`14_...md` §15, Stage 10) ships now. Full
Client 360, session booking, and long-term relationship tooling are
deferred to the real Guide OS epic.

### #7 — AI Gateway, prompt registry and evaluation suite
**Decision: V1 critical, unchanged.** Already substantially ahead of
schedule (Sprint 0 Part 4) — `app/ai_gateway.py` is the only provider call
site today. V1 adds no new AI provider integration, only new *tasks*
(Direction Intelligence, profile synthesis) routed through the existing
gateway.

### #8 — Product analytics + traceable event model
**Decision: V1 minimal.** Funnel events extended with V1's paid-funnel
milestones, AI quality/cost visibility (already emitted), and review-queue
metrics (Stage 13). Full analytics warehouse/dashboard tooling deferred.

### #9 — Admin QA console + audit trail
**Decision: V1 critical, extended.** This issue's scope ("failed/flagged
generation queue", "regenerate a component", "audit trail") is the natural
engineering home for §14/§15's mandatory human review gate — the issue is
not narrowed, it's the delivery vehicle for a now-non-negotiable V1 rule
rather than a QA nice-to-have.

### #10 — Canonical identity, consent and tenant permissions
**Decision: V1 critical, unchanged.** Already the explicit prerequisite for
Issue #1 per the Founder Architecture Review and the Issue #1 readiness
review. V1 adds the Product Access/Entitlement layer as a new, adjacent
concern (Stage 1) — not part of Issue #10's original scope, tracked
separately since it's genuinely new architecture (`14_...md` §27.3).

### #12 — Sprint 0
**Decision: history/foundation.** Not rewritten, not reopened. Sprint 0's
regression baseline, migration map, debt register, AI Gateway, and golden
dataset structure remain exactly as delivered and reviewed.

### #11 (not an epic — the original architecture PR)
No reconciliation needed; this document narrows the *implementation scope*
of the architecture #11 introduced, without changing that architecture.

---

## Governance note (repository, not product)

Per instruction: **master is not deleted, and `product-system-v3.1` is not
merged into master as part of this reconciliation.** Recorded recommendation
for a separate Founder repository-governance decision: keep
`product-system-v3.1` as the active integration branch through V1
stabilization; once V1 is validated (post-pilot), adopt a merge/rebase
strategy into `master` and use `master` as the protected production/
mainline branch from that point forward. Git history must be preserved
either way — no history-rewriting merge strategy should be used.
