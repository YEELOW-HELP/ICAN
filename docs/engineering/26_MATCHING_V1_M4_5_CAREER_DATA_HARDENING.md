# Matching V1 — M4.5: Career Vector Data Hardening (Founder Review "M4.5 GO", 2026-08-28)

Baseline: `fd69a98` (M4, frozen). Scope: **data hardening only** — M1-M4
architecture (assessment, deterministic profile, `CareerMatchingProfile`
schema, Matching Engine, guarded cosine, ranking, missing-data semantics)
is unchanged and was not redesigned. This document is the M4.5 deliverable
required by the Founder's M4.5 GO directive.

---

## 1. Official source files and versions used

Downloaded directly (via `curl`, not page-scraping) from the official
O*NET Resource Center bulk database release:

```
https://www.onetcenter.org/dl_files/database/db_30_3_text.zip
```

downloaded and extracted 2026-08-28. Three source files were used, out of
the full release:

| File | Scale ID(s) | Content |
|---|---|---|
| `Career Interest Types.txt` | `OI` | Occupational Interests (RIASEC), numeric |
| `Work Styles.txt` | `WI` (+ `DR`, unused) | Work Styles Impact, numeric, **signed** |
| `Work Context.txt` | `CX`, `CT` (+ `CXP`/`CTP`, unused) | Work Context, category-percentage or scaled |

Official scale ranges, taken verbatim from the release's own
`Scales Reference.txt` (never inferred from the data):

| Scale ID | Range | Meaning |
|---|---|---|
| `OI` | 1 to 7 | Occupational Interests |
| `WI` | **-3 to +3** | Work Styles Impact — signed: negative = detrimental to performance in this occupation, positive = beneficial, 0 = neutral/irrelevant |
| `CX` | 1 to 5 | Context (most Work Context elements) |
| `CT` | 1 to 3 | Context — used **only** by "Work Schedules"; confirmed empirically to be a different scale than the other Work Context elements |

**Disclosed discrepancy:** the current O*NET database release is actually
version **31.0**, not 30.3. This pass deliberately stayed pinned to
**30.3** for consistency with every `source_version`/`career_vector_version`
stamp already persisted by M1–M4 (`onet_30.3_raw_numeric`,
`career_vector_v0.2`). Flagged here for the Founder; a future pass could
re-pull 31.0 under a new version stamp if desired.

Licensing: O*NET 30.3 data is available under a **Creative Commons
Attribution 4.0 International License**, attributed to the O*NET 30.3
Database, U.S. Department of Labor, Employment and Training
Administration, National Center for O*NET Development.

---

## 2. RIASEC: old vs new representation

**Old (M3, retained as `LEGACY_ENGINEERING_FALLBACK`):**
`holland_code_to_riasec_vector()` — a Holland high-point-code approximation:
top letter → 0.90, second → 0.70, third → 0.50, all remaining letters →
baseline 0.20. Not an O*NET-native numeric scale; an explicit, documented
MNP convention. Unchanged in this pass — still used by `seed.py`'s
`career_vector_v0.1` profile, never edited.

**New (M4.5, `CURRENT_OFFICIAL`):** the real numeric `OI` value (1–7) for
each of the 6 RIASEC letters, taken directly from `Career Interest
Types.txt` for each career's primary O*NET-SOC code, rescaled to `[0,1]`
via `oi_to_normalized()`. Never blended with the Holland approximation —
the two live as separate, independently-versioned `CareerMatchingProfile`
rows (`career_vector_v0.1` vs `career_vector_v0.2`) for the same career.

Example (`software_developer`, primary SOC `15-1252.00`):

| Letter | Raw OI | M3 Holland approx | M4.5 `oi_to_normalized` |
|---|---|---|---|
| R | 3.61 | 0.20 | 0.435 |
| I | 6.05 | 0.90 | 0.842 |
| A | 2.37 | 0.20 | 0.228 |
| S | 1.81 | 0.20 | 0.135 |
| E | 1.87 | 0.20 | 0.145 |
| C | 5.62 | 0.70 | 0.770 |

---

## 3. Exact normalization formulas (all new in M4.5, `app/services/career_kb/vectors.py`)

Every function is a plain linear rescale of the scale's **official**
min/max, exactly the same convention `MNP_GOLDEN_TEST_V0.1.md` already
uses for user-side Likert scores.

