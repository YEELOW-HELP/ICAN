# МОЖУ Methodology Lab

Closed methodology contour for «МОЖУ: Мій Напрям». Production code consumes
only **Founder-approved, versioned** methodology from here — it is never
free to invent dimensions, weights, or psychometric scoring on its own.

## STATUS (all v0.1 documents in this directory)

> **Founder-approved engineering methodology contract v0.1.**
> **NOT a validated psychometric instrument.**
> **Scoring / calibration remains EXPERIMENTAL until evaluated.**

v0.1 is the minimum shared standard needed to build Stage 3B (Direction
Intelligence) safely. It fixes vocabulary, layering, and rules. It does
**not** claim scientific validity, and every numeric weight/threshold it
implies is explicitly experimental and lives in versioned configuration
(`app/services/direction/config.py`), not in this canon.

## Matching V1 (2026-08-28 Founder product pivot)

`docs/product/20_MATCHING_V1_FOUNDER_DEFINITION.md` is the latest binding
Founder product contract. It introduces a new BASIC V1 deterministic core
(Structured Golden Test → deterministic profile → deterministic career
matching → self-serve Career Dashboard) that **coexists** with, rather than
replaces, the canon below. Old DirectionRuns and the PRO Hybrid-Assessment
track keep their historical semantics unchanged; nothing in the Canon table
is rewritten. See `docs/engineering/21_MATCHING_V1_RECONCILIATION_AND_IMPLEMENTATION_PLAN.md`
for the full KEEP/SUPERSEDE/PRO-ONLY/NEW/DEFER reconciliation.

| Path | Document | Owns |
|---|---|---|
| `05_GOLDEN_TEST/MNP_GOLDEN_TEST_V0.1.md` | Golden Test v0.1 *(hardened 2026-08-28)* | the structured assessment (scales, item counts, scoring, missing-answer handling) and the deterministic matching mathematics (Interest/Work Style/Values Fit, Feasibility, Coverage) for BASIC V1 |
| `05_GOLDEN_TEST/MNP_SCALE_TO_ONET_MAPPING_V0.1.md` | Scale ↔ O*NET Mapping v0.1 | per-scale MNP↔O*NET compatibility (DIRECT/DERIVED/PROXY/MNP_ONLY), verified against the current (2024-redesigned) O*NET Work Styles taxonomy, plus the Career Vector Compatibility Proof for each Fit family |
| `05_GOLDEN_TEST/MNP_MATCHING_METRIC_BENCHMARK_V0.1.md` | Matching Metric Benchmark v0.1 | 11 computed cosine-vs-Euclidean similarity cases, the guarded-cosine recommendation, and the band-cutoff sensitivity analysis |
| `05_GOLDEN_TEST/MNP_BASIC_SHORT_FORM_STRATEGY_V0.1.md` | BASIC Short-Form Strategy v0.1 | full item bank vs. the ~75-item BASIC short form, minimum items/scale, reverse-item policy, insufficient-data rule |
| `06_CAREER_KB/MNP_CAREER_KB_V1.md` | Career KB V1 *(hardened 2026-08-28)* | the three-layer source model (Work.ua / O*NET / MNP curation), `CareerExternalMapping` crosswalk schema, `CareerMatchingProfile` vector schema, provenance/versioning rules |
| `06_CAREER_KB/MNP_WORKUA_DATA_USE_DECISION_V0.1.md` | Work.ua Data Use Decision v0.1 | the licensing/data-use gate — what may be referenced, stored, displayed, or requires an agreement, before any automated Work.ua import |

Three existing Canon documents below carry a **"AMENDED BY MATCHING V1
FOUNDER DEFINITION"** pointer banner (light-touch, not rewritten): MNP-HPM
v0.1 (Work Values gains new subdimensions), Career Fit Model v0.1 (four-output
model superseded for BASIC, retained for historical/PRO), Ranking Policy v0.1
(lexicographic principle reused over the new outputs).

## Layout

### Canon (frozen as `MNP-HPM / Direction Evaluation v0.1` — MVP EXPERIMENTAL BASELINE)

