# CURRENT SOURCE OF TRUTH

Short operational answer to: **what is canonical TODAY?**

This document does **not** duplicate the MNP development package. Where an
older document conflicts with a current Founder decision, **this document
wins** (see §9).

Last updated: Repository Cleanup V1.

---

## 1. Product

**МОЖУ / Мій Напрям (MNP)** — career navigation for the Ukrainian market.

Goal: answer a person *"which career fits me and what do I need to work in
it?"* with a clear, deterministic, explainable result — no fabricated
numbers, no black-box AI scoring in the core.

---

## 2. Canonical Git branches

| branch | role |
|---|---|
| `master` | stable legacy / release baseline (ICAN 1.1 era) |
| `product-system-v3.1` | **single canonical development / integration branch** for MNP |
| feature branches | short-lived, branched from `product-system-v3.1`, merged back via PR |
| research / archive | `matching-v1-deterministic-core`, `data-foundation-v1`, `stage-3b-direction-intelligence-v1` — retained for history/research, **never merged to production** |
| temporary / superseded | `stage-1-hotfix-anthropic-key-validation` — its useful behaviour is already ported into `repo-cleanup-v1`. **Safe to delete after PR #24 merges.** Not a permanent research/archive branch. |

Consolidated and deleted: `mnp-v1-implementation`, `career-kb-v1-final`,
`mnp-career-kb-v1`, `mnp-data-explorer-v1`, `founder-architecture-review-v3.1`,
`methodology-lab-v0.1`, `docs/mnp-development-package-v1`.

Do **not** create another permanent integration branch.

---

## 3. Current production architecture

### FOUNDATION / REUSE
- Identity / Consent
- Assessment (Stage 1 hybrid)
- Evidence / Human Potential Profile (Stage 2)
- Knowledge (Stage 3A Career Knowledge Base — legacy taxonomy)
- CRM 1.0 (`/dashboard`, `/crm/*`)

### MNP V1 CURRENT
- Career Card (public profession card)
- **Career KB** — canonical profession DB (`mnp_*` tables)
- Career KB Admin / Editor (`/v1/mnp/admin/*`, `#/admin/*`) — manage without code
- Career Explorer (public catalog + card, `/mnp/#/catalog`)
- Minimal Questionnaire
- Resume parser (resume → CareerCard)
- Deterministic Matching / Transition engine (`app/services/matching/`) — no AI
- MNP frontend (`mnp_frontend/`, plain JS, no build step)

### RESEARCH / TOOLING
- `data_explorer/` — ESCO, O*NET, Work.ua inventory, crosswalk, human lab, Excel export
- `evals/` — golden datasets and tooling

### LEGACY / DEPRECATED CANDIDATES
- ICAN 1.1 Telegram screening flow (`app/bot/`, `bot_flow="legacy"`) — still runnable, foundation only
- Stage 3A `models_knowledge.py` whole-catalog snapshot taxonomy — superseded for MNP by the `mnp_*` Career KB; kept for whatever still depends on it

---

## 4. Career KB status

- **150 careers · 5 ACTIVE · 145 DRAFT**
- DRAFT: hidden from the public site, excluded from production matching.
- The canonical `mnp_*` DB (+ Career KB Editor) is the **production source
  of truth**.
- `MNP_CAREER_KB_V1.xlsx` is a **review / export artifact, NOT a source of
  truth** — DB → Excel only, there is no Excel → DB path.
- **Career Data Audit / ESCO-O*NET mapping V1** is research / postponed and
  **NOT part of the current V1 runtime**. Its implementation lives only in
  the unmerged `career-kb-data-audit-v1` branch and is not carried into
  `product-system-v3.1`.
- No fabricated market data anywhere: every career is `MARKET_DATA_LIMITED`.

Acceptance record: `docs/mnp_v1/04_KNOWLEDGE_BASE/CAREER_KB_V1_FOUNDER_ACCEPTANCE.md`.

---

## 5. Person domain

**PERSON KB BASE V1 is the canonical Person KB** (`MnpPerson` /
`mnp_persons` + fact tables; branch `person-kb-base-v1`). Fact-first
career profile — education / credentials / experience / activities /
skills / languages / mobility / documents, with an evidence state on
every fact. Fed by three flows into ONE root: user manual profile, user
CV upload + review, admin manual. Docs:
`docs/person_kb/PERSON_KB_BASE_V1.md`.

Explicitly **not** in Base V1: psychological portrait / RIASEC / Big Five
/ Work Values / Work Styles / aptitude / AI personality inference /
universal career-fit score.

Reuse decisions (see `PERSON_KB_BASE_V1.md` §14):

- **Identity** — reused as-is (`IdentityUser`). Private user routes
  authenticate with a **bearer session token** (`POST /v1/mnp/session` →
  `session_token`; hash-only in `mnp_web_sessions`) — a client-supplied
  `X-Mnp-User-Id` is never trusted on Person KB routes.
- **Skill taxonomy** — reused: `mnp_person_skills_v1 → mnp_skills` (the
  same rows the Career KB uses). No parallel Person skill dictionary.
- **Resume parser** — reused (`app/services/resume_parser_mnp` pure
  functions).
- **Evidence** — the canonical Person KB evidence model is
  `PersonEvidenceState` on `MnpPerson` fact rows. `MnpEvidence` /
  `MnpCareerCard` evidence is retained for Matching compatibility only;
  new Person code must not write to it.
- The old `MnpCareerCard` person stack + `MnpEvidence` + Stage 3A
  `Assessment` / `Profile` / `Knowledge` — **retained** for Matching /
  questionnaire compatibility; superseded for new development. Person KB
  is **not** wired into Matching in Base V1 (a `MnpPerson → matching
  input` adapter is the next step).

Do **not** create a further parallel Person model stack. New Person-side
development targets `MnpPerson`.

---

## 6. Market KB

Not yet implemented / not canonical.

No fabricated market metrics (vacancy counts, salary, demand, city-level
data). Placeholders must show an honest empty / "coming later" state.

---

## 7. Data Explorer

Research / QA / dataset-exploration layer (`data_explorer/`).

- **May READ** production / canonical data (e.g. `MNP_DATABASE_URL` pointed
  at a real DB, read-only).
- Production runtime **must NOT depend on** `data_explorer/`.

---

## 8. Migrations

Existing Alembic migration history is canonical. Do **not** squash or
rebuild migrations during normal feature development. New schema changes
are additive migrations only.

Local dev builds the schema from models (`scripts/dev_seed.py`) because two
old `ALTER COLUMN` migrations are Postgres-only; the full chain is validated
in CI (`postgres-migrations`).

---

## 9. Documentation precedence

1. **`CURRENT_SOURCE_OF_TRUTH.md`** (this file)
2. latest Founder-approved acceptance / decision documents
3. current implementation + tests
4. `MNP_DEVELOPMENT_PACKAGE_V1` / `docs/mnp_v1/`
5. historical / research documents

Where old docs contradict a current Founder decision, this file wins.
Historical documents are **not** deleted — they remain as history, clearly
superseded.

---

## 10. Next workstream

```
Repository cleanup        (done)
Person KB BASE V1          (done -- branch person-kb-base-v1)
   → Person KB → Matching adapter
   → Resume Builder on Person KB
   → later: preference / values layer, Market KB Ukraine
```
