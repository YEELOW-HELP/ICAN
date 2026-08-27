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

## Layout

| Path | Document | Owns |
|---|---|---|
| `02_HUMAN_POTENTIAL_MODEL/MNP_HUMAN_POTENTIAL_MODEL_V0.1.md` | MNP-HPM v0.1 | the 12 canonical dimensions, their subdimensions, the Fact/Evidence/Claim/Interpretation/Recommendation layering, and the legacy→canonical claim mapping |
| `03_EVIDENCE_STANDARD/MNP_EVIDENCE_STANDARD_V0.1.md` | Evidence Standard v0.1 | evidence levels E0–E3, deterministic confidence inputs, LOW/MEDIUM/HIGH public semantics, contradiction rules |
| `04_CAREER_FIT_MODEL/MNP_CAREER_FIT_MODEL_V0.1.md` | Career Fit / Direction Evaluation Model v0.1 | the **four separate outputs** (Potential Fit, Goal Alignment, Transition Feasibility, Evidence Confidence), score components, profile↔career comparison rules, per-output aggregation, the hard-constraint gate, skill-state semantics, the 12-subtype constraint taxonomy |
| `04_CAREER_FIT_MODEL/MNP_RANKING_POLICY_V0.1.md` | Ranking Policy v0.1 | the **separate versioned decision layer**: eligibility, band gates, lexicographic ordering, pool sizes — never a composite score |
| `07_CONSULTANT_FEEDBACK/MNP_LEARNING_AND_FEEDBACK_PROTOCOL_V0.1.md` | Learning & Feedback Protocol v0.1 | consultant correction reason codes, append-only correction model, the controlled learning loop |
| `09_EVALUATIONS/MNP_EVALUATIONS_V0.1.md` | Evaluations v0.1 | the difference between engineering fixtures and authoritative Golden Cases, and how a Golden Case becomes authoritative |
| `MNP_FOUNDER_METHODOLOGY_CONTRACT_V0.1.md` | Founder Methodology Contract v0.1 | the binding Founder decisions (A–M) that these documents implement, and the hard limits on what engineering may decide |

## Provenance of v0.1 content

Every statement in these documents traces to Founder-approved source
material: the Stage 3B Founder task, the Founder "МОЖУ Methodology Lab"
brief, the Founder decisions memo (A–M), or structure already curated in
the repository (`docs/architecture/*`, `app/db/models_*`). Nothing here
introduces methodology beyond that. Where a decision was genuinely
undefined, the document says so explicitly and records the conservative
v0.1 default plus the open question — it does not guess.
