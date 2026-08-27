# MNP Assessment Gap Map v0.1

> **STATUS: Founder-approved methodology-operational document v0.1 —
> MVP EXPERIMENTAL BASELINE.**
> **NOT a validated psychometric instrument. Scoring/calibration EXPERIMENTAL.**
> **This document does NOT redesign Stage 1.** It records, per canonical
> MNP dimension, what evidence the current MVP assessment produces, how
> thin it is, and what a future Stage 1 v2 should add. Sequencing of any
> Stage 1 change is a separate decision (`MNP_METHODOLOGY_BACKLOG_V0.2.md`).

**What the MVP assessment collects today** (do not treat as exhaustive —
it is the Stage 1 Hybrid flow + optional CV): a few structured baseline
questions, a small set of open questions with adaptive follow-up
(`missing` / `low_confidence` / `contradiction` reasons), and CV text
extraction when a CV is uploaded. Stage 2 turns these into `Evidence` →
`ProfileClaim` rows across the legacy 11-value `ProfileDimension`, which
the Stage 3B adapter (`legacy-to-mnp:v0.1`) maps onto the 12 canonical
dimensions.

**Coverage legend:** `None` = no evidence source at all ·
`Low` = one weak/self-report source, most subdimensions untouched ·
`Medium` = usable for a first pass, known blind spots ·
`High` = solid for MVP (none of the 12 are High in v0.1).

---

## 1. Per-dimension map

| # | Dimension | Current likely evidence sources | Expected MVP coverage | Known weakness | Stage 1 v2 improvement | Improvement type |
|---|---|---|---|---|---|---|
| 1 | **Interests** | open answers (interests / desired-direction), some structured items → legacy `interest` | **Medium** | self-report only; social-desirability bias; no behavioural probing; unstructured (no interest-area coverage guarantee) | add "tell me about a time you enjoyed / lost track of time doing X" prompts; a short structured interest-area checklist | structured question + behavioral interview |
| 2 | **Strengths** | open answers; CV achievements; `derived` → legacy `strength` | **Low–Medium** | conflated with Skills and Interests; no structured strength taxonomy; often just a restated interest | "what do people come to you for?" + one concrete example per claimed strength | structured question + behavioral interview |
| 3 | **Skills** | CV extraction (strongest); structured skill items; open answers → legacy `skill` | **Medium** with CV / **Low** without | profile skill terms and `CareerSkill` terms are different taxonomies (only exact-key matches); no proficiency level; `CONFIRMED_MISSING` needs an explicit negative the assessment rarely elicits | structured skill checklist with self-rated level, aligned to the `skills` taxonomy; an explicit "skills you do NOT have / want to avoid" item | structured question + CV extraction |
| 4 | **Abilities & Learning Potential** | **none** (no legacy `ProfileDimension` source — HPM §4.3) | **None** | entirely uncovered; `tf_abilities_learning` is always `INSUFFICIENT_DATA`; Transition Feasibility is structurally thin because of this | learning-history questions ("what did you teach yourself recently, and how fast?"); optionally a light external aptitude module | structured question + behavioral interview + external assessment (optional) |
| 5 | **Work Style** | structured `work_preference:structured_environment`; some `trait` → legacy | **Low** | only 1 of the 10 v0.1 Work Style subdimensions is elicited (structure_preference); autonomy / pace / ambiguity_tolerance / leadership / decision_responsibility / initiative / routine_tolerance / collaboration / customer_interaction are untouched; `pf_work_style` also blocked on the KB side | a dedicated Work Style block covering all 10 subdimensions | structured question (+ KB enrichment — backlog) |
| 6 | **Work Environment** | structured `work_preference:remote_work` / `team_environment`; open answers → legacy | **Low–Medium** | only `setting` and `collaboration_context` facets map; physical / customer-interaction / schedule facets thin; `pf_work_environment` matching is keyword-based and crude | a structured environment-preference block mirroring `CareerWorkContext` fields 1:1 | structured question |
| 7 | **Values** | open answers; structured value items (`autonomy` / `stability` / `impact`) → legacy `value` | **Low–Medium** | no forced-choice / trade-off elicitation (values are only meaningful relative to each other); no "relevant to THIS decision" marker → `ga_decision_relevant_values` is always `INSUFFICIENT_DATA`; no career-side values data in the KB | values card-sort / forced-ranking; a "which of these matters MOST for this specific career decision?" item | structured question (trade-off format) |
| 8 | **Motivation** | open answers (desired outcomes); some structured → legacy `motivation` | **Low** | conflated with Goals and Values; `ga_motivation` is always `INSUFFICIENT_DATA` (no career-side counterpart) | motivation prompts distinct from goals; "what got you to actually act on a change last time?" | structured question + behavioral interview |
| 9 | **Experience** | CV extraction (strongest); open answers; `current_status` → legacy `experience` | **Medium** with CV / **Low** without | no structured `Experience` entity (folded into claims); no role→skill leverage mapping; `pf_experience_relevance` is always `INSUFFICIENT_DATA` | structured work-history capture (role, duration, domain, key responsibilities); richer CV parsing into structured experience records | CV extraction + structured question |
| 10 | **Goals** | open answers (desired direction); structured goal items (`career_change` / `skill_development` / `stability_seeking`) → legacy `goal` | **Low–Medium** | goals are often vague ("something in IT"); no timeframe / horizon; `ga_goals` is `INSUFFICIENT_DATA` (no structured career goal-target data) | structured goal prompts (direction of change, horizon, non-negotiables); consultant clarification for vague goals | structured question + consultant clarification |
| 11 | **Constraints** | open answers; structured `location` / `schedule` / `income` items; `contextual_factor:family_responsibilities`; CV (location) → legacy `constraint` | **Medium** (soft) / **Low** (hard + confirmed) | the taxonomy has 12 subtypes; the assessment probes ~4; no explicit "is this a hard limit or a preference?" elicitation, so v0.1 marks everything soft and the hard gate is inert in production; `time` / `financial` subtypes barely probed | an explicit constraint block covering all 12 subtypes, each with a hard/soft + confirmed follow-up | structured question + consultant clarification (hardness confirmation) |
| 12 | **Career Adaptability / Agency** | `trait:adaptability` only → legacy | **Low** | a single term; no agency / proactivity signal; `tf_career_adaptability` is always `INSUFFICIENT_DATA` | a short adaptability/agency block ("last time you changed direction, what did you actually do?"); optionally a light validated adaptability scale | structured question + behavioral interview + external assessment (optional) |

