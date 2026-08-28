# MNP Scale ↔ O*NET Mapping V0.1

**Status:** PROVISIONAL v0.1 — hardening deliverable requested in Founder Review "Matching V1 M0" (2026-08-28). Supersedes the unqualified O*NET-alignment notes in `MNP_GOLDEN_TEST_V0.1.md` §9–12 with an explicit, per-scale, source-verified mapping. No code changed.

**Research basis (verified against live O*NET Resource Center sources, not assumed from prior training data):**
- HumRRO / National Center for O*NET Development, *"Revisiting the Work Styles Domain of the O\*NET Content Model"* (2024 No. 090, onetcenter.org/dl_files/Work_Styles_New.pdf) — confirms Work Styles underwent a genuine structural redesign: **16 lower-order / 6 higher-order → 21 lower-order / 7 higher-order dimensions**, integrated into production starting **O\*NET 30.1** (research-dataset element IDs aligned to O\*NET 30.3 as of May 2026).
- O\*NET 30.2/30.3 Data Dictionary, Appendix 4 (Content Updates Since Release 4.0).
- O\*NET Work Values domain (Theory of Work Adjustment-derived, 6 constructs: Achievement, Independence, Recognition, Relationships, Support, Working Conditions) — confirmed unchanged in *structure* through the 30.x line; only occupation-level *data* (83 occupations) was updated in Version 30.

**Critical finding that changes M0's working assumption:** `Independence` was **dropped from Work Styles** in the 2024 redesign specifically *because* "it more clearly falls within the Work Values domain" (it is one of O\*NET's own 6 Work Values). `Analytical Thinking` was dropped as more cognitive/Skills-domain in nature. This independently confirms the M0 design decision to place `independence_value` under MNP Work **Values**, not Work **Style** — but it also means the current O\*NET Work Style taxonomy no longer contains any behavioral-autonomy-preference construct at all, which matters for the `autonomy` row below.

RIASEC is confirmed **stable and unrevised** as O\*NET's top-level Interests scale (a newer "Basic Interests" 41-facet layer exists underneath as of O\*NET ~26–27, but the 6-letter occupational profile is unchanged) — the Golden Test's decision to keep RIASEC as the classical anchor stands, unconditionally.

---

## Mapping table format

`MNP scale → MNP definition → user questionnaire construct → O*NET element ID/name → O*NET source dataset/version → O*NET scale → normalization/transformation → compatibility status → rationale`

Compatibility statuses: **DIRECT** (same construct, same or trivially convertible scale) / **DERIVED** (MNP scale is a documented composite of ≥2 O*NET elements, or vice versa) / **PROXY** (conceptually related but measuring a meaningfully different construct — used only as a fallback, never presented as equivalent) / **MNP_ONLY** (no O*NET counterpart exists; MNP-original, requires its own validation path).

---

## A. RIASEC (Interests)

| MNP scale | Definition | Item construct | O*NET element | Source/version | O*NET scale | Transform | Status | Rationale |
|---|---|---|---|---|---|---|---|---|
| R (Realistic) | Prefers hands-on, mechanical, physical work | 5-item Likert | `Interests — Realistic` | O*NET Interest Profiler, O*NET 30.x | 1–7 Occupational Interest rating | `(x-1)/6` → [0,1] | **DIRECT** | Identical construct, identical letter, unrevised in O*NET. |
| I (Investigative) | Prefers analytical, scientific inquiry | 5-item Likert | `Interests — Investigative` | same | 1–7 | same | **DIRECT** | — |
| A (Artistic) | Prefers creative, expressive work | 5-item Likert | `Interests — Artistic` | same | 1–7 | same | **DIRECT** | — |
| S (Social) | Prefers helping, teaching, caregiving work | 5-item Likert | `Interests — Social` | same | 1–7 | same | **DIRECT** | — |
| E (Enterprising) | Prefers persuading, leading, selling | 5-item Likert | `Interests — Enterprising` | same | 1–7 | same | **DIRECT** | — |
| C (Conventional) | Prefers structured, data/detail work | 5-item Likert | `Interests — Conventional` | same | 1–7 | same | **DIRECT** | — |

All six: **DIRECT**, unconditionally. No hardening required.

---

