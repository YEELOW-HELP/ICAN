# Sprint 0 Exit Report

Sprint 0, Part 6 (final) — Issue #12. Written against Issue #12's own stated
exit criteria (quoted below) and the actual state of PR #13
(`sprint-0-migration-baseline` → `product-system-v3.1`) and PR #11
(`product-system-v3.1` → `master`) as of this commit. Nothing in this report
is invented — every claim below was checked directly (tests run, CI status
read from GitHub, issue/PR state read from GitHub) rather than assumed.

## What was completed

| Part | Deliverable | Commit(s) |
|---|---|---|
| 1 | Regression baseline: coverage audit, gap analysis, new tests (bot e2e harness, AI-provider-failure handling, CRM write-endpoint RBAC negatives + delete CRUD, Alembic revision-chain integrity, frozen API route snapshot); `--disable-socket` so no test can ever call a real provider | `0bfac28` |
| 2 | `docs/engineering/10_CURRENT_TO_TARGET_MIGRATION_MAP.md` — all 15 current tables mapped to target ERD entities (REUSE/ADAPT/DEPRECATE/REPLACE), 7 documented contradictions between the target docs and the actual code | `3fc6d8b` |
| 3 | `docs/engineering/11_TECHNICAL_DEBT_REGISTER.md` — 15 tracked items (severity/probability/blast radius/mitigation/owner), Decisions 1 and 2 recorded | `1117a1c`, `60344be` (correction) |
| 4 | `app/ai_gateway.py` — single seam for all LLM calls; `ScreeningAgent` (the only direct provider call site in the app) now goes through it, tagged `legacy-screening-v1`; trace/latency/token/cost logging on success **and** on provider failure | `dd863ac`, `bdbc845` (failure-observability follow-up) |
| 5 | `evals/golden/` — versioned golden-dataset structure, JSON Schema, 10 synthetic example cases for screening, no eval runner | `501b293` |
| 6 | This report + documentation reconciliation (`00_MASTER_INDEX.md`, `09_MIGRATION_AND_TEAM_OWNERSHIP.md`, `05_RELEASE_PLAN.md`, `06_R0_R1_BACKLOG.md`) | this commit |

Every part was reviewed and approved by Mykola individually before the next
started, per the process he set at Sprint 0's start (Issue → branch →
implementation → tests → commit → PR → review → next task).

## What was intentionally not completed

Explicitly out of scope by instruction, not oversights:

- No database schema changes, no Alembic migrations.
- No implementation of: canonical User/AuthIdentity, Consent,
  InterviewSession/Answer, the versioned taxonomy (Decision 2), Evidence/
  ProfileClaim, `CLIENT_ASSIGNMENT` (Decision 1), TENANT/MEMBERSHIP.
- No retries or fallback providers in the AI Gateway.
- No eval runner — `evals/golden/` is structure only.
- No frontend work.
- The unresolved production button-cascade bug was not investigated or
  fixed (correctly — it needs live reproduction, which requires resuming
  Telegram traffic, which is out of scope until the product is ready per
  Mykola's own earlier instruction).

## Test count and CI status

- Local: **117 tests passing** (up from 61 at Sprint 0 start: +16 Part 1,
  +5 Part 4 (gateway), +1 Part 4 follow-up, +34 Part 5 (golden dataset
  schema validation)).
- CI (`.github/workflows/ci.yml`, runs `pytest -q` on every push/PR):
  **all 8 recorded runs on `sprint-0-migration-baseline` have completed
  successfully**, including the Part 6 commit `a42667e`
  (full SHA `a42667ec8ec32874bb395066c931bd3a69046c2d`, run completed
  2026-08-25T18:03:22Z, conclusion `success`) — confirmed via the GitHub
  Actions API, not just local runs. This final documentation-cleanup
  commit (the one containing this sentence) is pushed after this check was
  made, so its own CI result is not yet known at time of writing; what is
  confirmed for it is the local `pytest -q` run below.
- No test anywhere in the suite makes a real network call to Anthropic or
  Telegram (`pytest-socket`, loopback-only, enforced since Part 1).

## Production behavior changes

**None.** `ScreeningAgent`'s behavior is unchanged — same model, same
system prompt, same tool schema, same fact-merging logic; it now calls
through `AIGateway` instead of `AsyncAnthropic` directly, but the request
and response shape at that boundary is identical. This is verified by the
full `tests/test_bot_e2e.py` suite passing unchanged and by
`tests/test_screening.py`'s behavioral assertions passing unchanged (only
their fake-client injection point moved from `ScreeningAgent` to
`AIGateway`). The only new user-visible-adjacent change is structured log
lines — nothing a candidate or CRM user would see.

## Database/schema changes

**None.** No Alembic migration was created in Sprint 0. No table, column,
or index was added, renamed, or dropped.

## Unresolved high-risk items

Pulled from `11_TECHNICAL_DEBT_REGISTER.md` — full detail there, high/medium
severity items repeated here for visibility:

- **No consent/privacy tracking exists** (Item 13, severity High) — real
  compliance exposure today, independent of any migration timeline.
- **Versioned taxonomy architecture undesigned** (Item 11, severity High) —
  Decision 2 confirms the direction, but no schema exists yet for how a
  taxonomy version attaches to future claims/evidence.
- **`AuthIdentity` has no field-level specification** (Item 5, severity
  Medium, but blocks the highest-blast-radius migration in the whole
  Migration Map).
