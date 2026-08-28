# MNP Career KB V1 — Source Architecture & Schema

**Status:** PROVISIONAL v0.1 — specification only, no schema created by this document.

> **HARDENED (2026-08-28) per Founder Review "Matching V1 M0":** §C below is corrected to cite the **current** O*NET Work Styles taxonomy — a genuine structural redesign (16→21 elements, 6→7 higher-order factors) took effect starting **O\*NET 30.1**, confirmed via direct research (HumRRO 2024 report + O\*NET 30.2/30.3 Data Dictionary), not assumed. See `methodology_lab/05_GOLDEN_TEST/MNP_SCALE_TO_ONET_MAPPING_V0.1.md` for the full per-scale DIRECT/DERIVED/PROXY/MNP_ONLY reconciliation and the Career Vector Compatibility Proof required before any Fit family may participate in Matching V1.
**Depends on:** `docs/product/20_MATCHING_V1_FOUNDER_DEFINITION.md` §3/§6A, `MNP_GOLDEN_TEST_V0.1.md` §16 (career-vector encoding), existing Stage 3A `app/db/models_knowledge.py` (`Career`, `CareerRequirement`, `CareerWorkContext`, `CareerSkill`, `CareerFact`), and the sibling gate document `MNP_WORKUA_DATA_USE_DECISION_V0.1.md`.

This document specifies the schema and governance for the three-layer Career KB source model. It does not modify `app/`; M3 (doc 21 §5) implements this design.

---

## A. Canonical Career identity

Unchanged from Stage 3A: **`Career.code`** remains the sole internal, stable, primary business identifier for a career. Every layer described below (Work.ua, O*NET, MNP curation) attaches to a `Career` row via `Career.code` — never the reverse. No external identifier is ever used as a foreign key target, a lookup key in application logic, or a de-duplication key. This extends the existing Stage 3A rule (brief §16: "external IDs must not become our primary business IDs") to the two new external sources introduced here.

---

## B. Work.ua reference mapping

Work.ua's Career Guide (~149 UA professions) is treated as **layer A**: a reference source for UA names, industry, descriptions, hard/soft skills, education paths, related professions, and market-sensitive facts (salary, vacancy counts, trend). Until the licensing gate in `MNP_WORKUA_DATA_USE_DECISION_V0.1.md` is resolved, Work.ua content is:
- **referenceable** (an MNP curator may read it and manually author an equivalent, differently-worded MNP description),
- **not bulk-imported, scraped, or republished verbatim** in any automated pipeline.

Each `Career` row that has a Work.ua counterpart gets one `CareerExternalMapping` row (§D) with `source_system = "workua"`, storing the Work.ua slug/URL as a reference, not as displayed content, until the licensing decision permits direct reuse.

---

## C. O*NET mapping

O*NET is treated as **layer B**: the psychometric/occupational vector source (RIASEC, Work Values, Work Styles, Job Zones). Referenced via **O\*NET-SOC codes** (e.g. `21-1021.00`), stored in `CareerExternalMapping` with `source_system = "onet"`. O*NET's public-domain structured data (Interest Profiler scores, Work Values importance scores, Work Styles importance scores, Job Zone) is imported directly, respecting O*NET's documented usage terms (public domain, attribution requested — no licensing gate needed, unlike Work.ua). Every imported value carries `source_version` (the O*NET database release version, e.g. `30.3`) so a later O*NET release doesn't silently overwrite without a visible version bump. No AI-generated vector reconstruction is permitted when O*NET structured data already exists for a mapped occupation (Founder invariant, doc 20).

**Work Styles taxonomy version note (M3 implementation risk, verified 2026-08-28):** O\*NET's Work Styles domain underwent a genuine structural redesign — the historical 16-element/6-higher-order-factor taxonomy was replaced by a **21-element/7-higher-order-factor** taxonomy (Independence removed and relocated to Work Values; Analytical Thinking removed to Skills/Abilities; 7 new elements added, including Cautiousness, Self-Confidence, Intellectual Curiosity, Tolerance for Ambiguity, Optimism, Humility, Sincerity), integrated into production starting **O\*NET 30.1**. Any M3 O*NET importer MUST target the **current** `Work Style Names and Descriptions for O*NET Content Model Reference` file, not the retired 16-element structure many older integrations/tutorials still reference — this is a real, concrete implementation risk this hardening pass surfaced, not a hypothetical one. See `methodology_lab/05_GOLDEN_TEST/MNP_SCALE_TO_ONET_MAPPING_V0.1.md` §B for the full per-key reconciliation against this current taxonomy.

---

## D. MNP curation

**Layer C.** MNP curation is the only layer permitted to:
- Add Ukrainian entry-requirement/localization detail (language requirements, licensing/legal constraints specific to Ukraine, local education pathways) not present in either source.
- Correct or annotate a Work.ua↔O*NET crosswalk (§J).
- Add localized labels/descriptions distinct from a raw Work.ua translation.
- Add feasibility annotations used by the Golden Test's Constraints matching (§14 of the Golden Test doc).