## B. Work Style (MNP HPM v0.1 §3.1, 10 keys)

Reconciled against the **new** 21-element/7-factor O*NET Work Style taxonomy (§ above), not the retired 16-element version.

| MNP scale | Definition | Item construct | O*NET element(s) | Source/version | O*NET scale | Transform | Status | Rationale |
|---|---|---|---|---|---|---|---|---|
| `autonomy` | Prefers self-directed work, minimal supervision | Likert | *(none — see below)* | — | — | — | **MNP_ONLY** | O\*NET's only behavioral-autonomy Work Style (`Independence`) was **removed** in the 2024 redesign and reclassified as a Work Value, not a Work Style (confirmed by the HumRRO report). Current O\*NET has no Work-Style-level autonomy construct. MNP retains `autonomy` as a legitimate MNP-original behavioral-preference construct, kept deliberately distinct from the Values-side `independence_value` (§C) — the two measure different things (behavioral preference vs. valued outcome) even though O*NET now houses only the latter. |
| `structure_preference` | Prefers structured vs. open-ended work | Likert | `Structured Work` / `Unstructured Work` | O*NET Work **Context** (not Work Style), 30.x | Context frequency/importance rating | Reverse-scale union of the two split Work Context items | **DERIVED** (cross-domain) | O*NET measures this construct at the job/Work-Context level, not the person/Work-Style level — a genuine domain mismatch, not a naming coincidence. Usable as a career-side signal via crosswalk, but is not psychometrically equivalent to a person-side personality-trait rating. |
| `ambiguity_tolerance` | Comfortable with uncertainty/ambiguity | Likert | `Tolerance for Ambiguity` | O*NET Work Style, new taxonomy (Openness) | Occupational importance rating (post-30.1) | Direct rescale | **DIRECT** | Newly added in the 2024 redesign under exactly this name — a strong, current, direct match. |
| `pace` | Prefers fast vs. steady work pace | Likert | *(none directly)* — related: `Stress Tolerance` (Work Style), `Time Pressure` / `Pace Determined by Speed of Equipment` (Work Context) | O*NET, 30.x | mixed | Composite proxy | **PROXY** | No O*NET Work Style directly measures pace preference; Stress Tolerance and the named Work Contexts are correlated but distinct constructs (coping-under-pressure vs. preferring speed). |
| `collaboration` | Prefers working with others vs. alone | Likert | `Social Orientation` (Extraversion) + `Cooperation` (Agreeableness) | O*NET Work Style, new taxonomy | Importance rating | Mean of the two components | **DERIVED** | MNP's single collaboration construct spans two now-separate O*NET higher-order factors; a documented composite, not a 1:1 match. |
| `leadership` | Prefers leading/directing others | Likert | `Leadership Orientation` | O*NET Work Style, new taxonomy (Extraversion) | Importance rating | Direct rescale | **DIRECT** | Renamed from plain "Leadership" in the redesign but same construct, confirmed by definition text. |
| `customer_interaction` | Prefers direct customer/public contact | Likert | *(none as Work Style)* — `Deal With External Customers`, `Performing for or Working Directly with the Public` (Work Context / GWA) | O*NET, 30.x | mixed | Cross-domain proxy | **PROXY** | Person-side preference has no O*NET Work Style counterpart; only job-side context/activity descriptors exist. |
| `decision_responsibility` | Prefers bearing decision consequences | Likert | *(none as Work Style)* — `Freedom to Make Decisions`, `Responsibility for Outcomes and Results`, `Impact of Decisions on Co-workers or Company Results` (Work Context) | O*NET, 30.x | mixed | Cross-domain proxy | **PROXY** | Same domain mismatch as above — a job characteristic, not a rated personality trait, in O*NET's model. |
| `routine_tolerance` | Tolerates repetitive/routine work | Likert (reverse-scored item, §5 of Golden Test doc) | inverse of `Importance of Repeating Same Tasks` (Work Context); partially related to `Adaptability` (Work Style, Openness) | O*NET, 30.x | mixed | Reverse + composite proxy | **PROXY** | No direct Work Style; a job-context descriptor and a loosely-related trait, combined only as an approximation. |
| `initiative` | Proactively takes on responsibility | Likert | `Initiative` | O*NET Work Style, new taxonomy ("Compound Dimensions" — spans Conscientiousness/Agreeableness/Extraversion per the HumRRO report) | Importance rating | Direct rescale | **DIRECT** | Exact name and definition match survives the redesign unchanged in substance. |