```
oi_to_normalized(raw) = (raw - 1.0) / 6.0        # OI official range 1..7
wi_to_normalized(raw) = (raw + 3.0) / 6.0        # WI official range -3..+3 (signed; 0 -> 0.5)
cx_to_normalized(raw) = (raw - 1.0) / 4.0        # CX official range 1..5
ct_to_normalized(raw) = (raw - 1.0) / 2.0        # CT official range 1..3 ("Work Schedules" only)
```

Transformation version stamps (persisted per component, never mixed):
`onet_oi_numeric_v0.1`, `onet_wi_numeric_v0.1`, `onet_cx_numeric_v0.1`,
`onet_ct_numeric_v0.1`. Legacy stamps unchanged:
`onet_holland_to_riasec_v0.1` (RIASEC legacy), `onet_explicit_style_signal_v0.1`
(Work Style legacy, M3's proxy signal — no longer used by the hardened
profile, still used by the untouched M3 `career_vector_v0.1` profile).

---

## 4. Work Style coverage

DIRECT scales sourced directly from a single O*NET `WI` element:
`leadership` ← "Leadership Orientation" (1.D.1.i), `initiative` ←
"Initiative" (1.D.1.e), `ambiguity_tolerance` ← "Tolerance for Ambiguity"
(1.D.1.d).