- **Unresolved production button-cascade bug** (Item 4, severity High) —
  root cause still unknown; must not be assumed fixed by any future
  architecture change until reproduced and verified.
- **PostgreSQL Alembic execution has no CI coverage** (Item 1, severity
  High) — every future migration for canonical User/Consent/InterviewSession
  is currently untested against the real database dialect.
- **`GOAL`/`CONSTRAINT`/`EXPERIENCE` have no field-level ERD** (Item 9,
  severity Medium) — blocks migrating the CRM's richest, most
  human-verified data.
- **`CLIENT_ASSIGNMENT` undesigned** (Item 12, severity Medium) — Decision 1
  confirms the direction; current `manager_id`/`consultant_id` semantics are
  preserved unchanged until it lands.

## R0/R1 blockers

- **Issue #1** ("EPIC R0 — Assessment state machine + adaptive interview")
  requires "API and DB are channel-agnostic; Telegram is only a client" as
  an explicit acceptance criterion. That is exactly the canonical
  User/AuthIdentity migration this sprint identified as the **highest-risk,
  highest-blast-radius item in the whole Migration Map** — and its target
  shape (`AuthIdentity`) is still unspecified in the ERD (debt item 5).
  Whoever starts Issue #1 will hit this as the very first real design
  decision, not partway through. Recommend resolving debt item 5 before or
  as the explicit first step of Issue #1, not mid-implementation.
- **R1's "Evidence Graph" deliverable** (per `docs/product/00_MASTER_INDEX.md`)
  depends on the versioned taxonomy (debt item 11), which is confirmed in
  direction (Decision 2) but not designed. This does not block Issue #1
  itself (which is state-machine mechanics, not evidence-linked claims) but
  will block R1 if not scheduled.
- **J1/J2 (AI Gateway & Evals, Issue #7, R1-scoped)** are partially
  satisfied ahead of schedule (see `06_R0_R1_BACKLOG.md` — gateway wrapper
  and trace logging done; schema validation, retry/fallback, the remaining
  10 golden cases, and the eval runner are still open).
- **Wider R0 rollout beyond already-consented test users** should be gated
  on a Product/Legal decision about consent capture (debt item 13) — this
  is a compliance question, not an engineering one, and this report is not
  the place to decide it.

## Accepted Founder/Product decisions

Recorded in `11_TECHNICAL_DEBT_REGISTER.md`, not implemented:

- **Decision 1** — Manager and Guide are separate concepts.
  `CLIENT_RELATIONSHIP` is client↔guide only; operational
  ownership/coordination (manager, coordinator, ...) will be a future
  `CLIENT_ASSIGNMENT`-type model. Current `manager_id` semantics preserved
  until that lands.
- **Decision 2** — Taxonomies are versioned, starting at Taxonomy v1, with
  historical traceability to the version that produced any given result.
  Full taxonomy design is separate future work.

## Sprint 0 exit criteria — checked against Issue #12's actual text

Issue #12 states five exit criteria. Checked directly against current
GitHub state, not assumed:

| Criterion | Status |
|---|---|
| PR #11 architecture reviewed | **Not yet.** PR #11 (`product-system-v3.1` → `master`) is still open/draft with no review recorded. This is explicitly Mykola's own action (he clarified earlier in Sprint 0 that self-review by this work would not be appropriate) — not something Parts 1–6 could complete on his behalf. |
| Current behavior protected by tests | **Satisfied.** 61 → 117 tests, CI green on every commit, no production behavior change. |
| Migration map documented | **Satisfied.** `10_CURRENT_TO_TARGET_MIGRATION_MAP.md`. |
| Owners identified for issues #1–#10 | **Not satisfied.** Checked directly via the GitHub API: issues #1–#10 currently have zero assignees. This is a staffing/org decision for Mykola/Founder, not an engineering deliverable. |
| Sprint 1 can start without ambiguity | **Partially.** The regression baseline, migration map, and debt register remove most technical ambiguity. One concrete ambiguity remains for Issue #1 specifically: `AuthIdentity`'s shape (debt item 5) — see "R0/R1 blockers" above. |

**2 of 5 criteria fully satisfied, 1 partially, 2 pending actions that are
explicitly outside engineering scope** (PR review and issue ownership are
Mykola's calls to make, not mine to complete).

## Recommendation: CONDITIONAL GO

The engineering deliverables Sprint 0 was actually asked to produce — a
verified regression baseline, an honest migration map, a tracked debt
register, an AI Gateway wrapping legacy behavior with zero production
change, and a golden-dataset structure — are complete, tested, and green in
CI. Nothing here blocks Issue #1 from being *scoped and planned*.

It is a **conditional**, not unconditional, GO because three things outside
this sprint's engineering scope are still open and materially relevant to
starting Issue #1 cleanly:

1. PR #11's architecture review (Mykola's action).
2. Assigning an owner to Issue #1 (and ideally #2–#10) (Mykola/Founder's
   action).
3. Resolving `AuthIdentity`'s field-level shape (debt item 5) before, not
   during, Issue #1's implementation — otherwise the first real technical
   decision of Sprint 1 gets made informally mid-PR instead of deliberately
   up front.

No unresolved risk was omitted from this report to make the recommendation
look better than it is — see "Unresolved high-risk items" above, all of
which remain genuinely open regardless of this GO/NO-GO call.