**Summary:** of 10 MNP Work Style keys, **3 are DIRECT** (ambiguity_tolerance, leadership, initiative), **2 are DERIVED** (structure_preference, collaboration), **4 are PROXY** (pace, customer_interaction, decision_responsibility, routine_tolerance), **1 is MNP_ONLY** (autonomy). This is a materially different — and more honest — picture than M0's original assumption that the whole vector "reuses HPM v0.1 unchanged and aligns with O*NET." Only just over half the vector has a psychometrically direct O*NET counterpart; the rest are either cross-domain crosswalks (job-context data standing in for a personality-trait rating) or MNP-original.

---

## C. Work Values (MNP, new 8-key set defined in Golden Test doc §11)

O*NET's Work Values model: 6 constructs (Achievement, Independence, Recognition, Relationships, Support, Working Conditions), structurally unchanged through 30.x (only occupation-level data was updated in V30).

| MNP scale | Definition | O*NET element | Source/version | O*NET scale | Transform | Status | Rationale |
|---|---|---|---|---|---|---|---|
| `income` | Values high/stable pay | *(none direct)* — partially inside `Working Conditions` | O*NET Work Values, 30.x | 1–7 importance | Composite proxy | **PROXY** | O*NET's Working Conditions value bundles compensation with physical conditions and security; MNP splits income out as its own scale — not a clean subset. |
| `stability` | Values job security | partially `Support` | O*NET Work Values, 30.x | 1–7 | Composite proxy | **PROXY** | Support in O*NET's model centers on supervisory backing, not job security specifically. |
| `growth` | Values advancement/promotion opportunity | *(none)* | — | — | — | **MNP_ONLY** | Not represented in O*NET's coarser 6-value model. |
| `independence_value` | Values autonomy/self-direction as an outcome | `Independence` | O*NET Work Values, 30.x (and now doubly confirmed as the correct domain by the 2024 Work Styles redesign, §B above) | 1–7 importance | Direct rescale | **DIRECT** | Strongest, most confidently-verified mapping in this whole document. |
| `impact_helping` | Values helping others/contributing | `Relationships` | O*NET Work Values, 30.x | 1–7 | Direct rescale | **DIRECT** | O*NET's Relationships value explicitly covers co-worker harmony and service to others. |
| `recognition_status` | Values recognition/advancement status | `Recognition` | O*NET Work Values, 30.x | 1–7 | Direct rescale | **DIRECT** | Name and construct match. |
| `work_life_balance` | Values time/boundaries outside work | *(none)* | — | — | — | **MNP_ONLY** | Not represented in O*NET's 6-value model at all. |
| `learning` | Values ongoing skill/knowledge acquisition | *(none)* | — | — | — | **MNP_ONLY** | Not represented; closest analogue is the Work Style `Intellectual Curiosity`, a different domain (behavior, not value). |

**Summary:** 3 DIRECT (independence_value, impact_helping, recognition_status), 2 PROXY (income, stability), 3 MNP_ONLY (growth, work_life_balance, learning). The Values vector is honestly a **hybrid** instrument, not primarily O*NET-derived — this must be stated plainly rather than implied otherwise.

---

## D. Work Environment (MNP HPM v0.1 §3.2, 5 keys)

O*NET's nearest domain is **Work Context** (57–61 items depending on version, non-task job-environment descriptors).

| MNP scale | Definition | O*NET element(s) | Status | Rationale |
|---|---|---|---|---|
| `setting` | Office/remote/field preference | `Indoors, Environmentally Controlled` / `Outdoors, Exposed to Weather` / `In an Open or Enclosed Vehicle` (Work Context) | **DERIVED** | Composite of several Work Context items; job-side descriptors used as a person-preference proxy. |
| `collaboration_context` | Team vs. solo environment preference | `Work With Work Group or Team` (Work Context) | **DIRECT** (cross-domain) | Closest 1:1 match available, though still a job descriptor, not a personality rating. |
| `schedule_predictability` | Fixed vs. variable schedule preference | `Work Schedule – Regular/Irregular/Seasonal` (Work Context) | **DIRECT** (cross-domain) | Same caveat as above. |
| `physical_environment` | Physical demands tolerance | `Spend Time Standing/Walking/Kneeling`, hazard-exposure items (Work Context) | **DERIVED** | Composite of multiple physical-demand Work Context items. |
| `customer_interaction_context` | Public/customer-facing environment | `Deal With External Customers` (Work Context) | **DIRECT** (cross-domain) | Same caveat — job descriptor, not trait. |