DERIVED scale: `collaboration` = mean(`wi_to_normalized`("Social
Orientation", 1.D.2.f), `wi_to_normalized`("Cooperation", 1.D.2.d)) — a
documented, disclosed two-element average, not an invented weighting.

`structure_preference` (Work Style, DERIVED per the M0 mapping doc): **left
unavailable**. Real, disclosed finding — the O*NET 30.3 Work Context
domain contains no "Structured Work"/"Unstructured Work" element at all
(confirmed by enumerating every element name in `Work Context.txt`).
`MNP_SCALE_TO_ONET_MAPPING_V0.1.md`'s claimed DERIVED source for this
scale does not exist in the current release. No substitute was invented,
per Founder Review §5 ("if a transformation is not defensible, leave the
component unavailable"). Flagged for a future mapping-document amendment.

**Coverage: 23/24 mapped careers get all 4 Work Style scale keys**
(`leadership`, `initiative`, `ambiguity_tolerance`, `collaboration`);
`community_outreach_coordinator` (UNMAPPED) gets zero, unchanged from M3.

---

## 5. Work Environment coverage

DIRECT: `collaboration_context` ← "Work With or Contribute to a Work
Group or Team" (4.C.1.b.1.e, `CX`); `customer_interaction_context` ←
"Deal With External Customers or the Public in General" (4.C.1.b.1.f,
`CX`); `schedule_predictability` ← "Work Schedules" (4.C.3.d.4, **`CT`**
— confirmed to be a different scale than the other Work Context elements,
never assumed to be 1–5).

DERIVED: `setting` ← "Indoors, Environmentally Controlled" (4.C.2.a.1.a,
`CX`) alone — a conservative single-element subset of the originally
approved composite, documented as such. `physical_environment` = mean(
"Spend Time Standing" (4.C.2.d.1.b), "Spend Time Walking or Running"
(4.C.2.d.1.d)), both `CX`.

**Coverage: 21/24 careers get ≥2 comparable Work Environment components.**
Two O*NET-SOC codes genuinely lack Work Context data in the O*NET 30.3
release — `13-1082.00` (Project Management Specialists → `project_manager`)
and `13-2051.00` (Financial and Investment Analysts → `financial_analyst`)
— both real occupations with populated Interests/Work Styles, simply not
yet incumbent/expert-rated for Work Context. Left unavailable, not
fabricated. `community_outreach_coordinator` (UNMAPPED) also has zero, as
before.

---

## 6. Work Values decision

**No component created for any of the 24 Alpha careers.** Real, disclosed
finding: no "Work Values" file exists anywhere in the O*NET 30.3 text
database release at all (confirmed by listing every extracted file name)
— genuinely absent, not merely deprecated-but-present, which is stronger
than the Founder's original framing ("marked as no longer updated"). Per
Founder Review §7, Values Fit remains `INSUFFICIENT_DATA` for every
career, unconditionally. A future option, `LEGACY_ONET_WORK_VALUES_V30_0`
(sourcing from an older, pre-redesign O*NET Work Values release under an
explicit legacy label), is documented here as a possibility but was **not
implemented** in this pass — it requires separate Founder approval.

---

## 7. Alpha coverage table (all 24 careers)

| Career | RIASEC | Work Style | Values | Work Environment | Requirements |
|---|---|---|---|---|---|
| software_developer | 6/6 | 4/4 | 0 | 5/5 | 1 |
| it_support_specialist | 6/6 | 4/4 | 0 | 5/5 | 0 |
| civil_engineer | 6/6 | 4/4 | 0 | 5/5 | 1 |
| mechanical_engineer | 6/6 | 4/4 | 0 | 5/5 | 1 |
| registered_nurse | 6/6 | 4/4 | 0 | 5/5 | 2 |
| pharmacist | 6/6 | 4/4 | 0 | 5/5 | 2 |
| school_teacher | 6/6 | 4/4 | 0 | 5/5 | 1 |
| corporate_trainer | 6/6 | 4/4 | 0 | 5/5 | 0 |
| social_worker | 6/6 | 4/4 | 0 | 5/5 | 1 |
| community_outreach_coordinator | 0/6 (UNMAPPED) | 0/4 | 0 | 0/5 | 0 |
| sales_manager | 6/6 | 4/4 | 0 | 5/5 | 0 |
| retail_sales_associate | 6/6 | 4/4 | 0 | 5/5 | 0 |
| operations_manager | 6/6 | 4/4 | 0 | 5/5 | 0 |
| project_manager | 6/6 | 4/4 | 0 | **0/5** (no O*NET Work Context data) | 0 |
| accountant | 6/6 | 4/4 | 0 | 5/5 | 1 |
| financial_analyst | 6/6 | 4/4 | 0 | **0/5** (no O*NET Work Context data) | 1 |
| graphic_designer | 6/6 | 4/4 | 0 | 5/5 | 1 |
| video_editor | 6/6 | 4/4 | 0 | 5/5 | 1 |
| truck_driver | 6/6 | 4/4 | 0 | 5/5 | 2 |
| logistics_coordinator | 6/6 | 4/4 | 0 | 5/5 | 0 |
| electrician | 6/6 | 4/4 | 0 | 5/5 | 2 |
| plumber | 6/6 | 4/4 | 0 | 5/5 | 1 |
| customer_service_representative | 6/6 | 4/4 | 0 | 5/5 | 0 |
| call_center_operator | 6/6 | 4/4 | 0 | 5/5 | 0 |

**Totals:** RIASEC complete 23/24 · Work Style ≥2 comparable components
23/24 · Values 0/24 · Environment ≥2 comparable components 21/24 ·
Requirements present 14/24.

**Per-family median coverage by domain** (fraction of the full scale set
— 6 RIASEC / 4 Work Style / 5 Environment — with a real value):

| Domain | RIASEC | Work Style | Environment |
|---|---|---|---|
| creative | 1.00 | 1.00 | 1.00 |
| customer_service | 1.00 | 1.00 | 1.00 |
| education | 1.00 | 1.00 | 1.00 |
| engineering | 1.00 | 1.00 | 1.00 |
| finance | 1.00 | 1.00 | 0.50 |
| healthcare | 1.00 | 1.00 | 1.00 |
| logistics_transport | 1.00 | 1.00 | 1.00 |
| management | 1.00 | 1.00 | 0.50 |
| sales | 1.00 | 1.00 | 1.00 |
| skilled_trades | 1.00 | 1.00 | 1.00 |
| social_sector | 0.50 | 0.50 | 0.50 |
| technology | 1.00 | 1.00 | 1.00 |

`finance` and `management` sit at 0.50 Environment coverage purely because
of the two real O*NET Work-Context gaps (`financial_analyst`,
`project_manager`) noted above. `social_sector` sits at 0.50 across all
three families purely because `community_outreach_coordinator` is
UNMAPPED (1 of its 2 careers has full coverage, the other has none — the
median of {0, 1} is 0.5).

---

## 8. Persona rankings — BEFORE (`career_vector_v0.1`) vs AFTER (`career_vector_v0.2`)

Both profile versions coexist immutably in the same DB (M3's profile is
simply no longer `is_current` after the hardened seed runs — never
edited, never deleted). `match_profile_to_careers`/`calculate_pair_match`
(M4, unchanged) ran unmodified against both. Full reproduction:
`pytest tests/test_matching_m45_hardened_data.py::test_before_after_persona_report -s`.

### A_technical_investigative

| # | BEFORE career | Interest | # | AFTER career | Interest |
|---|---|---|---|---|---|
| 1 | it_support_specialist | high/0.967 | 1 | mechanical_engineer | high/0.969 |
| 2 | civil_engineer | high/0.967 | 2 | civil_engineer | high/0.967 |
| 3 | mechanical_engineer | high/0.967 | 3 | software_developer | high/0.888 |
| 4 | truck_driver | high/0.816 | 4 | electrician | high/0.885 |
| 5 | software_developer | high/0.816 | 5 | plumber | high/0.840 |
| 6 | electrician | high/0.816 | 6 | truck_driver | high/0.823 |
| 7 | plumber | high/0.816 | 7 | it_support_specialist | high/0.815 |
| 8 | pharmacist | high/0.763 | 8 | pharmacist | high/0.764 |
| 9 | financial_analyst | high/0.751 | 9 | registered_nurse | high/0.732 |
| 10 | accountant | medium/0.674 | 10 | logistics_coordinator | high/0.706 |

### B_social_helping

| # | BEFORE career | Interest | # | AFTER career | Interest |
|---|---|---|---|---|---|
| 1 | corporate_trainer | high/0.965 | 1 | social_worker | high/0.925 |
| 2 | call_center_operator | high/0.848 | 2 | corporate_trainer | high/0.912 |
| 3 | customer_service_representative | high/0.848 | 3 | school_teacher | high/0.895 |
| 4 | retail_sales_associate | high/0.848 | 4 | project_manager | high/0.797 |
| 5 | operations_manager | high/0.848 | 5 | operations_manager | high/0.792 |
| 6 | school_teacher | high/0.819 | 6 | sales_manager | high/0.787 |
| 7 | registered_nurse | high/0.819 | 7 | registered_nurse | high/0.758 |
| 8 | social_worker | high/0.819 | 8 | call_center_operator | high/0.753 |
| 9 | sales_manager | high/0.719 | 9 | customer_service_representative | high/0.753 |
| 10 | logistics_coordinator | high/0.717 | 10 | pharmacist | high/0.737 |

### C_entrepreneurial_leadership

| # | BEFORE career | Interest | # | AFTER career | Interest |
|---|---|---|---|---|---|
| 1 | sales_manager | high/0.985 | 1 | project_manager | high/0.982 |
| 2 | call_center_operator | high/0.965 | 2 | sales_manager | high/0.976 |
| 3 | customer_service_representative | high/0.965 | 3 | operations_manager | high/0.971 |
| 4 | retail_sales_associate | high/0.965 | 4 | retail_sales_associate | high/0.931 |
| 5 | logistics_coordinator | high/0.965 | 5 | logistics_coordinator | high/0.924 |
| 6 | operations_manager | high/0.965 | 6 | call_center_operator | high/0.918 |
| 7 | project_manager | high/0.965 | 7 | customer_service_representative | high/0.918 |
| 8 | accountant | high/0.936 | 8 | financial_analyst | high/0.911 |
| 9 | financial_analyst | high/0.848 | 9 | accountant | high/0.870 |
| 10 | corporate_trainer | high/0.819 | 10 | corporate_trainer | high/0.761 |

### D_artistic_creative

| # | BEFORE career | Interest | # | AFTER career | Interest |
|---|---|---|---|---|---|
| 1 | video_editor | high/0.891 | 1 | graphic_designer | high/0.855 |
| 2 | school_teacher | high/0.808 | 2 | video_editor | high/0.791 |
| 3 | social_worker | high/0.808 | 3 | corporate_trainer | medium/0.659 |
| 4 | graphic_designer | high/0.776 | 4 | school_teacher | medium/0.633 |
| 5 | pharmacist | medium/0.544 | 5 | social_worker | medium/0.581 |
| 6 | software_developer | medium/0.529 | 6 | software_developer | medium/0.488 |
| 7 | mechanical_engineer | medium/0.495 | 7 | pharmacist | medium/0.479 |
| 8 | financial_analyst | medium/0.478 | 8 | financial_analyst | medium/0.472 |
| 9 | logistics_coordinator | medium/0.478 | 9 | registered_nurse | medium/0.417 |
| 10 | project_manager | medium/0.478 | 10 | civil_engineer | medium/0.411 |

### E_flat_undifferentiated

BEFORE: `ranked` empty (all 23 mapped careers `LOW_DIFFERENTIATION`, the
1 UNMAPPED career `INSUFFICIENT_DATA`). AFTER: `ranked` still empty,
identical shape. **The flat persona remains fully protected under the
new data** — never a single SCORED Interest Fit, exactly as required.

**Work Style Fit and Values Fit, every persona, every career:** in the
tables above, Work Style Fit shows `insufficient_data` BEFORE and
`low_differentiation` AFTER for effectively every row; Values Fit shows
`insufficient_data` in both. This is disclosed and explained in §10 below
— it is a real, surprising side effect worth flagging, not a silently
absorbed detail.

---

## 9. Family coverage / ranking inputs

Every ranked entry across all 4 non-flat personas participates in the
ranking sort via `families=['interest']` only — Work Style and Values
never reach `SCORED` status for any Alpha career under the current M2 test
personas (see §10). Feasibility is `partial` for every entry shown (no
`BLOCKED` entries appear in the reproduced Top-10s; the full `blocked`
group is unaffected by this pass since Feasibility logic and inputs are
untouched by M4.5).

---

## 10. Engine bug investigation — none found, but one real, disclosed surprise

**No bug found in `app/services/matching/pure.py` or `engine.py`.**
`git diff -- app/services/matching/` is empty for this entire phase — the
M4 engine was not touched, consistent with Founder Review §10.

**Disclosed, surprising finding (not a bug, reported per instructions):**
after hardening, **Work Style Fit is `LOW_DIFFERENTIATION` for every
persona/career pair** that previously would have been `INSUFFICIENT_DATA`
(M3's Work Style data was too sparse — 0 or 1 component per career — to
ever reach the differentiation check at all). Root cause, traced and
confirmed: `tests/test_basic_profile_personas.py`'s `PERSONAS` bias maps
(reused unchanged from M2, per convention) only bias `("riasec", <letter>)`
answers; every Work Style Likert item is left at the flat
`default_likert=3`. With M4.5 now supplying ≥2 real comparable Work Style
components per career (crossing the `MIN_COMPARABLE_COMPONENTS=2` gate
for the first time), the guarded-cosine engine correctly proceeds past the
first guard and then correctly hits the **second** guard — the
`DIFFERENTIATION_STDEV_THRESHOLD=0.10` check — because the **user** side
now has zero variance across the comparable Work Style scales (every
answer normalizes to the identical value). This is the guard functioning
exactly as designed (Founder Review's own invariant: never manufacture a
SCORED result out of an undifferentiated input), on the **user** side of
the pair, triggered as a side effect of the **career** side finally having
enough data to reach it. It is not an M4 engine defect and not an M4.5
career-data defect — it is a **gap in the existing M2 test-persona
fixtures**, which never needed Work Style variation before because no
career ever had enough Work Style data to require it. Recommendation:
extend `PERSONAS` with plausible Work Style Likert biases in a future
pass (M5 candidate) so persona reruns can exercise a genuinely SCORED
Work Style Fit — deliberately **not** done in this pass, since patching
test fixtures to produce a more flattering Work Style result while
"data hardening" is underway would blur the line Founder Review draws
between fixing a demonstrated defect and tuning toward an expected
outcome.

---

## 11. Focused tests (18 Founder-specified items + supporting tests)

`tests/test_matching_m45_hardened_data.py` — 25 tests, all passing:

1. Real O*NET OI numeric values used for RIASEC (not Holland approximation)
2. Holland-code approximation not preferred when OI is available
3. OI normalization exact (linear rescale of the official 1–7 range)
4. Full six-dimensional career vector retained
5. Work Styles sourced from O*NET 30.3 (`WI` scale, not `IM`)
6. Only approved DIRECT/DERIVED mappings imported (`structure_preference` never populated)
7. Work Style normalization exact (signed -3..+3, 0 → 0.5)
8. Work Context imported only for approved mappings (5 exact scale keys)
9. Missing data remains missing (`project_manager`/`financial_analyst` Work Context; UNMAPPED career)
10. Work Values remain insufficient without an approved current source (0/24, `LEGACY_ONET_WORK_VALUES_V30_0` documented, not implemented)
11. Zero AI calls (AST scan across all 4 new/modified M4.5 modules)
12. No Work.ua data import (source-text scan across the same modules)
13. Offline fixture deterministic (2 calls, identical result; no network tokens in source)
14. Source provenance preserved (source_system/element_id/element_name/raw_value/transformation_version, per component)
15. All 24 careers processed by the hardened seed
16/17. M4 engine + full regression remain green (see §12)
18. Flat persona remains protected under hardened data

Plus: legacy M3 profile untouched (existence, values, `is_current=False`
after hardening, still independently queryable by `version=1`); quality
classifier tier tests; the BEFORE/AFTER persona report generator (§8).

---

## 12. Full regression

```
641 passed, 2 skipped in 544.09s (0:09:04)
```

Prior baseline (post-M4): 616 passed, 2 skipped. **+25 new tests, zero
regressions, zero failures.** `git diff -- app/services/matching/` is
empty — the M4 engine package has zero changes for this phase.

---

## 13. Alembic head

**Unchanged: `d5f9b3a71c84`** (M4's migration). No new migration was
needed — M4.5 is a pure new-data pass that reuses M3's existing
`CareerMatchingProfile`/`CareerMatchingComponent` tables and M3's existing
versioning contract (`create_career_matching_profile`'s
supersede-on-new-version-stamp behavior). Confirmed no new file exists
under `migrations/versions/`.

---

## 14. Remaining data gaps (honest inventory)

- **Work Values:** 0/24 — no current O*NET source exists at all (not
  merely deprecated). Requires either a separately-approved
  `LEGACY_ONET_WORK_VALUES_V30_0` source or a different current-data
  source entirely.
- **`structure_preference` (Work Style):** unavailable for all 24 careers
  — no current O*NET Work Context element corresponds to it anymore;
  `MNP_SCALE_TO_ONET_MAPPING_V0.1.md` needs a documented amendment.
- **Work Environment:** 2/24 careers (`project_manager`,
  `financial_analyst`) have zero O*NET Work Context data for their SOC
  code — a genuine O*NET data gap, not an MNP mapping problem.
- **`community_outreach_coordinator`:** still fully UNMAPPED (no clean
  O*NET-SOC correspondence) — unchanged from M3, out of scope for a data
  hardening pass.
- **Requirements coverage:** only 14/24 careers have any
  `CareerRequirement` rows at all — this is Stage 3A/M0 scope, untouched
  by M4.5, but relevant to Transition Feasibility quality going forward.
- **Test-persona Work Style blindness (§10):** the existing M2
  `PERSONAS` fixtures cannot currently produce a SCORED Work Style Fit
  for any career, because they never vary Work Style Likert answers —
  worth hardening in a future pass, deliberately not done here.
- **O*NET 31.0 vs 30.3:** this pass used 30.3 for version-stamp
  consistency; O*NET has since published 31.0.

---

## 15. Recommendation for M5

**CONDITIONAL GO.** The underlying career-side data for RIASEC and Work
Style is now genuinely CURRENT_OFFICIAL for 23/24 Alpha careers, and
Work Environment for 21/24 — a real, substantial hardening over M3's
placeholder data, with zero regressions and the M4 engine proven to
require no code changes. Before building product UI on top of this,
recommend:

1. A short, separate pass to extend the M2 test-persona fixtures with
   Work Style Likert biases (§10) — cheap, low-risk, and needed to
   actually exercise/validate Work Style Fit before it reaches a user.
2. A Founder decision on `structure_preference` (drop the scale, or
   accept it as permanently unavailable) and on whether to pursue
   `LEGACY_ONET_WORK_VALUES_V30_0` or a different Work Values source.
3. Confirm whether to re-pin to O*NET 31.0 now or defer.

None of these block M5 UI work on the Interest Fit / Work Style Fit /
Transition Feasibility outputs that already have real, sufficient data
(23-24/24 careers) — only Values Fit (0/24) needs to be explicitly
represented as "not yet available" in any UI copy, not hidden or implied
as zero.

---

*Source attribution: This document and the underlying data incorporate
information from the O*NET 30.3 Database, developed by the U.S.
Department of Labor, Employment and Training Administration, National
Center for O*NET Development, used under the CC BY 4.0 license.*
