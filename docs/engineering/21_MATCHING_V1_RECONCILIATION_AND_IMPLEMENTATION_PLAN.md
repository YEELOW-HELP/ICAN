# 21. Matching V1 — Reconciliation & Implementation Plan

**Status:** ENGINEERING PLAN — documentation/specification only, no code changed by this document.

> **HARDENED (2026-08-28) per Founder Review "Matching V1 M0":** M0 is approved in direction but **M1 production implementation has NOT started** — a methodology hardening pass was required first and is now complete. Three new companion documents resolve the previously-unresolved Open Math Questions A/B with actual research and computation: `methodology_lab/05_GOLDEN_TEST/MNP_SCALE_TO_ONET_MAPPING_V0.1.md` (verified against the current, 2024-redesigned O*NET Work Styles taxonomy), `MNP_MATCHING_METRIC_BENCHMARK_V0.1.md` (11 computed cosine-vs-Euclidean cases; guarded cosine adopted), `MNP_BASIC_SHORT_FORM_STRATEGY_V0.1.md` (94-item bank reclassified as research estimate; ~75-item BASIC short form proposed). See the Founder Report for the full GO/CONDITIONAL-GO decision on M1.
**Base:** built on top of `docs/product/20_MATCHING_V1_FOUNDER_DEFINITION.md` (binding Founder product contract, 2026-08-28).
**Scope of this document:** reconcile everything already built (Stage 1–4A.5) against the new Matching V1 product model, define what is kept / superseded / deferred, and lay out the M1–M6 implementation slices. This document does not implement anything; M1 begins after Founder review of this plan.

---

## 1. Why this document exists

Doc 20 introduces a new BASIC V1 deterministic core (Structured Test → Deterministic Profile → Deterministic Career Matching → self-serve Career Dashboard) that sits *underneath* everything built so far in Stage 1–4A.5, and narrows the old four-output Direction model (Potential Fit / Goal Alignment / Transition Feasibility / Evidence Confidence) to a historical, PRO-track artifact rather than the BASIC default. This plan exists to make that transition explicit, auditable, and non-destructive: nothing already shipped is deleted or rewritten; a new, parallel, versioned methodology is added beside it.

---

## 2. Reconciliation map — existing system vs Matching V1

### 2.1 KEEP (used as-is, no rework required)

| Area | Component | Why it survives unchanged |
|---|---|---|
| Identity/consent/access | `IdentityUser`, consent flow, RBAC roles (`SUPER_ADMIN`/`ADMIN`/`CAREER_CONSULTANT`) | Product-agnostic infrastructure; Matching V1 reuses it as-is. |
| Career base entities | `app/db/models_knowledge.py` (`Career`, `CareerRequirement`, `CareerWorkContext`, `CareerSkill`, `CareerFact`, etc.), `Career.code` identity | Doc 20 explicitly keeps `Career.code` as the sole internal identity; Matching V1 is an *additive* layer on top (`CareerMatchingProfile`), never a replacement of these tables. |
| Consultant review state machine | `app/services/direction/review.py` (PENDING_REVIEW → APPROVED/CHANGES_REQUESTED/REJECTED), `ConsultantCorrection` (13 reason codes) | Doc 20 §Curated Directions Layer explicitly says this infrastructure is reused for the new 3 MAIN + 3 ALTERNATIVE curated layer. No new review state machine needed. |
| Corrections / append-only overlay pattern | `build_reviewed_direction_view()` (`app/services/direction/readmodel.py`) | The EFFECTIVE-vs-SYSTEM projection pattern (correction overlays applied in-memory, source rows never mutated) is reused for the new curated-directions read model. |
| Dashboard infrastructure | Consultant Dashboard + Client Card (Stage 4A), `admin_frontend/` shell, auth/session (`api.js`) | The frontend shell, routing, and auth pattern are reused; new views are added inside it, not replaced. |
| Versioning discipline | `app/services/direction/versions.py` (pinned `methodology_version`, `direction_engine_version`, etc.) | Matching V1 extends this pattern with its own new version fields (§5 below); the mechanism itself (pin-at-creation-time, never silently upgrade historical rows) is unchanged. |
| Audit/privacy invariants | Readmodel never imports raw source models (`Answer`/`CVUpload`/`InterviewMessage`); AI_TRACE not persisted | Both invariants apply equally to the new deterministic engine, which reads even less raw data (structured test responses only, no LLM in the BASIC path at all). |
| Optional narrative generation | `AIGateway.call_tool`, grounded-narrative-from-explanation-bundle pattern | Retained for the curated-directions layer's consultant narrative and for the PRO enrichment layer; the "LLM reads only deterministic bundles, never raw text" invariant carries over unchanged. |

### 2.2 PRO-ONLY (retained, but explicitly moved out of the BASIC default path)