All five Work Environment keys map to O*NET **Work Context** (job-side data), never to a person-side psychometric rating — this is a structurally correct crosswalk (Work Environment was always meant to describe the job/environment, not the person), unlike several Work Style rows above where the domain mismatch is a genuine limitation.

---

## Founder Decision Table (per required format)

| Family | User construct | Career construct | Compatibility | Recommended V1 status |
|---|---|---|---|---|
| **RIASEC** | Self-rated interest pattern across 6 Holland categories | O*NET occupational Interest Profiler score, same 6 categories | 6/6 DIRECT | **READY** |
| **Work Style** | Self-rated behavioral/personality work preferences (10 MNP keys) | O*NET Work Style importance ratings (new 21-element taxonomy) + Work Context (job descriptors) as fallback | 3 DIRECT / 2 DERIVED / 4 PROXY / 1 MNP_ONLY | **PROVISIONAL** — usable in V1 with the per-key status visibly carried into `CareerExternalMapping` confidence, never presented as uniformly as reliable as RIASEC |
| **Work Values** | Self-rated importance of 8 work outcomes | O*NET's 6-construct Work Values model | 3 DIRECT / 2 PROXY / 3 MNP_ONLY | **PROVISIONAL** — same treatment; the 3 MNP_ONLY scales (growth, work_life_balance, learning) explicitly lack any O*NET-anchored career-side data source and need a distinct sourcing plan (MNP curation judgment, not O*NET import) before they can honestly drive matching |
| **Work Environment** | Self-rated environment preferences (5 MNP keys) | O*NET Work Context (job-side descriptors) | 2 DIRECT(cross-domain) / 3 DERIVED | **READY** — structurally correct crosswalk (environment is inherently job-side data), lower risk than Work Style/Values |

**No family is DO_NOT_USE.** Per Founder instruction, Matching V1 must work even if a family were disqualified; since none is, no fallback removal is required for M1 — but the **PROVISIONAL** flag on Work Style and Work Values must propagate into the Compatibility Report as a visible caveat ("this dimension's psychometric grounding is partly MNP-original, not fully validated against an external instrument") rather than being silently smoothed over.

---

## Career Vector Compatibility Proof (per Founder Review "VERY IMPORTANT" requirement)

For each Fit family: what the user side measures, what the career side measures, how they're converted to a common representation, and whether high-high actually means compatibility. A family only participates in Matching V1 after this proof; where the proof is weak, the family is marked PROVISIONAL/MNP_ONLY rather than a transformation being invented to paper over the gap.

