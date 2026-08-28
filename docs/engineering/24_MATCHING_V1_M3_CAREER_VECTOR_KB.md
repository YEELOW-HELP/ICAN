# 24. Matching V1 M3 — Career Vector Knowledge Base + O*NET Alpha Import

**Status:** IMPLEMENTED (Founder Review "M3 GO", 2026-08-28). Scope: the career-side deterministic vector layer, versioned and provenance-tracked, for a 24-career Alpha catalog. **No user×career matching, no ranking, no Feasibility scoring** — those are M4+. This document does not restate `docs/product/20_MATCHING_V1_FOUNDER_DEFINITION.md`.

---

## 1. New module map

| File | Purpose |
|---|---|
| `app/db/models_career_kb.py` | 3 tables + 2 enums — additive, beside Stage 3A's `Career` |
| `app/services/career_kb/onet_alpha_fixture.py` | offline O*NET source fixture, no network |
| `app/services/career_kb/crosswalk.py` | `create_external_mapping`, `mark_unmapped`, `get_external_mappings` |
| `app/services/career_kb/vectors.py` | `holland_code_to_riasec_vector`, `create_career_matching_profile`, `add_career_matching_component` (the PROFILE_ONLY gate) |
| `app/services/career_kb/seed.py` | `seed_alpha_career_matching_profiles` — idempotent orchestrator |
| `app/services/career_kb/queries.py` | `get_career_matching_profile` — channel-independent read contract |
| `migrations/versions/c4a8e2f19d67_...py` | additive migration, 3 tables |

Stage 3A (`models_knowledge.py`) is unmodified. M1/M2 are unmodified; M3 *reads* M1's `AssessmentScale` rows (the single source of truth for MNP↔O*NET mapping_status) but writes nothing to them.

---

## 2. Alpha career catalog

Reused, unchanged, from the existing Stage 3A curated seed (`app/services/knowledge/seed.py::ensure_seed_knowledge_base`, 32 careers) rather than inventing a second, parallel list — that seed's own docstring already states its careers were "chosen for structural diversity," 2 per `CareerDomain`. M3 selects exactly **24** of those 32, 2 per each of the 12 categories Founder Review §2 named:

| Category | Careers |
|---|---|
| software / data | `software_developer`, `it_support_specialist` |
| engineering / technical | `civil_engineer`, `mechanical_engineer` |
| healthcare | `registered_nurse`, `pharmacist` |
| education | `school_teacher`, `corporate_trainer` |
| social / helping | `social_worker`, `community_outreach_coordinator` |
| sales | `sales_manager`, `retail_sales_associate` |
| management | `operations_manager`, `project_manager` |
| finance / accounting | `accountant`, `financial_analyst` |
| creative / design | `graphic_designer`, `video_editor` |
| logistics / operations | `truck_driver`, `logistics_coordinator` |
| skilled / practical | `electrician`, `plumber` |
| customer / service | `customer_service_representative`, `call_center_operator` |

The other 8 seeded careers (marketing, administration, hospitality, manufacturing domains) are untouched, available for a future catalog expansion.

---

## 3. O*NET source, version, and licensing

**Source version stamp:** `onet_30.3` (the same O*NET release verified current during the M0 hardening pass, `MNP_SCALE_TO_ONET_MAPPING_V0.1.md`).

**Sourcing method (fully disclosed, no exceptions):** 6 of the 24 occupations' RIASEC/Job-Zone/Work-Style data were **verified live** in this session (2026-08-28) via O*NET OnLine's public summary pages: `software_developer` (Software Developers, 15-1252.00), `registered_nurse` (Registered Nurses, 29-1141.00), `accountant` (Accountants and Auditors, 13-2011.00), `electrician` (Electricians, 47-2111.00), `graphic_designer` (Graphic Designers, 27-1024.00), `sales_manager` (Sales Managers, 11-2022.00). The remaining 18 use the same, well-documented, standard O*NET RIASEC/Job Zone classification for those occupations — **transcribed, not independently re-fetched in this session** — flagged `verified_live=False` per-record in `onet_alpha_fixture.py`.

**Licensing/attribution:** O*NET content is developed by the National Center for O*NET Development (sponsored by the U.S. Department of Labor, Employment and Training Administration) and is in the public domain in the United States. O*NET's own published usage terms request attribution. This product's `KnowledgeSource` row for O*NET carries the exact citation text to display wherever O*NET-derived data reaches an end user:

> "This [product/service] incorporates information from O*NET Web Services by the U.S. Department of Labor, Employment and Training Administration."

No equivalent gate applies to O*NET the way `MNP_WORKUA_DATA_USE_DECISION_V0.1.md` gates Work.ua — O*NET requires attribution, not a licensing negotiation, consistent with the M0 Career KB doc's §C.

