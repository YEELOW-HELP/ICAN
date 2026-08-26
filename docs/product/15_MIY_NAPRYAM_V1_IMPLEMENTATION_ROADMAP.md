# МОЖУ: Мій Напрям — V1 Implementation Roadmap

Companion to `docs/product/14_MIY_NAPRYAM_V1_PRODUCT_DEFINITION.md` (the
product source of truth).

> **Execution model update (accelerated):** the Founder-authorized primary
> execution model is now **four large vertical stages** (below), replacing
> the original 16-stage sequence as the thing teams plan and branch against.
> The original 16-stage breakdown is kept as an **internal dependency/
> reference appendix** — useful for tracking what's inside a large stage
> and in what order, but it is no longer what gets reviewed/branched/merged
> stage-by-stage. Nothing in this document authorizes implementation by
> itself — each of the four stages still goes through its own readiness
> review and Founder approval, the same process used for Issue #1 Part 0.

---

## Authorized execution model: four stages

### STAGE 1 — Core + Paid Hybrid Assessment

**Goal:** a real user can enter through Telegram, obtain access, complete
Hybrid with or without CV, stop/resume, and reach a completed assessment
safely.

**Combines:**
- Canonical `User`/`AuthIdentity` (channel-agnostic identity — Telegram is
  a client, not the identity, per the Founder Architecture Review).
- Consent (hardened design: `granted_by_user_id`, `grantor_role`,
  `policy_version`, `source`, `withdrawn_at`).
- A minimal Product Access/Entitlement **skeleton** (enough to gate
  assessment start — see §27.2 in doc 14 for the still-open schema
  question; a stub/manual-grant is acceptable here, the real payment
  provider is Stage 4).
- Assessment state machine (`draft → active → paused → complete →
  processing → ready → failed`).
- `Answer` / `InterviewMessage` persistence.
- Idempotency (duplicate submission never double-records or double-charges
  AI cost).
- Autosave every answer.
- Pause/resume, including across a real process restart.
- The adaptive Hybrid interview (completeness/evidence/confidence/
  contradiction-driven next-question selection, traceable reason).
- Optional CV upload/extraction as an evidence source inside Hybrid, not a
  separate mode.
- The Telegram adapter.
- Feature flag / legacy-compatibility (existing ICAN 1.1 Telegram screening
  behavior stays untouched until this is explicitly cut over).
- Required tests and the PostgreSQL migration(s) this stage needs,
  verified through the CI job from Sprint 1 Part 0.

**Explicitly not in Stage 1:** the free Structured website funnel;
Conversation mode; Direction Intelligence.

**Deliverable:** a real user can enter through Telegram, obtain access,
complete Hybrid with or without CV, stop/resume, and reach a completed
assessment safely.

### STAGE 2 — Evidence + Human Potential Profile

**Goal:** a completed Hybrid assessment becomes an auditable structured
profile.