### Interest Fit (RIASEC)
- **USER SIDE:** self-reported preference for 6 categories of work activity (Realistic/Investigative/Artistic/Social/Enterprising/Conventional), via 3–5 Likert items/letter.
- **CAREER SIDE:** O*NET's own Occupational Interest Profiler score per letter — a job-analytic rating of how much each RIASEC theme characterizes the occupation, on the same conceptual 6-letter model.
- **TRANSFORMATION:** both sides rescaled independently to `[0,1]` (user: `(mean-1)/4` off a 5-point scale; career: O*NET's native 1–7 scale rescaled `(x-1)/6`), then compared via guarded cosine (§17 of Golden Test doc).
- **SEMANTICS:** high-high genuinely means compatibility here — both sides measure literally the same construct (Holland's RIASEC theory), one from the person's own report, one from occupational analysts' independent rating of the job. This is the strongest, most literal compatibility proof of the four families.
- **Verdict: READY.**

### Work Style Fit
- **USER SIDE:** self-reported behavioral/personality work preferences across 10 MNP-defined subdimensions.
- **CAREER SIDE:** a mix of (a) O*NET Work Style importance ratings for the 3 DIRECT-mapped keys (genuinely the same construct, analyst-rated), and (b) O*NET Work Context data for the 4 PROXY keys (a *job characteristic* — e.g. "how often does this job involve external customers" — standing in for a *person preference* — "does this person like customer contact"), and (c) no career-side source at all for the 1 MNP_ONLY key (`autonomy`), where the career side would need MNP curation judgment, not automated import.
- **TRANSFORMATION:** DIRECT/DERIVED keys rescale as importance ratings on O*NET's native scale → `[0,1]`; PROXY keys have **no principled transformation** from "job requires X" to "person prefers X" — a job that heavily involves customer contact does not thereby mean people who like customer contact are compatible with it in the same sense; it only means the job *offers the opportunity* for that preference to be exercised (this is precisely O*NET's own Trait Activation Theory framing, confirmed in the HumRRO 2024 report — relevance, not equivalence).
- **SEMANTICS:** high-high compatibility holds cleanly only for the 3 DIRECT keys. For the 4 PROXY keys, "high user preference" × "high job-context frequency" is a *plausible* but not *proven* compatibility signal — it says the job offers the opportunity, not that a high-preference person will necessarily be more satisfied or effective there. For `autonomy` (MNP_ONLY), there is currently no career-side data source at all.
- **Verdict: PROVISIONAL.** Used in V1 (the alternative — dropping 5 of 10 keys — would gut the vector), but every PROXY/MNP_ONLY component must carry a visible provenance flag in the Compatibility Report, never presented with the same confidence as the 3 DIRECT keys or the RIASEC family.

### Values Fit
- **USER SIDE:** self-reported importance of 8 work-related outcomes.
- **CAREER SIDE:** O*NET Work Values importance ratings for the 3 DIRECT keys; no principled career-side source for the 2 PROXY keys (`income`, `stability` — O*NET's coarser Working Conditions/Support constructs are not a clean subset) or the 3 MNP_ONLY keys (`growth`, `work_life_balance`, `learning`).
- **TRANSFORMATION:** same rescale-and-cosine approach as Work Style; for MNP_ONLY keys there is literally no O*NET transformation to define — any career-side value for these 3 keys must come from MNP curation, not import, and must be labeled as such.
- **SEMANTICS:** high-high holds for the 3 DIRECT keys (Independence/Recognition/Relationships — genuinely the same construct on both sides, per the Theory of Work Adjustment lineage both instruments share). For the other 5, semantics are unproven or entirely absent on the career side.
- **Verdict: PROVISIONAL**, with the 3 MNP_ONLY keys flagged as requiring a distinct, non-O*NET-import sourcing plan before they can honestly drive live matching (not resolved by this document — a tracked M3 dependency).

### Transition Feasibility
- **USER SIDE:** structured facts (education, language, geography/mobility, schedule, credentials, financial/time capacity for retraining).
- **CAREER SIDE:** existing Stage 3A `CareerRequirement`/`CareerWorkContext` structured facts (typical entry education, licensing requirements, work format) — not vector-based at all.
- **TRANSFORMATION:** gate-then-score (Golden Test doc §20–22), a direct structured-fact comparison, not a vector-similarity metric — no O*NET psychometric layer is involved in Feasibility at all.
- **SEMANTICS:** unambiguous — a documented education/license/geography mismatch either blocks or soft-penalizes deterministically; no cosine/Euclidean ambiguity applies to this family.
- **Verdict: READY** — already the most solid family, since it was never dependent on O*NET vector data to begin with.

---

## Required hardening actions on other M0 documents (tracked here, applied there)

1. `MNP_GOLDEN_TEST_V0.1.md` §10–11 must stop implying uniform O*NET alignment for Work Style/Work Values and point here instead.
2. `MNP_CAREER_KB_V1.md` §C (O*NET mapping) must cite **O*NET 30.1+** and the new 21-element Work Style taxonomy explicitly, not a generic/unversioned reference.
3. Any future O*NET data import (M3) must import the **current** `Work Style Names and Descriptions for O*NET Content Model Reference` file (the new 21-element structure), not the retired 16-element one — a real implementation risk this research surfaced, since most public tutorials/older integrations still reference the old taxonomy.