---

## 4. Crosswalk design

`CareerExternalMapping` is many-to-many by construction (`UniqueConstraint(career_id, source_system, external_code)`, no 1:1 assumption anywhere in the schema or service layer). Two real cardinality cases are deliberately present in the Alpha data, not merely claimed possible:
- **One MNP career → two O*NET occupations:** `software_developer` maps to both Software Developers (15-1252.00, CONFIRMED, confidence 0.95) and Web Developers (15-1254.00, PROVISIONAL, confidence 0.55).
- **Two MNP careers → one O*NET occupation:** `customer_service_representative` and `call_center_operator` both map to Customer Service Representatives (43-4051.00).
- **Deliberately UNMAPPED:** `community_outreach_coordinator` has no defensible single O*NET occupation — a `CareerExternalMapping(mapping_status=UNMAPPED, external_code=NULL)` row records this as a deliberate, auditable statement, not a silent absence.

---

## 5. Mapping-status breakdown (Alpha, 24 careers)

23 careers have ≥1 CONFIRMED O*NET mapping; 1 (`call_center_operator`) has a single PROVISIONAL mapping only; 1 (`community_outreach_coordinator`) is UNMAPPED. `software_developer` additionally carries one PROVISIONAL secondary mapping. Total `CareerExternalMapping` rows: 26 (24 primary + 1 secondary for software_developer + the 1 UNMAPPED marker, counting `call_center_operator`'s single PROVISIONAL row in the 24).

---

## 6. Career-side RIASEC representation

Fully populated for the 23 mapped careers (6 components each = 138 `CareerMatchingComponent` rows for RIASEC alone), `mapping_status=DIRECT`, `matching_usage=MATCH_ENABLED`. `community_outreach_coordinator` has **zero** RIASEC components (not a 0-vector) — proven by `test_missing_source_value_stays_missing_not_zero`.

**Normalization formula** (the one new, explicitly-documented transformation this slice introduces — `holland_code_to_riasec_vector`, `app/services/career_kb/vectors.py`):
```
letters = first 3 RIASEC letters of the real O*NET/Holland code, in rank order
vector[letter_at_rank_0] = 0.90
vector[letter_at_rank_1] = 0.70   (if present)
vector[letter_at_rank_2] = 0.50   (if present)
every other letter        = 0.20  (baseline, not zero)
```
Deterministic and pure: same Holland code string → byte-identical vector every time (`test_riasec_normalization_deterministic`). The *source* value (the Holland code itself) is real O*NET data; this graduated numeric spread is MNP's own disclosed convention for converting a categorical top-letters classification into a full profile — not an O*NET-native numeric scale, and not claimed as one.

---

## 7. Work Style representation

Populated for exactly **one** career in Alpha: `sales_manager` (`leadership`, `initiative` — both DIRECT, both explicitly, textually confirmed as emphasized Work Styles by the live O*NET fetch for that occupation, using the CURRENT post-2024-redesign O*NET taxonomy, not the retired one). Value `0.85` is a disclosed proxy for "O*NET textually confirms this style as emphasized for this occupation" (`transformation_version="onet_explicit_style_signal_v0.1"`) — not a precise imported numeric importance score (O*NET's underlying 1-5 importance ratings were not extractable via the available web-fetch tooling in this session; see §Limitations).

Every other Alpha career has **zero** Work Style components — genuinely unavailable, not fabricated. The mechanism itself (only DIRECT/DERIVED scales may ever receive a component; PROXY/MNP_ONLY are hard-refused via `MatchDisabledScaleError`) is proven for all 10 Work Style scale keys by `tests/test_career_kb_vectors.py`.

---

## 8. Work Values representation

**Zero** `CareerMatchingComponent` rows created for Work Values, for any Alpha career. O*NET's public summary pages surface Work *Styles* importance text cleanly but not a clean numeric Work *Values* breakdown per occupation extractable via this session's tooling — rather than fabricate a plausible-looking number under a false `source_system="onet"` attribution, this family is left entirely unavailable for Alpha. The gate mechanism (only `independence_value`/`impact_helping`/`recognition_status` — the 3 DIRECT Work Values scales — could ever receive a component; the 5 PROXY/MNP_ONLY scales are hard-refused) is proven with a synthetic test value in `test_work_values_mapping_correct`.

---

## 9. Work Environment representation

Same as Work Values: **zero** components created for any Alpha career (no O*NET Work Context numeric data was extracted in this session), mechanism proven with a synthetic test value (`test_environment_mapping_follows_approved_mapping_only`) confirming all 5 Work Environment scales are MATCH_ENABLED per the approved mapping and would accept a genuinely-sourced value.

---

## 10. Requirements / entry-barrier representation

No new schema — Stage 3A's existing `CareerRequirement`/`CareerWorkContext`/`CareerSkill` (already populated for all 24 Alpha careers by the pre-existing seed) serve this need directly, per Founder Review §15 ("do not duplicate existing authoritative knowledge"). The one genuinely new fact M3 adds: **O*NET Job Zone**, stored as a `CareerFact(fact_type="onet_job_zone", is_market_sensitive=False)` for the 23 mapped careers (not a `CareerMatchingComponent` — Job Zone belongs to none of the 4 vector families; it is Feasibility-relevant metadata for a future M4+ pass).

---

## 11. PROFILE_ONLY exclusion — proof, not just policy

`add_career_matching_component` looks up the target scale's `matching_usage` from M1's own `AssessmentScale` rows and raises `MatchDisabledScaleError` outright if it is not `MATCH_ENABLED` — there is no code path, seed data, or parameter that can bypass this. `tests/test_career_kb_vectors.py::test_proxy_does_not_create_match_component` and `test_mnp_only_does_not_create_match_component` attempt exactly this and assert the exception.

---

## 12. Provisional semantics

`CareerMatchingProfile.provisional = True` unconditionally for every Alpha profile (`seed_alpha_career_matching_profiles` passes `provisional=True` explicitly, never computed from anything that could make it `False` in M3). Individual `CareerMatchingComponent.provisional` is `True` for every DERIVED component (`collaboration`, `structure_preference` if ever populated) and `False` for DIRECT ones (`R`/`I`/`A`/`S`/`E`/`C`, `leadership`, `initiative`) — a component's own confidence is tracked independently of the profile-level flag, both queryable.

---

## 13. Career-side coverage metadata

`CareerVectorView.coverage(expected_scale_keys)` (in `app/services/career_kb/queries.py`) computes `(# expected MATCH_ENABLED scales with a real value) / (# expected)` for one family of one career — e.g. `sales_manager`'s Work Style coverage against all 10 possible keys is `2/10`. This is **not** the same concept as user Assessment Coverage (M1/M2) and is never confused with it in the contract (`CareerMatchingProfileView` has no field named `coverage` that could collide). M3 does not compute a final pairwise Match Coverage (user × career) — that requires M4's matching engine to exist first.

---

## 14. Import/idempotency/versioning

`seed_alpha_career_matching_profiles` is idempotent end-to-end: every sub-step (mapping creation, profile creation, component creation, the O*NET `KnowledgeSource`, the Job Zone `CareerFact`) checks-then-creates, never blind-inserts. A `CareerMatchingProfile` is keyed by `(career_id, career_vector_version, mapping_version, source_version)` — an identical re-run returns the existing row; a genuinely changed source/mapping version creates a new `profile_version`, supersedes the prior `is_current` row (never edits/deletes it), exactly mirroring `DeterministicProfile`'s (M2) versioning idiom.

---

## 15. Limitations (full, honest accounting)

- **Work Values and Work Environment are entirely unavailable for Alpha** (§8/§9) — the single largest scope gap. A production import pass needs genuine O*NET bulk database files or API access (not a generic web-summary fetch) to responsibly populate these two families.
- **Work Style is populated for only 1 of 24 careers** (`sales_manager`) — the other 9 DIRECT/DERIVED-eligible scale keys have no Alpha data for the other 23 careers.
- **18 of 24 occupations' RIASEC/Job-Zone data is transcribed, not independently live-verified in this session** — a defensible, standard, well-documented classification, but not re-fetched; flagged per-record (`verified_live=False`) so this is queryable, not hidden.
- The RIASEC graduated-numeric-spread convention (§6) is an MNP transformation of a real Holland top-code, not O*NET's own native numeric interest scale — disclosed, not claimed otherwise.
- 24 careers is an engineering-validation catalog, explicitly not the production ~149-career target (Founder Review §2).

## 16. Future expansion path

A real production import (M3.1+) would: (a) acquire the official O*NET database text files or Web Services API (not a page-by-page web fetch) for Work Styles/Work Values/Work Context numeric importance ratings across the full occupation set; (b) expand the Alpha 24 → the full curated Ukrainian catalog (~149, per `MNP_CAREER_KB_V1.md` §E) once the Work.ua licensing gate (`MNP_WORKUA_DATA_USE_DECISION_V0.1.md`) is separately resolved for UA-market context (not needed for the O*NET vector layer itself); (c) route crosswalk review through `CareerExternalMapping.reviewed_by`/`confidence` fields already present in this schema, requiring no further migration.