| Component | Status |
|---|---|
| Stage 1 Hybrid Assessment (`handlers_v1.py`, free-text answers) | PRO track only. BASIC V1 uses the new Structured Golden Test instead. |
| CV AI extraction (`evidence_extractor`) | PRO enrichment only. |
| Adaptive/LLM-driven follow-up questions | PRO enrichment only. |
| AI claim synthesis (`claim_synthesizer`) | PRO enrichment only. |
| AI narrative enrichment beyond the grounded Direction narrative | PRO enrichment only. |

None of this code is deleted or disabled — `BOT_FLOW=v1` continues to register the Hybrid flow for PRO users. Matching V1's BASIC flow is a **new, separate bot flow** (see §4, M5) that does not require any Hybrid-flow code to run.

### 2.3 SUPERSEDE FOR BASIC (old model retained for history, not used as the new BASIC default)

| Old (Stage 3B) | New (Matching V1 BASIC) | Compatibility rule |
|---|---|---|
| Potential Fit | *(removed as a BASIC output)* | Historical `DirectionRun` rows keep this field; never rewritten. |
| Goal Alignment | *(removed as a BASIC output; Goals become a contextual tie-break only — §6 of Golden Test)* | Same. |
| Evidence Confidence | *(removed as a BASIC output; replaced conceptually by Coverage, which measures test completeness, not confidence)* | Same. |
| Transition Feasibility (claims-based) | Transition Feasibility (deterministic, structured-constraints-based) — **name kept, computation replaced** | New computation only applies to Matching-V1-tagged runs; old Feasibility computation on historical rows is untouched. |
| Default flow = Hybrid Assessment | Default flow = Structured Golden Test (BASIC) | `BOT_FLOW` gains a third value, `matching_v1_basic` (design only in this doc; wiring happens in M5). |

Both methodologies coexist permanently. A `DirectionRun`/new equivalent record is tagged with which methodology produced it (§5); nothing is "migrated" from old to new.

### 2.4 NEW (built from scratch, no existing equivalent)

- Structured Golden Test (item bank, scales, scoring) — spec: `methodology_lab/05_GOLDEN_TEST/MNP_GOLDEN_TEST_V0.1.md`.
- Deterministic Profile Engine (turns test responses into RIASEC / Work Style / Work Values / Work Environment / Goals / Constraints vectors + Coverage).
- Career Matching Vectors / Career KB V1 (`CareerMatchingProfile`, `CareerExternalMapping`) — spec: `methodology_lab/06_CAREER_KB/MNP_CAREER_KB_V1.md`.
- Deterministic Matching Engine (Interest Fit / Work Style Fit / Values Fit / Transition Feasibility / Coverage) — formulas: Golden Test doc §17–24.
- Self-serve Career Dashboard (permanent "Кар'єра" section) — contract: §7 below and doc 20 §5A.
- Compatibility Report (per user×career, deterministic, no consultant approval).

### 2.5 DEFER (explicitly out of scope for M0–M6)

Opportunity matching (jobs/vacancies), Career Route automation, adaptive psychometrics, population percentiles, archetypes, ML-based calibration of fit weights, any custom/fine-tuned LLM. These remain named placeholders in the Career KB schema (§N/§O of the Career KB doc) but are not designed or built here.

---

## 3. Product/flow reconciliation

**Old default flow (Stage 1–4A.5):** Telegram → Hybrid Assessment (free text + optional CV) → AI claim synthesis → `PotentialProfile` → `generate_directions()` → 4-output DirectionRun → consultant review → narrative.

**New BASIC V1 flow (doc 20 §5):**
Structured Golden Test → Deterministic Profile → Deterministic Career Matching → **Profile shown immediately** → **Ranked Career Catalog shown immediately** → **Compatibility Report available immediately, self-serve, no consultant gate** → optional consultant curation → Approved 3 MAIN + 3 ALTERNATIVE Directions → Career Route (future).

The key product change is the **review boundary**: everything up to and including the Compatibility Report is self-serve and immediate; only the *curated* 3+3 layer requires consultant approval. This is a narrower consultant gate than Stage 3B's (which required review before showing any Direction at all).

PRO remains an optional enrichment layer available at any point after BASIC, never a precondition for it.

---

## 4. Versioning-stamp requirement

Every result produced by the new methodology stamps all five of:

- `assessment_version` — Golden Test item bank/scale version (e.g. `golden_test_v0.1`)
- `profile_engine_version` — deterministic scoring/normalization version
- `matching_methodology_version` — Fit-metric/feasibility-formula version (Golden Test doc)
- `career_vector_version` — version of the `CareerMatchingProfile` data feeding the match (source snapshot + mapping version)
- `matching_engine_version` — code version of the deterministic matching engine itself

This mirrors, and sits beside, Stage 3B's existing pinned fields (`methodology_version`, `direction_engine_version`, `dimension_taxonomy_version`, `subdimension_taxonomy_version`, `constraint_taxonomy_version`). A record is either an "old-methodology" record (Stage 3B fields populated, new fields null) or a "Matching V1" record (new fields populated); the two families are never mixed within one record, and neither ever overwrites the other's history.