MNP curation **never silently overwrites** Work.ua- or O*NET-sourced provenance fields — a curated correction is stored as an additional, separately-attributed field/row, with the original source value and its provenance preserved alongside it (same "never mutate the source, add an overlay" discipline as the existing Stage 3B correction/readmodel pattern, doc 21 §2.1).

---

## E. Career matching vectors

New, additive entity layer, versioned independently of the Stage 3A `Career` table:

```
Career (existing, Stage 3A, UNCHANGED)
  └── CareerMatchingProfile (NEW, one per Career, versioned)
        ├── riasec: (R,I,A,S,E,C) — each component nullable + provenance
        ├── work_style: 10 components (HPM v0.1 §3.1 keys) — nullable + provenance
        ├── work_values: 8 components (Golden Test doc §11 keys) — nullable + provenance
        ├── work_environment: 5 components (HPM v0.1 §3.2 keys) — nullable + provenance
        ├── job_zone: O*NET Job Zone (1-5) + education/experience descriptor
        ├── entry_requirements: structured (education level, licenses, typical experience)
        ├── source_version, mapping_version, localization_version
        └── is_provisional: bool
  └── CareerMatchingProfileComponents (NEW, optional finer-grained table if per-component
        provenance rows are needed instead of embedded JSON — implementation choice for M3,
        not fixed here)
```

`CareerMatchingProfile` never overwrites or removes any existing Stage 3A `Career`/`CareerRequirement`/`CareerWorkContext`/`CareerSkill` row — purely additive, one-to-one with `Career`.

---

## F. Market-sensitive facts

Reuses the existing Stage 3A `CareerFact` model and its `is_market_sensitive` flag. Every market-sensitive fact (salary range, vacancy count, trend) MUST carry, non-optionally: `source_id`, `source_url_or_reference`, `observed_at`, `expires_at`. No market-sensitive value is ever displayed without its `expires_at` being checked against "now" at render time — an expired fact is hidden or explicitly marked stale, never silently shown as current (see §H, and Open Question G in the sibling data-use decision doc for the exact expiry windows).

---

## G. Source/provenance model