| Path | Document | Owns |
|---|---|---|
| `MNP_FOUNDER_METHODOLOGY_CONTRACT_V0.1.md` | Founder Methodology Contract v0.1 | the binding Founder decisions (A–M + Wave A N–Q + §2B) and the hard limits on what engineering may decide |
| `02_HUMAN_POTENTIAL_MODEL/MNP_HUMAN_POTENTIAL_MODEL_V0.1.md` | MNP-HPM v0.1 *(amended — see Matching V1 above)* | the 12 canonical dimensions, their subdimensions, the Fact/Evidence/Claim/Interpretation/Recommendation layering, the legacy→canonical claim mapping |
| `03_EVIDENCE_STANDARD/MNP_EVIDENCE_STANDARD_V0.1.md` | Evidence Standard v0.1 | evidence levels E0–E3, deterministic confidence inputs, LOW/MEDIUM/HIGH public semantics, contradiction rules |
| `04_CAREER_FIT_MODEL/MNP_CAREER_FIT_MODEL_V0.1.md` | Career Fit / Direction Evaluation Model v0.1 *(amended — see Matching V1 above)* | the **four separate outputs**, score components, profile↔career comparison rules, per-output aggregation, the hard-constraint gate, skill-state semantics, the 12-subtype constraint taxonomy |
| `04_CAREER_FIT_MODEL/MNP_RANKING_POLICY_V0.1.md` | Ranking Policy v0.1 *(amended — see Matching V1 above)* | the **separate versioned decision layer**: eligibility, band gates, lexicographic ordering, pool sizes — never a composite score |
| `07_CONSULTANT_FEEDBACK/MNP_LEARNING_AND_FEEDBACK_PROTOCOL_V0.1.md` | Learning & Feedback Protocol v0.1 | consultant correction reason codes, append-only correction model, the controlled learning loop |
| `09_EVALUATIONS/MNP_EVALUATIONS_V0.1.md` | Evaluations v0.1 | engineering fixtures vs authoritative Golden Cases, and how a Golden Case earns authority |

### Operational (MVP validation phase — how the pilot is run and measured)

| Path | Document | Owns |
|---|---|---|
| `07_CONSULTANT_FEEDBACK/MNP_CONSULTANT_REVIEW_STANDARD_V0.1.md` | Consultant Review Standard v0.1 | exactly how a consultant reviews A–H, the structured actions (`ACCEPT`/`EDIT`/`REJECT`/`NEED_MORE_EVIDENCE`; `ACCEPT_MAIN`/`ACCEPT_ALTERNATIVE`/`MOVE`/`REJECT`/`NEED_MORE_DATA`), and the correction→reason-code map |
| `09_EVALUATIONS/MNP_GOLDEN_CASE_PROTOCOL_V0.1.md` | Golden Case Protocol v0.1 | the authoritative-Golden-Case template + the reviewer-1 / reviewer-2 / consensus / Methodology-Owner lifecycle |
| `09_EVALUATIONS/MNP_PILOT_EVALUATION_PROTOCOL_V0.1.md` | Pilot Evaluation Protocol v0.1 | the 10 system metrics + 3 client metrics, each with numerator/denominator, data source, and MVP alarm threshold |
| `02_HUMAN_POTENTIAL_MODEL/MNP_ASSESSMENT_GAP_MAP_V0.1.md` | Assessment Gap Map v0.1 | per-dimension evidence sources, MVP coverage, known weakness, and the Stage 1 v2 improvement (does **not** redesign Stage 1) |
| `MNP_METHODOLOGY_BACKLOG_V0.2.md` | Methodology Backlog v0.2 | the prioritized P0–P3 backlog for `v0.2+` |
| `MNP_TECH_DEBT_RECOMMENDATION_V0.1.md` | Tech Debt Recommendation v0.1 | the Methodology-track recommendation on Register Items 11 and 16 (input to the register owner; does not edit the register) |

## Provenance of v0.1 content

Every statement in these documents traces to Founder-approved source
material: the Stage 3B Founder task, the Founder "МОЖУ Methodology Lab"
brief, the Founder decisions memo (A–M), or structure already curated in
the repository (`docs/architecture/*`, `app/db/models_*`). Nothing here
introduces methodology beyond that. Where a decision was genuinely
undefined, the document says so explicitly and records the conservative
v0.1 default plus the open question — it does not guess.