---

## 5. Implementation slices (design only — not built in M0)

- **M1 — Structured assessment data model.** New tables for the Golden Test item bank, item responses, scale definitions, and BASIC/PRO mode flag on the assessment session. No scoring yet.
- **M2 — Deterministic profile engine.** Scoring functions (per-scale mean, reverse-scoring, missing-answer handling per Golden Test doc §6–8), Coverage computation, produces a versioned `DeterministicProfile` record.
- **M3 — Career Vector KB schema + O*NET import.** `CareerMatchingProfile`, `CareerMatchingProfileComponents`, `CareerExternalMapping` tables; O*NET importer respecting source provenance (Career KB doc §C, §G); crosswalk review workflow (Career KB doc §J).
- **M4 — Deterministic matching engine + Career Catalog API.** Interest/Work-Style/Values Fit, Feasibility, Coverage computation (Golden Test doc §17–24); ranked catalog endpoint; Compatibility Report endpoint.
- **M5 — Telegram BASIC flow.** New `BOT_FLOW=matching_v1_basic` handler set; delivers the Structured Golden Test, shows Profile + Career Catalog + Compatibility Report immediately (no consultant gate) inside the bot/mini-app.
- **M6 — Consultant curated 3+3 + Compatibility/Route integration.** Reuses Stage 3B review infrastructure (§2.1) against the new deterministic outputs; produces the approved 3 MAIN + up to 3 ALTERNATIVE curated layer and narrative.

Each slice ships independently, tested, with a Founder GO before starting and a Founder report before proceeding to the next — matching the cadence used for Stage 3B/4A/4A.5.

---

## 6. Compatibility guarantees (carried forward from Stage 3B discipline)

- No historical `DirectionRun` is ever rewritten, re-scored, or re-labeled under the new methodology.
- Old and new methodologies are permanently coexisting, distinguished by the version-stamp fields (§4), never by inference.
- The consultant review/correction/audit infrastructure is shared, not forked — one state machine, two families of underlying scored content.
- All BASIC V1 privacy/provenance invariants already established (readmodel never touches raw source text; AI never re-derives or overrides a deterministic score) apply to the new engine identically, and more strictly, since the BASIC path involves no LLM call at all.

---

## 7. Career Dashboard contract (doc 20 §5A, engineering-level summary)

Full UX detail is deferred to a future revision of `docs/product/18_DIRECTION_REPORT_PRESENTATION_TZ.md` (not modified in M0 — flagged here as required future work). This document fixes the *screen contract* only, so M4/M5 have a stable target:

1. **Career Catalog** — global, flat, ranked list (see Open Question H below); one row per `Career`, shows Interest/Work Style/Values Fit bands + Feasibility band; no combined score.
2. **Career Filters** — domain, feasibility band, fit band thresholds; filters narrow the global list, they do not regroup it by default.
3. **Career Card** — summary view of one career: description, bands, entry requirements, related careers.
4. **Compatibility Report** — full per-user×career deterministic report, sections A–G (doc 20).
5. **Market Data section** — sourced, dated, clearly separated from fit data; never blended into a score (Career KB doc §F/§H).
6. **Consultant Curated Directions section** — the 3 MAIN + 3 ALTERNATIVE layer, visually and structurally distinct from the self-serve catalog above it.
7. **Saved Careers** (future) — placeholder only.
8. **Opportunity links** (future) — placeholder only.

**Separation invariant:** FIT DATA (deterministic, from the matching engine) / MARKET DATA (sourced, dated, from Career KB facts) / CONSULTANT RECOMMENDATION (curated, reviewed) are three distinct visual and data-model tracks on every screen that shows more than one of them. No UI element may combine values from more than one track into a single number.

---

## 8. Open Founder decisions carried into the Golden Test / Career KB documents

Per Founder instruction, none of the following are silently resolved by engineering; each is written up with OPTIONS/PROS/CONS/V0.1 RECOMMENDATION/WHY/PROVISIONAL STATUS in the referenced document, awaiting Founder sign-off before M1:

- A. Work Preferences / Work Values exact scales — Golden Test doc §A.
- B. Vector-distance metric — Golden Test doc §B.
- C. Goals' role in ranking — Golden Test doc §C.
- D. Coverage threshold — Golden Test doc §D.
- E. Career catalog granularity — Career KB doc §E.
- F. Work.ua↔O*NET crosswalk cardinality — Career KB doc §F.
- G. Market data freshness windows — `MNP_WORKUA_DATA_USE_DECISION_V0.1.md` §G.
- H. Compatibility Report / Catalog ordering — §7 above and Golden Test doc §24.

Every recommendation below is marked **PROVISIONAL — V0.1, pending Founder sign-off and Golden Case calibration**, consistent with how every prior methodology_lab v0.1 document in this project has been labeled.