Every value imported from Work.ua or O*NET, and every value added by MNP curation, carries:
- `source_system` (`workua` | `onet` | `mnp_curation`)
- `source_version` (source's own release/version identifier)
- `mapping_version` (this KB's crosswalk-logic version, independent of the source's own version)
- `imported_at` / `curated_at` timestamp
- `reviewed_by` (nullable — set once a human has reviewed an auto-imported mapping, §J)

This mirrors exactly the versioning discipline already used for `DirectionRun` (doc 21 §4) — provenance is a first-class, queryable field set, never inferred from a timestamp or a comment.

---

## H. Expiry/freshness model

Applies to `CareerFact` rows flagged `is_market_sensitive=True` (§F). `expires_at = observed_at + freshness_window`, where `freshness_window` is fact-type-specific (see Open Question G in `MNP_WORKUA_DATA_USE_DECISION_V0.1.md` for the full options analysis and recommended windows: salary ≈6 months, vacancy counts ≈30 days, trend ≈6 months). Non-market-sensitive facts (e.g. a profession's typical skill list) have no expiry — they are versioned via `source_version`/`mapping_version` instead, refreshed only on a deliberate re-import.

---

## I. Localization

All user-facing text (career name, description, skill labels) is stored in Ukrainian as the primary/only locale for V1 — no multi-locale schema is introduced in M0. A `localization_version` field on `CareerMatchingProfile` (§E) exists so a future MNP re-translation/re-labeling pass is trackable, without implying multi-language support exists yet.

---

## J. Crosswalk review workflow

Every `CareerExternalMapping` row starts in `mapping_status = PENDING_REVIEW` when created by an (eventual) automated O*NET-code-suggestion step, or `MANUAL` when created directly by an MNP curator. A human reviewer (Methodology Owner or delegated curator) moves it to `CONFIRMED` or `REJECTED`; only `CONFIRMED` mappings feed live `CareerMatchingProfile` computation by default (a `PENDING_REVIEW` mapping may be used for preview/testing but is flagged `is_provisional=True` wherever it's shown). This mirrors the existing consultant-review state-machine shape (doc 21 §2.1) without reusing the same table — crosswalk review is a distinct, simpler, single-approver workflow, not the multi-outcome Direction review flow.

---

## K. Unmapped-state handling

A `Career` with **zero** `CareerExternalMapping` rows to O*NET has `CareerMatchingProfile = NULL` (or all components `UNSCORED`) — it simply cannot produce Interest/Work Style/Values Fit until mapped. It remains fully visible in the Career Catalog if it has enough Stage 3A `CareerRequirement`/`CareerWorkContext` data for Feasibility alone, explicitly labeled "psychometric fit not yet available" rather than silently hidden or given an invented default vector. **Never invent a crosswalk** — an unmapped career stays unmapped until a human confirms one (§J).

---

## L. Provisional vector semantics

`is_provisional=True` on a `CareerMatchingProfile` (or an individual component) means: the value exists and is usable, but has not yet passed MNP curation review (§J) or Golden Case calibration. Provisional values ARE used in live matching (so the catalog isn't empty during pilot), but are visibly flagged in the Compatibility Report ("this career's profile is provisional, based on an unreviewed source mapping") — never presented with the same confidence as a `CONFIRMED`, curated profile.

---

## M. Update/versioning strategy

`CareerMatchingProfile` bumps `source_version` when the underlying O*NET release changes, and `mapping_version` when MNP's own crosswalk logic changes (independent axes — an O*NET release bump doesn't require a crosswalk-logic change and vice versa). A version bump creates a **new** `CareerMatchingProfile` snapshot rather than mutating the old one in place, so any `DirectionRun`/matching result that pinned a specific `career_vector_version` (doc 21 §4) remains reproducible against the exact data it was computed from.

---

## N. Future Opportunity DB link

Out of scope for M0–M6 (doc 21 §2.5, DEFER). Reserved: a future `Opportunity` entity (vacancies/postings) would attach to `Career.code`, never to a Work.ua/O*NET external ID directly, preserving the identity rule in §A.

---

## O. Future Career Route link

Out of scope for M0–M6 (DEFER). Reserved: a future `CareerRoute` entity linking a curated Direction (doc 21 §2.1 review layer) to a sequence of `Career`/skill-development milestones. Not designed here; noted only so `CareerExternalMapping`/`CareerMatchingProfile` naming doesn't collide with it later.

---

## Open Math/Design Questions (Founder decisions required before M3)

### E. Career catalog granularity

**Options:** (1) small curated ~149 Work.ua-level catalog surfaced to users, O*NET's larger taxonomy (~900+ detailed occupations) used only underneath as the vector source via crosswalk; (2) surface the full O*NET occupation taxonomy directly to users; (3) a hybrid — user-selectable "broad" vs "detailed" catalog view.

**Pros/Cons:** (1) matches what a Ukrainian pilot user can actually act on locally (~149 recognizable UA professions vs ~900+ granular US BLS occupations most of which have no direct Ukrainian labor-market equivalent); keeps MNP curation load bounded (149 careers to manually enrich, not 900+). (2) maximizes psychometric granularity but is unusable for a Ukrainian audience and multiplies the Work.ua-licensing-independent curation burden by ~6x. (3) more flexible but adds real UI/product complexity for a V1 pilot with no demonstrated user demand for it yet.

**V0.1 RECOMMENDATION:** Option 1 — ~149 Work.ua-level careers as the exposed Career Catalog surface; full O*NET taxonomy used only as the underlying vector source via many-to-one crosswalk (§F).
**WHY:** Directly matches Founder's own stated direction in doc 20 ("small curated UA catalog first, rich source taxonomy underneath"); keeps curation scope bounded and locally relevant.
**PROVISIONAL STATUS:** Provisional — may expand the exposed catalog later if pilot users request finer-grained distinctions within a broad Work.ua category.

### F. Work.ua↔O*NET crosswalk cardinality

**Options:** (1) assume strict one-to-one; (2) support many-to-many via the `CareerExternalMapping` crosswalk entity, confidence-weighted averaging when multiple O*NET codes map to one Work.ua career; (3) force a single "best representative" O*NET code per Work.ua career (one-to-one by curation fiat, discarding the rest).

**Pros/Cons:** (1) is false to reality — e.g. a broad UA "Розробник ПЗ" (Software Developer) genuinely spans multiple distinct O*NET codes (Software Developers, Web Developers, QA Analysts/Testers) with materially different RIASEC/Work-Style profiles; forcing one-to-one silently discards signal. (2) most accurate, fully auditable per-mapping via the crosswalk table, but requires an averaging rule to be specified precisely (confidence-weighted mean, weights = mapping review status/confidence). (3) simpler than (2) but still silently discards real distinctions a curator might want visible later.

**V0.1 RECOMMENDATION:** Option 2 — many-to-many, explicit `CareerExternalMapping` rows, `CareerMatchingProfile` vector computed as a confidence-weighted average across all `CONFIRMED` mappings for that career (unconfirmed mappings excluded from the live average, but visible to curators).
**WHY:** Reflects real-world crosswalk cardinality honestly, keeps every individual mapping auditable rather than silently blended, and doesn't force a false one-to-one simplification the Founder explicitly warned against ("do not assume one-to-one").
**PROVISIONAL STATUS:** Provisional — exact confidence-weighting formula (e.g. equal weight vs review-status-weighted) is an M3 implementation detail requiring Methodology Owner sign-off once real crosswalk data exists to calibrate against.

---

## CareerExternalMapping — proposed entity shape

```
CareerExternalMapping
  id
  career_id           → Career.id (FK; Career.code remains the canonical identity, §A)
  source_system        enum { workua, onet }
  external_code         string   # Work.ua slug/id, or O*NET-SOC code
  external_reference    string   # URL or citation, reference-only for workua (§B)
  mapping_status        enum { PENDING_REVIEW, CONFIRMED, REJECTED, MANUAL }
  confidence            float [0,1], nullable until reviewed
  mapping_version       string
  reviewed_by           nullable FK → staff user
  created_at, updated_at
  UNIQUE(career_id, source_system, external_code)
```
