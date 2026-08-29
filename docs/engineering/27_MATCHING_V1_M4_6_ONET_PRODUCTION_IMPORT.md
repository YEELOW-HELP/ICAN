# 27. Matching V1 M4.6 — Career Vector Data: Production O*NET Import (DATA-002)

Baseline: `e6bae43` (M4.5, frozen). Scope: **career-vector data only** —
replace the hand-typed 24-career O*NET fixture with a full, reproducible
import from the official O*NET bulk text database, close the M4.5 Work
Style / Work Values coverage gaps, and add a repeatable crosswalk-
suggestion tool. **No engine change** (`app/services/matching/` untouched),
**no migration** (pure new-data version bump), **no Work.ua** (licensing
gate stands), **no ESCO**.

Founder decisions (DATA-002 session): O*NET **31.0** for live scales +
O*NET **30.2** for Work Values (3 DIRECT keys only); live pin =
`career_vector_v0.3` / `source_version = onet_31.0`; crosswalk tooling
built + run against the 24-Alpha catalog only (the ~149 Work.ua catalog
stays blocked on `MNP_WORKUA_DATA_USE_DECISION_V0.1.md`).

---

## 1. New / changed module map

| Path | Status | Purpose |
|---|---|---|
| `scripts/onet_import/common.py` | NEW | paths, version pins, O*NET element-ID ↔ MNP scale-key maps, tab-file reader |
| `scripts/onet_import/download_onet.py` | NEW | direct download + extract `db_31_0_text.zip`, `db_30_2_text.zip` (CC BY 4.0, no scrape); sha256-verified, idempotent |
| `scripts/onet_import/build_onet_reference.py` | NEW | parse the real O*NET files → `data/onet/onet_reference.sqlite` (all 1016 occupations, every scale the 4 vector families use); asserts ranges vs `Scales Reference.txt` |
| `scripts/onet_import/export_source_artifact.py` | NEW | reference DB → `app/services/career_kb/onet_source_v3.json`, scoped to mapped O*NET-SOC codes |
| `scripts/onet_import/suggest_crosswalk.py` | NEW | MNP careers → ranked O*NET-SOC candidates (title + alt-title match) → `data/crosswalks/onet_suggestions.csv` (review artifact, never auto-applied) |
| `app/services/career_kb/onet_source_v3.py` | NEW | loader + version constants for the generated artifact (mirrors `onet_30_3_numeric_fixture.py`'s API) |
| `app/services/career_kb/onet_source_v3.json` | NEW (generated, committed) | 23 O*NET-SOC records, ~28 KB — keeps CI network-free |
| `app/services/career_kb/vectors.py` | +1 fn | `ex_to_normalized` + `EX_TRANSFORMATION_VERSION` (additive; nothing existing changed) |
| `app/services/career_kb/seed_v3.py` | NEW | `seed_career_matching_profiles_v3` — builds `career_vector_v0.3` via the unchanged `create_career_matching_profile` / `add_career_matching_component` gates |
| `tests/test_career_kb_onet_production_import.py` | NEW | 18 offline tests |
| `requirements-datalab.txt` | NEW | `requests` — scripts only, NOT in `requirements.txt`, NOT imported by `app/` |
| `data/onet/**`, `data/crosswalks/**` | gitignored | raw zips, reference DB, suggestion CSV |

`app/services/career_kb/onet_30_3_numeric_fixture.py` and `seed_hardened.py`
(M4.5) are **unchanged** — v0.2 stays as immutable history.

---

## 2. Official source files and versions

Downloaded 2026-08-29 from the O*NET Resource Center bulk release:

```
https://www.onetcenter.org/dl_files/database/db_31_0_text.zip   sha256 c7cfcd41…  (13.2 MB, Aug 2026)
https://www.onetcenter.org/dl_files/database/db_30_2_text.zip   sha256 b5479271…  (13.4 MB, Jul 2026)
```

| MNP family | O*NET file | Scale ID | Release | Element IDs |
|---|---|---|---|---|
| RIASEC | `Career Interest Types.txt` | `OI` (1–7) | **31.0** | `1.B.1.a`–`1.B.1.f` |
| Work Style | `Work Styles.txt` | `WI` (−3…+3, signed) | **31.0** | `1.D.1.i` Leadership Orientation, `1.D.1.e` Initiative, `1.D.1.d` Tolerance for Ambiguity, `1.D.2.f` Social Orientation + `1.D.2.d` Cooperation (→ `collaboration` mean) |
| Work Environment | `Work Context.txt` (Category = `n/a`) | `CX` (1–5) / `CT` (1–3) | **31.0** | `4.C.1.b.1.e`, `4.C.1.b.1.f`, `4.C.3.d.4` (CT), `4.C.2.a.1.a`, `4.C.2.d.1.b` + `4.C.2.d.1.d` (→ `physical_environment` mean) |
| Work Values | `Work Values.txt` | `EX` (1–7) | **30.2** | `1.B.2.f` Independence → `independence_value`; `1.B.2.d` Relationships → `impact_helping`; `1.B.2.c` Recognition → `recognition_status` |

Scale ranges taken verbatim from each release's own `Scales Reference.txt`
and asserted at build time (`build_onet_reference._assert_scale_ranges`).

**Why the split:** `Work Values.txt` was removed from the O*NET database
in release 30.3; O*NET's own guidance is to keep using the 30.2 file.
Confirmed empirically: no `Work Values.txt` in `db_31_0_text.zip`; present
in `db_30_2_text.zip`.

**Re-confirmed M4.5 finding:** O*NET 31.0 Work Context still contains **no**
"Structured Work" / "Unstructured Work" element — `structure_preference`
(Work Style, DERIVED) remains unavailable, not fabricated.

---

## 3. Normalization formulas

`app/services/career_kb/vectors.py` — the M4.5 functions are reused
unchanged; only `ex_to_normalized` is new:

```
oi_to_normalized(raw) = (raw - 1) / 6          # OI  1..7   (M4.5)
wi_to_normalized(raw) = (raw + 3) / 6          # WI  -3..+3 (M4.5; 0 -> 0.5)
cx_to_normalized(raw) = (raw - 1) / 4          # CX  1..5   (M4.5)
ct_to_normalized(raw) = (raw - 1) / 2          # CT  1..3   (M4.5)
ex_to_normalized(raw) = (raw - 1) / 6          # EX  1..7   (NEW, M4.6)
```

`transformation_version` per component:
`onet_oi_numeric_v0.1`, `onet_wi_numeric_v0.1`, `onet_cx_numeric_v0.1`,
`onet_ct_numeric_v0.1` (reused), and **`legacy_onet_work_values_30.2_v0.1`**
(new) for every Work Values component — its `source_element_name` also
carries the "(O*NET Work Values, onet_30.2)" note, so the mixed-release
provenance is queryable per row even though the profile's single
`source_version` string is `onet_31.0`.

DERIVED composites (unchanged from M4.5): `collaboration` = mean(Social
Orientation, Cooperation); `physical_environment` = mean(Spend Time
Standing, Spend Time Walking or Running); `setting` = "Indoors,
Environmentally Controlled" alone.

---

## 4. Coverage — v0.2 (M4.5) → v0.3 (M4.6)

23 of the 24 Alpha careers get a `career_vector_v0.3` profile.
`community_outreach_coordinator` is deliberately UNMAPPED (no O*NET-SOC) —
no profile, exactly as in M3/M4.5. `software_developer` uses its CONFIRMED
primary code `15-1252.00` (the PROVISIONAL `15-1254.00` stays crosswalk
provenance only — M4.5 primary-mapping rule).

| Family | v0.2 (M4.5) | v0.3 (M4.6) | Change |
|---|---|---|---|
| **RIASEC** | 23/24 careers, Holland top-code **approximation** (0.90/0.70/0.50/0.20 spread) | **23/23 careers, real O*NET 31.0 `OI` numerics** | approximation → measured |
| **Work Style** | **1/24** careers (`sales_manager` only), a `0.85` proxy signal | **23/23 careers**, 4 real components each (`leadership`, `initiative`, `ambiguity_tolerance` DIRECT + `collaboration` DERIVED), real `WI` numerics | proxy on 1 → measured on 23 |
| **Work Values** | **0/24** | **20/23 careers**, 3 DIRECT components each, O*NET 30.2 `EX` numerics | 0 → 20 |
| **Work Environment** | 21/24 careers (`project_manager`, `financial_analyst` had no 30.3 Work Context) | **22/23 careers**, 5 components each | `project_manager` gained Work Context data in 31.0 |
| Job Zone fact | 23/24 (`onet_job_zone` `CareerFact`) | refreshed to `source_version = onet_31.0` | — |

**Genuine remaining data gaps (honest inventory):**

- **`financial_analyst`** (`13-2051.00`): no O*NET Work Context **and** no
  30.2 Work Values (the SOC split out in the 2018 SOC revision, after the
  2008-era Work Values analyst data). RIASEC + Work Style only.
- **`project_manager`** (`13-1082.00`) and **`software_developer`**
  (`15-1252.00`): no 30.2 Work Values (same SOC-vintage reason). RIASEC +
  Work Style + Work Environment.
- **5 of 8 MNP Work Values keys** (`income`, `stability`, `growth`,
  `work_life_balance`, `learning`) have **no O*NET counterpart at all** —
  `MNP_SCALE_TO_ONET_MAPPING_V0.1.md` §C. They stay unsourced (MNP
  curation judgment, not import). The gate
  (`add_career_matching_component` → `MatchDisabledScaleError`) refuses
  them independently.
- **`structure_preference`** (Work Style): no O*NET element, 30.3 or 31.0.
- `community_outreach_coordinator`: still UNMAPPED.

Every gap is an **absent component**, never a fabricated `0` (proven by
`test_missing_source_stays_null_never_zero`).

---

## 5. BEFORE (v0.2) / AFTER (v0.3) persona rankings

`pytest tests/test_career_kb_onet_production_import.py::test_before_after_persona_report -s`.
Personas from `tests/test_basic_profile_personas.py` (RIASEC-biased only).

**Interest Fit rankings are essentially unchanged** v0.2 → v0.3 — O*NET
31.0's `OI` values track 30.3's closely for these occupations, and the M4.5
`oi_to_normalized` numerics were already real (v0.2 was itself a big jump
from v0.1's Holland approximation). Example (`A_technical_investigative`,
top 5): `mechanical_engineer` (0.969) → `civil_engineer` (0.967) →
`software_developer` (0.888) → `electrician` (0.885) → `plumber` (0.840),
identical order and scores to within ±0.001 across the two versions.

**Work Style / Values Fit still print `low_differentiation`** in the
persona report. Traced and confirmed — this is **not** a v0.3 data defect:

1. **Test-fixture limit (user side):** `answer_all_items` applies one
   literal response per *scale*. A 2-item Work Style scale with one
   `reverse_scored` item always averages to the flat midpoint → user
   `stdev = 0` → the guarded cosine's user-side differentiation guard
   fires first. This is the M4.5 §10 finding, now also reached for Work
   Values because the career side finally has the data to get past the
   *first* (comparable-count) guard. A real user answering the actual
   assessment differentiates their answers.
2. **O*NET WI variance (career side):** even with a perfect user vector,
   the 4 MNP-mapped Work Style elements' `WI` values cluster tightly per
   occupation — measured career-side `stdev` ≈ 0.06–0.07 (threshold 0.10)
   for `accountant` / `sales_manager` / `electrician`. Work Values (3
   elements) is borderline: 0.03 (`accountant`) to 0.15 (`electrician`).

**The v0.3 data is present and correct** (coverage tests above); whether
the guarded cosine can *score* Work Style / Values Fit is a separate M5
methodology question (§7).

---

## 6. Crosswalk suggestion tool

`scripts/onet_import/suggest_crosswalk.py` → `data/crosswalks/onet_suggestions.csv`
(158 rows, 32 careers; top-5 O*NET-SOC candidates per career).

- **Method:** normalized-token match of the MNP career's English title
  against O*NET's primary + alternate (`Job Titles.txt`) + reported
  (`Sample of Reported Titles.txt`) title corpus (62 458 titles), with
  primary-title matches weighted 1.0 and alt/reported 0.5–0.55 (they are
  user-submitted and noisy), crude singular folding, Jaccard + sequence
  ratio.
- **Run against the 24-Alpha:** rank-1 suggestion **agrees** with the
  existing M3 hand crosswalk for **18 of 23** mapped careers — an
  independent cross-check that most of the hand crosswalk is sound. The 5
  "differs" are alternate-title collisions (e.g. `truck_driver` →
  "Industrial Truck and Tractor Operators", a plausible-but-wrong alt the
  hand crosswalk correctly avoided) — flagged for a curator, not applied.
- **Scaling to ~149:** the same tool, fed a larger MNP career list (code +
  English title + `CareerAlias` rows), produces the catalog-scale draft
  once that list exists. It never writes `CareerExternalMapping` — a human
  fills `reviewed_by` / `confidence` (Career KB doc §J).

---

## 7. Limitations & M5 recommendation

**CONDITIONAL GO for M5.** The career-side data is now genuinely
`CURRENT_OFFICIAL` and complete for RIASEC + Work Style across 23/23
mapped careers, Work Environment 22/23, Work Values 20/23 — a real,
reproducible upgrade over M4.5's 24-row hand fixture, with zero engine
changes and zero regressions.

Before building product UI on the Work Style / Values Fit outputs:

1. **Per-item user-answer control in the test fixtures** — `answer_all_items`
   needs an item-level override so persona reruns can produce a
   differentiated user Work Style / Values vector and actually exercise a
   SCORED result. (M4.5 §10/§15 already recommended this; still not done —
   deliberately out of a *data* pass.)
2. **Founder decision on the small-vector differentiation guard** — a
   3–4-element career vector with `stdev` ~0.07 failing a 0.10 threshold
   may be the guard being too blunt for short vectors, or a genuine signal
   that O*NET WI on 4 elements can't differentiate occupations. Needs a
   methodology call, not a code tweak.
3. **The 5 unsourced MNP Work Values keys** need a distinct sourcing plan
   (MNP curation) before Values Fit can honestly claim full coverage.
4. **`financial_analyst`** — consider re-crosswalking to a SOC with fuller
   O*NET coverage, or accept RIASEC+WorkStyle-only for it.

None of these block M5 work on **Interest Fit** + **Transition
Feasibility**, which have real, sufficient data.

---

## 8. Verification performed

- `python -m scripts.onet_import.download_onet` — both zips, sha256 logged.
- `python -m scripts.onet_import.build_onet_reference` — idempotent;
  1016 occupations, 18 081 scale values (`riasec` 5538, `work_context`
  5466, `work_style` 4455, `work_values` 2622); ranges verified vs
  `Scales Reference.txt`.
- `python -m scripts.onet_import.export_source_artifact` — 23 O*NET-SOC
  records, byte-stable (sorted keys, 4-dp floats).
- `python -m scripts.onet_import.suggest_crosswalk` — 158 rows, 18/23
  agree with the hand crosswalk.
- `pytest tests/test_career_kb_onet_production_import.py` — **18 passed**.
- `pytest tests/test_career_kb_*.py tests/test_matching_m45_hardened_data.py`
  — **54 passed** (no regression).
- Full regression — see the commit message / PR for the final count
  (target: prior baseline + 18, zero regressions).
- `git diff -- app/services/matching/` — **empty**.
- `alembic heads` — unchanged (`d5f9b3a71c84`).

---

*Source attribution: this document and the underlying data incorporate
information from the O\*NET Database (v31.0 + v30.2), used under the CC BY
4.0 license, U.S. Department of Labor / Employment and Training
Administration / National Center for O\*NET Development.*