---

## 2. Summary — what the pilot can and cannot lean on

**Usable for a first pass (Medium):** Interests, Skills *(with CV)*,
Experience *(with CV)*, Work Environment, Constraints *(soft only)*.

**Thin — expect frequent `INSUFFICIENT_DATA` / `NEED_MORE_EVIDENCE`:**
Work Style, Motivation, Values *(trade-offs)*, Goals *(specificity)*,
Career Adaptability.

**Not covered at all:** Abilities & Learning Potential (`None`) → this is
the single biggest reason **Transition Feasibility will have low coverage
in most pilot cases**, which the Founder has explicitly accepted as an MVP
condition.

**Direct consequences already visible in the code:**
- Goal Alignment is entirely `INSUFFICIENT_DATA` in legacy v0.1 (no
  decision-relevance marker on Values; no structured career goal-targets).
- Of the 12+ score components, only 4 can produce a `SCORED` result on
  current data (`pf_interests`, `pf_skills_match`, `pf_work_environment`,
  `tf_skill_gap`).
- The hard-constraint gate issues zero blocks on current KB + assessment
  data (no confirmed hard constraints on the user side, no `HARD_FACTUAL`
  requirements on the career side).

None of this is a bug — it is the honest coverage of the MVP baseline.
The `NEED_MORE_EVIDENCE` / `NEED_MORE_DATA` review actions and the
`ClarificationRequest` mechanism exist precisely so the system says "we
don't know" instead of guessing.

---

## 3. Cross-references

- Improvement priorities and triggers: `MNP_METHODOLOGY_BACKLOG_V0.2.md`.
- What "coverage" feeds: Evidence Confidence (`MNP_EVIDENCE_STANDARD_V0.1.md`
  §2.2) and the RankingPolicy coverage warnings
  (`MNP_RANKING_POLICY_V0.1.md` §2.2).
- How a consultant records a coverage gap: `NEED_MORE_EVIDENCE` /
  `NEED_MORE_DATA` in `MNP_CONSULTANT_REVIEW_STANDARD_V0.1.md`.