**Combines:**
- Evidence extraction; evidence/source links.
- Profile Claims; the Human Potential Profile itself.
- Confidence/hypothesis handling.
- Taxonomy/version references (`PROFILE_CLAIM.taxonomy_version_id`, per
  the Founder Architecture Review's versioned taxonomy architecture).
- AI trace/model/prompt provenance (already emitted by the AI Gateway;
  this stage is the first real *consumer* of that data on generated
  artifacts, not just logs).
- Versioned regeneration (a new version, never a silent overwrite).
- Profile-quality tests/evals.

**Deliverable:** a completed Hybrid assessment becomes an auditable
structured profile.

### STAGE 3 — Direction Intelligence + Routes + Report + Human Review

**Goal:** pilot-ready end-to-end product: Assessment → Profile →
Directions → Routes → Draft Report → Human Review → Approved Final Report.

**Combines (parallel internal work encouraged where dependencies permit —
see "Parallel work" below):**
- The curated/versioned Knowledge Base seed.
- Direction Intelligence: candidate generation/ranking, hard constraints,
  fit vs. confidence kept distinct, critic/verification, the direction
  eval dataset, TOP 3 + Alternative 3 output.
- Route Builder.
- Draft Report assembly + Web/PDF report rendering.
- Admin/Consultant Review Workspace.
- The mandatory server-side review state machine (Edit / Regenerate /
  Reject / Approve), with `AUDIT_LOG` for every privileged action.
- Final report delivery.

**This is the most quality-sensitive stage.** Knowledge Base, the Direction
engine, evals, report UI, and review UI should be developed in parallel
where dependencies allow, not artificially serialized into one long
critical path.

**Deliverable:** pilot-ready end-to-end product — Assessment → Profile →
Directions → Routes → Draft Report → Human Review → Approved Final Report.

### STAGE 4 — Commerce + Funnel + Commercial Launch

**Goal:** Commercial «МОЖУ: Мій Напрям» V1.

**Combines:**
- The real payment provider, BASIC/PREMIUM (§5 in doc 14, now fully
  decided — see below).
- Promo codes / organization packages.
- The landing website.
- The free Structured Test — built **here**, at launch stage, not earlier
  (see the assessment-mode correction below).
- Carrying free-test data into the paid flow.
- Telegram hand-off.
- Minimal analytics: funnel, review metrics, AI cost metrics.
- Security/hardening, final staging/pilot fixes, commercial release
  preparation.

**Deliverable:** Commercial «МОЖУ: Мій Напрям» V1.

---

## Parallel work

From Stage 1 onward, independent work may run in parallel **when safe**.
Examples:
- Direction/Knowledge methodology research can run while Stage 1 backend
  is built.
- Admin UI skeleton can begin while Stage 2's profile backend is built.
- Report UI/PDF design can run while Direction Intelligence (Stage 3) is
  being tested.
- The landing page (Stage 4) can be prepared before Stage 4's backend is
  complete.

**Constraint that does not relax:** parallel branches must never modify
the same unstable schema without coordination. A stage's schema is treated
as a shared, load-bearing resource the moment more than one branch touches
it — coordinate the migration, don't let two branches race to define the
same table differently.

## Engineering quality preserved under acceleration

Combining work into four large stages changes **granularity of review**,
not **rigor**. Unchanged:
- a separate feature branch per large Stage (not per sub-item);
- PostgreSQL CI (Sprint 1 Part 0's job) gates every stage's migrations;
- the full regression suite stays green at every merge;
- migration verification (chain integrity + real-Postgres execution);
- schema validation;
- security/privacy checks;
- audit/versioning (`AUDIT_LOG`, versioned profile/report artifacts);
- PR review;
- Founder-controlled merge — no stage merges itself.

---

## Products / pricing — Basic vs Premium (decided)

Carried from doc 14 §5, restated here since it drives Stage 1 and Stage 4
scope directly:

- **BASIC (~500 UAH):** paid Hybrid assessment, optional CV, human-reviewed
  final report, directions/routes, Telegram/Web/PDF delivery.
- **PREMIUM (~1000 UAH):** everything in BASIC, **plus a personal
  consultation/debrief with a career consultant.** Exact duration/process
  for the consultation is not decided yet and does not block Stage 1–3
  work — but the *functional* Basic/Premium split itself is no longer an
  open question.

This means Stage 3's Human Review Workspace and Stage 4's commerce work
should assume a consultant-facing consultation/debrief touchpoint exists
for PREMIUM buyers, even before its exact format is finalized.

## Assessment modes — Commercial V1 release requirement (corrected)

The architecture supports four assessment modes as a first-class concept
(doc 14 §7) — that has not changed. What was imprecise before is which of
those four **Commercial V1 release** actually requires:

| Mode | Commercial V1 release requirement |
|---|---|
| **Hybrid** | **Required** — the default paid flow, built in Stage 1. |
| **CV** | **Required as a capability/evidence source inside Hybrid** — not a standalone mode, not optional to build, but never a separate user-facing flow. |
| **Structured** | **Required for commercial launch, but built later** — at Stage 4 (free website lead magnet), not Stage 1. Architecture-compatible from day one; implementation is deliberately deferred. |
| **Conversation** | **Not a Commercial V1 release blocker.** Experimental/future; the architecture must remain compatible with it, but no V1 stage requires building it. |
| **Voice** | Future. Not part of any V1 stage. |

Any earlier wording implying "V1 requires all 4 modes" (as production user
flows, all built up front) is corrected by this table — the architecture
requirement (support 4 modes) and the release requirement (ship Hybrid+CV
now, Structured at launch, Conversation/Voice later) are different claims
and must not be conflated.

---

## MVP internal / Closed pilot / Commercial V1

| Milestone | Stage(s) | What's true at this point |
|---|---|---|
| **MVP internal** | 1–2 | The technical pipeline works end-to-end through a structured, auditable profile (assessment → evidence → profile). No directions, no report, no payment, no review console yet. |
| **Pilot-ready** | 1–3 | Full pipeline through an approved Final Report — Direction Intelligence, Routes, Report, and the mandatory Human Review gate all work. This is what a closed pilot cohort actually uses. |
| **Commercial V1** | 1–4 | Public paid launch — real payment, promo codes, landing site, free funnel, minimal analytics live. |

---

## Realistic estimate (Founder-set targets)

| Stage | Target |
|---|---|
| Stage 1 — Core + Paid Hybrid Assessment | ~5–8 calendar days |
| Stage 2 — Evidence + Human Potential Profile | ~5–7 days |
| Stage 3 — Direction Intelligence + Routes + Report + Human Review | ~10–14 days |
| Stage 4 — Commerce + Funnel + Commercial Launch | ~5–8 days |

| Milestone | Target |
|---|---|
| Internal MVP | ~2 weeks |
| Pilot-ready | ~4 weeks |
| Commercial V1 | ~5–7 weeks |

**These are aggressive, AI-assisted execution targets, not contractual
promises.** Quality gates, eval results, or product findings during Stage
3 in particular (the most quality-sensitive stage) may extend them —
acceleration changes planning granularity, it does not lower the bar a
stage has to clear before merge (see "Engineering quality preserved"
above).

---

## Issue #1–#10 reconciliation

Full rationale (summary table lives in `14_...md` §26). Stage references
below use the new four-stage numbering; the old sub-stage number is given
in parentheses for traceability into the appendix.

### #1 — Assessment
**Decision: V1, scope updated.** State machine, resume, minimum-data rule:
unchanged. Added: the 4-mode architecture requirement (`14_...md` §7,
corrected release-requirement table above), Hybrid as the required default
paid flow, CV as a required capability inside Hybrid (not a separate
mode), Structured deferred to Stage 4 (appendix Stage 12), Conversation not
a release blocker. All built in **Stage 1**.

### #2 — Evidence/Profile
**Decision: V1 critical, unchanged in substance.** Scoped to exactly what
a V1 report needs, not a generalized research platform. Built in
**Stage 2** (appendix Stage 4).

### #3 — Scenario Engine: Safe / Growth / Bold
**Decision: REDEFINED.** Superseded by Direction Intelligence's TOP 3 +
Alternative 3 (`14_...md` §11) — no ERD change implied. Built in
**Stage 3** (appendix Stage 5).

### #4 — Career Knowledge Graph + matching v1
**Decision: V1-critical intelligence foundation, rescoped** to a curated,
versioned Knowledge Base seed, not a full world career graph, not
automated ingestion. Built in **Stage 3** (appendix Stage 6).

### #5 — Direction decision + 90-day Roadmap Engine
**Decision: PARTIAL V1.** Direction decision stays in scope; the full
Roadmap Engine is deferred, V1 ships only the Route Builder. Built in
**Stage 3** (appendix Stage 8).

### #6 — Guide OS: Client 360 + session workspace
**Decision: PARTIAL V1.** Only the Consultant Review Workspace needed for
the mandatory Human Review gate ships now. Built in **Stage 3** (appendix
Stage 10).

### #7 — AI Gateway, prompt registry and evaluation suite
**Decision: V1 critical, unchanged.** Already ahead of schedule (Sprint 0
Part 4). No new provider integration in V1, only new tasks routed through
the existing gateway, across **Stages 1–3**.

### #8 — Product analytics + traceable event model
**Decision: V1 minimal.** Funnel events, AI quality/cost visibility, and
review-queue metrics. Built in **Stage 4** (appendix Stage 13), fed by
events emitted throughout Stages 1–3.

### #9 — Admin QA console + audit trail
**Decision: V1 critical, extended.** The engineering home for the
mandatory human review gate. Built in **Stage 3** (appendix Stage 10).

### #10 — Canonical identity, consent and tenant permissions
**Decision: V1 critical, unchanged.** The explicit prerequisite for
everything else. Built in **Stage 1** (appendix Stage 1), alongside the
new Product Access/Entitlement skeleton (a genuinely new, adjacent concern
— `14_...md` §27.2).

### #12 — Sprint 0
**Decision: history/foundation.** Not rewritten, not reopened.

### #11 (not an epic — the original architecture PR)
No reconciliation needed — this document narrows implementation scope,
not the architecture itself.

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

---

## Appendix: detailed sub-stage reference (historical planning detail)

**Not the primary execution model** (see the top of this document) — kept
because the level of detail here is useful for tracking dependencies
*inside* one of the four authorized stages. Sub-stage numbers below map
into the four stages as: Stage 1 ⊇ sub-stages 0–3; Stage 2 ⊇ sub-stage 4;
Stage 3 ⊇ sub-stages 5–10; Stage 4 ⊇ sub-stages 11–15.

### Sub-stage 0 — Foundation & Governance

**Goal:** the engineering ground V1 is built on is trustworthy before real
schema work starts.
**Backend:** PostgreSQL CI verification (Sprint 1 Part 0 — **done**,
merged via PR #15).
**Deliverable:** a CI pipeline that cannot silently accept a broken
migration.

### Sub-stage 1 — Canonical Identity, Consent, Product Access foundation

**Backend:** `identity_users`/`auth_identities` (`02_ERD.md`'s `USER`/
`AUTH_IDENTITY`); hardened `Consent`; a new, not-yet-specified minimal
Product Access/Entitlement schema (`14_...md` §27.2 — needs its own short
architecture note before backend work starts).
**Tests:** identity resolution, consent versioning/withdrawal, entitlement
redemption idempotency.
**What NOT to build yet:** a real payment provider (that's Stage 4);
self-serve org purchasing UI.

### Sub-stage 2 — Assessment Engine core (state machine)

**Backend:** `InterviewSession`/`Answer`/`InterviewMessage`, the full
`draft → active → paused → complete → processing → ready → failed` state
machine.
**Tests:** full state-transition table, idempotent answer submission,
resume-after-restart.

### Sub-stage 3 — Hybrid mode + CV-assisted evidence

**Backend:** the adaptive next-question service; CV upload wired into the
evidence pipeline as a source.
**AI:** existing legacy-screening-v1-shaped extraction through
`AIGateway`, evolved to flag confidence/contradiction into structured
fields.
**Tests:** already-resolved facts never re-asked; contradiction detection;
low-confidence re-ask; 20–30 minute duration band under realistic
question-bank sizing.

### Sub-stage 4 — Evidence / Human Potential Profile

**Backend:** `POTENTIAL_PROFILE`/`PROFILE_CLAIM` population; regeneration
creates a new version, never overwrites.
**Tests:** every high-impact claim has evidence or explicit
low-confidence/hypothesis status; regeneration preserves history.

### Sub-stage 5 — Direction Intelligence foundation

**Backend:** a dedicated Direction Intelligence service producing
`SCENARIO`/`SCENARIO_SCORE`/`DIRECTION_DECISION`-shaped output;
`scenario_type` free-text, no ERD change needed.
**Tests:** hard constraints never violated; 6 directions returned;
confidence/fit distinct; no unsupported market facts.

### Sub-stage 6 — Knowledge Base (seed + architecture)

**Data:** a small, manually curated, versioned seed with provenance.
**Tests:** every knowledge item used carries source/date.

### Sub-stage 7 — Direction evals

**Data:** extend `evals/golden/` with `target=scenario_generation` cases.
**Tests:** golden-dataset schema validation; reviewed cases before real
users see output.

### Sub-stage 8 — Route Builder

**Backend:** depends on the open founder decision in `14_...md` §27.1
(thin reuse of `ROADMAP`/`MILESTONE`/`ROADMAP_TASK` vs. a separate simpler
structure).
**Tests:** every route has the four required stages; no vacancy/university
content leaks in.

### Sub-stage 9 — Report generation

**Backend:** report assembly service; PDF/web rendering (format only,
publishing gated by review).
**Tests:** report renders all 13 required sections; no raw JSON reaches
output.

### Sub-stage 10 — Human Review Console

**Backend:** the report review state machine (`14_...md` §14/§27.3 —
states/transitions specified in its own short design note); server-side
RBAC for `SUPER_ADMIN`/`ADMIN`/`MANAGER`/`CONSULTANT`/`REVIEWER`.
**Tests:** a report cannot reach the user without `approved` state,
enforced by the state machine itself; every privileged action produces an
`AUDIT_LOG` row.

### Sub-stage 11 — Payment / Promo Code

**Backend:** real payment provider behind the entitlement abstraction;
promo code generation/redemption (admin-issued for V1).
**Tests:** payment success/failure/webhook idempotency; promo code
single-use enforcement; attribution query end-to-end.

### Sub-stage 12 — Free Structured Test funnel

**Frontend:** landing page, plan descriptions, FAQ, CTA, free test entry,
hand-off into Telegram.
**Tests:** free-test evidence actually carries into the paid flow.

### Sub-stage 13 — Analytics / QA minimal

**Backend:** structured event logging in the canonical envelope shape;
review-queue metrics.
**Tests:** events fire at every named milestone; no PII in event
properties.

### Sub-stage 14 — Closed Pilot

**Process:** a small cohort runs the full paid flow; consultants review
every report manually; founders read every report alongside review.
**Acceptance criteria:** the V1 Definition of Done (`14_...md` §22) holds
under real usage; no report reached a user without approval; no
data-safety incident.

### Sub-stage 15 — Commercial V1 launch

**Process:** public website live, payment live, promo-code distribution
live, on-call/monitoring per `docs/engineering/08_DELIVERY_PROCESS.md`.
