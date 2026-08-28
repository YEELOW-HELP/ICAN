# MNP Golden Test V0.1 — Deterministic Assessment & Matching Mathematics

**Status:** PROVISIONAL v0.1 — engineering/methodology specification, pending Founder sign-off and Golden Case calibration.

> **HARDENED (2026-08-28) per Founder Review "Matching V1 M0":** the ~94-item count, the unconditional cosine-similarity recommendation, the hardcoded 29-scale Coverage denominator, and the assumed O*NET alignment of Work Style/Work Values have all been superseded or qualified by three new companion documents produced from actual research and computation, not assumption:
> - `MNP_SCALE_TO_ONET_MAPPING_V0.1.md` — verified against the **current** O*NET Work Styles taxonomy (21 elements/7 factors, redesigned 2024, live in O*NET 30.1+ — the old 16-element taxonomy this document originally assumed is retired).
> - `MNP_MATCHING_METRIC_BENCHMARK_V0.1.md` — actual cosine-vs-Euclidean calculations on 11 cases; cosine is retained only in a **guarded** form (§17–19 below, revised).
> - `MNP_BASIC_SHORT_FORM_STRATEGY_V0.1.md` — the 94-item bank is a research/planning estimate; BASIC V1 targets a ~75-item short form.
> Sections below are annotated `[HARDENED]` where they were revised as a result.
**Supersedes for BASIC V1:** the free-text/claims-based scoring path used by Stage 3B (`MNP_CAREER_FIT_MODEL_V0.1.md`, `MNP_RANKING_POLICY_V0.1.md`) — those documents remain the historical/PRO reference (see amendment banners added to each), and are not rewritten.
**Depends on:** `MNP_HUMAN_POTENTIAL_MODEL_V0.1.md` (canonical dimensions, Work Style subdimensions §3.1, Work Environment facets §3.2, Constraints taxonomy §3.3), `docs/product/20_MATCHING_V1_FOUNDER_DEFINITION.md`, `docs/engineering/21_MATCHING_V1_RECONCILIATION_AND_IMPLEMENTATION_PLAN.md`.

Everything in this document must be mechanically reproducible from raw item responses — no step relies on judgment, LLM output, or an unstated constant. Every constant used is named and given a version tag (`golden_test_v0.1`, `matching_methodology_v0.1`) so a later revision can change the constant without silently altering historical results (see doc 21 §4, versioning-stamp requirement).

---

## 1. Exact scale list

Four Likert-scored **vector blocks** (feed the three Fit metrics), plus three **structured context blocks** (feed Feasibility and ranking context only — never a Fit score):

| Block | Scales | Count | Feeds |
|---|---|---|---|
| A. Interests (RIASEC) | Realistic (R), Investigative (I), Artistic (A), Social (S), Enterprising (E), Conventional (C) | 6 | Interest Fit |
| B. Work Style | `autonomy`, `structure_preference`, `ambiguity_tolerance`, `pace`, `collaboration`, `leadership`, `customer_interaction`, `decision_responsibility`, `routine_tolerance`, `initiative` (reused verbatim from HPM v0.1 §3.1 — no new taxonomy) | 10 | Work Style Fit |
| C. Work Values | `income`, `stability`, `growth`, `independence_value`, `impact_helping`, `recognition_status`, `work_life_balance`, `learning` (new — see §A) | 8 | Values Fit |
| D. Work Environment | `setting`, `collaboration_context`, `schedule_predictability`, `physical_environment`, `customer_interaction_context` (reused verbatim from HPM v0.1 §3.2) | 5 | Work Style Fit (as a secondary, lower-weight input — see §18) |
| E. Goals | desired domain(s) (multi-select from `CareerDomain`), horizon (single-select) | 2 items | Ranking tie-break only (§C, §25) — never a Fit score |
| F. Experience/Skills | employment status, years of experience, education level, known skills (multi-select) | 4 items | Feasibility (§20), catalog context |
| G. Constraints | mapped to the 12 HPM v0.1 §3.3 subtypes, collapsed to ~10 structured questions (see §14) | ~10 items | Feasibility (§20), hard blockers (§21) |

Total Likert scales: **6 + 10 + 8 + 5 = 29**. This is the denominator of the Coverage formula (§15).

---

## 2. Exact item count `[HARDENED]`

**Superseded by `MNP_BASIC_SHORT_FORM_STRATEGY_V0.1.md`.** The 94-item bank below is the full research item bank; BASIC V1's actual target is the ~75-item short form defined in that document (3/scale RIASEC, 2/scale Work Style, 2/scale Work Values, 1/scale Work Environment, structured blocks unchanged). The table below is retained as the full-bank reference.


| Block | Items/scale | Items | Rationale |
|---|---|---|---|
| RIASEC | 5 per letter | 30 | Standard short-form Interest Profiler length. |
| Work Style | 2 per scale, 3 for `autonomy`, `leadership`, `collaboration`, `pace` (reliability-critical) | 6×2 + 4×3 = 24 | Matches doc 20's "~24" estimate. |
| Work Values | 2 per scale | 16 | Parsimony; may rise to 24 (3/scale) after pilot reliability check — flagged as a v0.2 candidate, not decided now. |
| Work Environment | mostly 2, single-item on the two lowest-ambiguity facets | 2+2+2+1+1 = 8 | Matches doc 20's "~8" estimate. |
| Goals | 2 | 2 | Structured pickers, not Likert. |
| Constraints | 1 per collapsed question | 10 | See §14 for the 12→10 collapse. |
| Experience/Skills | 4 | 4 | Structured facts. |
| **Total** | | **94** | Within doc 20's "~75–95" target range, at the upper bound. Target completion time ≈ 13–16 min at ~8–10 sec/item average for single-tap Likert/picker items — consistent with the "~12–18 min" product target. |

**PROVISIONAL:** the exact 94-item count is an engineering estimate for structural planning; the *final authored item bank* (see §3) requires separate Methodology Owner sign-off and is tracked as an M1 content task, not resolved by this document.

---

## 3. Exact UA item wording

This document fixes the **structure and scoring rule**, not the final content bank — inventing 94 "final" psychometric items without Founder/Methodology sign-off would violate the same "do not silently invent methodology content" principle this whole project has followed since `MNP_HUMAN_POTENTIAL_MODEL_V0.1.md`. Below is the **exact template** each item must follow, with one worked, ready-to-use example item per representative scale. Full item-bank authoring (all 94 items) is an explicit M1 follow-up task requiring sign-off, not silently deferred.

Template: a first-person, present-tense statement the respondent rates for how well it describes them. Reverse items are marked `[R]`.

| Scale | Example item (UA) | Reverse? |
|---|---|---|
| Realistic (R) | «Мені подобається працювати руками — ремонтувати, збирати, налаштовувати обладнання» | No |
| Investigative (I) | «Мені цікаво розбиратися, чому щось працює саме так, а не інакше» | No |
| Artistic (A) | «Мені подобається створювати щось оригінальне — текст, дизайн, музику, відео» | No |
| Social (S) | «Мені важливо, щоб моя робота допомагала іншим людям» | No |
| Enterprising (E) | «Мені подобається переконувати людей і вести перемовини» | No |
| Conventional (C) | «Мені комфортно працювати з чіткими інструкціями та структурованими даними» | No |
| `autonomy` (Work Style) | «Я працюю найкраще, коли сам вирішую, як виконати завдання» | No |
| `routine_tolerance` [R] | «Мене швидко втомлює одноманітна, повторювана робота» | **Yes** — high agreement = *low* routine tolerance |
| `income` (Work Values) | «Для мене важливо, щоб робота давала високий і стабільний дохід» | No |
| `setting` (Work Environment) | «Мені комфортніше працювати в офісі/на об'єкті, ніж повністю віддалено» | No (bipolar item; see §4) |

---

## 4. Answer scale

All Likert items (blocks A–D) use a **5-point agreement scale**:

1 — Зовсім не про мене
2 — Радше ні
3 — Важко сказати
4 — Радше так
5 — Дуже про мене

Bipolar items (e.g. `setting`, remote↔office) are worded as a single directional statement and scored on the same 1–5 scale; the *opposite* pole is implicit (low score = opposite preference), never a second question — this keeps every scale's item count and scoring rule uniform.

Structured blocks (E, F, G) use single-select or multi-select pickers, not Likert — no numeric "answer scale" applies; each is stored as a discrete value.

---

## 5. Reverse-scored items

At least one reverse-worded item per Likert scale wherever a natural reverse phrasing exists (standard practice against acquiescence/response-set bias) — e.g. `routine_tolerance` above. Reverse items are flagged `reverse=true` in the item bank.

**Reverse-scoring formula (5-point scale):**
```
corrected = 6 - raw_response
```
applied to every `reverse=true` item **before** it enters the per-scale mean (§6).

---

## 6. Per-scale scoring

For scale `s` with answered (non-null, reverse-corrected) item values `x_1..x_k`:

```
scale_score_raw(s) = mean(x_1..x_k)          # on the 1–5 scale
scale_score(s)      = (scale_score_raw(s) - 1) / 4     # rescaled to [0, 1]
```

If `k = 0` (no items answered), the scale is **UNSCORED** — not zero, not imputed — and does not participate in that Fit metric's vector (see §7–8, §15 Coverage).

---

## 7. Missing-answer handling

- A single skipped item → that item is `null`, excluded from the scale's mean.
- A scale is **"sufficiently answered"** if `answered_items ≥ ceil(0.8 × item_count_for_scale)`. Examples: a 2-item scale requires both items (⌈1.6⌉=2); a 3-item scale requires at least 3 (⌈2.4⌉=3 — i.e., no skips tolerated below 4 items); a 5-item scale (RIASEC) tolerates 1 skip (⌈4.0⌉=4).
- If a scale is not "sufficiently answered," it is UNSCORED (excluded from Coverage numerator, §15) rather than scored on fewer items — this avoids a scale's reliability silently degrading without being flagged.
- Structured blocks (E/F/G): a question is either answered or not; there is no partial-scale averaging. An unanswered Constraints question means that constraint subtype is `UNKNOWN`, never assumed absent (mirrors the existing HPM v0.1 principle that "missing ≠ satisfied").

---

## 8. Normalization

- **Person side:** every scale score is linearly rescaled from the raw 1–5 mean to `[0, 1]` via `(mean − 1) / 4` (§6) — applied uniformly to RIASEC, Work Style, Work Values, and Work Environment.
- **Career side:** `CareerMatchingProfile` numeric fields (populated from O*NET, whose native scales vary — e.g. O*NET Interests use a 1–7 "Occupational Interest" scale, Work Values use a 1–5 importance scale) are rescaled to the **same `[0, 1]` range** at import time, using each source scale's own documented min/max (never re-derived or guessed). This import-time rescaling is recorded with `source_version` (Career KB doc §G) so a future O*NET scale revision doesn't silently shift meaning.
- Both sides of every distance/similarity computation are therefore always unit-interval vectors before §17–19 apply.

---

## 9. RIASEC vector

`riasec = (R, I, A, S, E, C)`, each component ∈ `[0, 1]`, computed per §6 from the RIASEC items (5/letter full bank, 3/letter short form — `MNP_BASIC_SHORT_FORM_STRATEGY_V0.1.md`). Missing letters (insufficiently answered) leave that component `UNSCORED`; if more than 1 of 6 RIASEC letters is unscored **on either the user side or the career side**, Interest Fit for that pairing is not computed (INSUFFICIENT_DATA — see §26 edge cases). O*NET alignment: **DIRECT, all 6 letters, unconditionally** — confirmed unrevised in the current O*NET Content Model (`MNP_SCALE_TO_ONET_MAPPING_V0.1.md` §A).

---

## 10. Work Style vector `[HARDENED]`

`work_style = (autonomy, structure_preference, ambiguity_tolerance, pace, collaboration, leadership, customer_interaction, decision_responsibility, routine_tolerance, initiative)`, 10 components ∈ `[0, 1]`, using the **existing HPM v0.1 §3.1 keys unchanged** (no renaming, no new taxonomy version needed for this vector's internal structure).

**O*NET alignment is NOT uniform** — see the full per-key mapping and status in `MNP_SCALE_TO_ONET_MAPPING_V0.1.md` §B: only 3 of 10 keys are DIRECT matches to the **current** (post-2024-redesign, 21-element) O*NET Work Style taxonomy (`ambiguity_tolerance`, `leadership`, `initiative`); 2 are DERIVED composites; 4 are cross-domain PROXY matches (job-context data standing in for a person-side trait); 1 (`autonomy`) is MNP_ONLY, since O*NET's own 2024 redesign removed its one autonomy-related Work Style (`Independence`) and reclassified it as a Work Value — independently validating this document's placement of `independence_value` under Work Values (§11) rather than Work Style. This vector's overall compatibility status is **PROVISIONAL**, not READY.

---

## 11. Values vector `[HARDENED]`

`work_values = (income, stability, growth, independence_value, impact_helping, recognition_status, work_life_balance, learning)`, 8 components ∈ `[0, 1]`. This is a **new** subdimension set (HPM v0.1 §3.4 currently lists Values as top-level-only) — requires the HPM amendment banner (see `MNP_HUMAN_POTENTIAL_MODEL_V0.1.md`, amended by this document). Naming note: `independence_value` is deliberately distinct from Work Style's `autonomy` key — the former is *what the person values* (independence as a work value), the latter is *how the person prefers to work* (behavioral autonomy preference); conflating the two keys would corrupt both vectors.

**O*NET alignment** (full detail in `MNP_SCALE_TO_ONET_MAPPING_V0.1.md` §C): `independence_value`→O\*NET *Independence* (**DIRECT**, and now doubly confirmed as the correct domain by O*NET's own 2024 Work Styles redesign, which relocated Independence out of Work Styles into Work Values), `recognition_status`→O\*NET *Recognition* (**DIRECT**), `impact_helping`→O\*NET *Relationships* (**DIRECT**). `income`, `stability` are **PROXY** (partial overlap with O*NET's coarser *Working Conditions*/*Support* constructs, not a clean subset). `growth`, `work_life_balance`, `learning` are **MNP_ONLY** — no O*NET Work-Values equivalent exists; these three require their own MNP-curation-based sourcing plan for the career side (they cannot be populated from an O*NET import), not silently treated as O*NET-grounded. This vector's overall compatibility status is **PROVISIONAL**, not READY.

---

## 12. Work Environment vector

`work_environment = (setting, collaboration_context, schedule_predictability, physical_environment, customer_interaction_context)`, 5 components ∈ `[0, 1]`, using the **existing HPM v0.1 §3.2 keys unchanged**.

---

## 13. Goals representation

Not a vector, not a Fit input. Stored as a small structured record:

```
goals = {
  desired_domains: [CareerDomain, ...],   # 0..n selected, may be empty ("exploring")
  horizon: enum { NOW, MONTHS_3_6, MONTHS_6_12, EXPLORING }
}
```

Used only as a deterministic tie-break input in ranking (§24–25) and as Compatibility Report context ("Section A" framing); never blended into a numeric score (Founder decision — doc 20, Open Question C, resolved below in §C).

---

## 14. Constraints representation

Collapsed from the 12 HPM v0.1 §3.3 subtypes into 10 structured questions (some subtypes share one question where they are practically inseparable at intake time):

| Question | HPM subtype(s) covered |
|---|---|
| Мова(и) та рівень володіння | language |
| Найвищий здобутий рівень освіти | education |
| Наявні ліцензії/дозволи (якщо є) | credential, legal |
| Готовність до релокації / географічні обмеження | geography, mobility |
| Бажаний формат роботи (офіс/віддалено/гібрид) | work_format |
| Обмеження за графіком (змінний, повний/частковий день) | work_schedule |
| Часовий ресурс на навчання/перехід (год/тиждень) | time |
| Фінансова спроможність на перенавчання (є/немає) | financial |
| Сімейні/логістичні обмеження, що впливають на графік | family_logistics |
| Функціональні обмеження (стан здоров'я, що впливає на вид діяльності) | functional |

Each stored as a discrete/structured value (never free text in BASIC — free text is PRO-only, doc 21 §2.2). An unanswered question → that subtype is `UNKNOWN`, feeds Feasibility as neutral/unknown, never as a passing or failing value (§20–21).

---

## 15. Coverage formula `[HARDENED — schema-driven, not hardcoded]`

Coverage measures **test completeness only** — not confidence, not psychometric certainty (Founder's explicit distinction, doc 20 §12).

Per Founder decision D ("do NOT hard-code denominator 29"), Coverage is **schema-driven**:

```
Coverage = (# of enabled, required, "sufficiently answered" Likert scales, per §7)
           ────────────────────────────────────────────────────────────────────
                    (# of enabled, required Likert scales in the active schema)
```

"Enabled" and "required" are properties of the active assessment schema version (M1's item-bank table), not a fixed constant in this document. This makes Coverage correctly track the **short-form schema** (still 29 scales, since the short form reduces items-per-scale, not scale count — `MNP_BASIC_SHORT_FORM_STRATEGY_V0.1.md` §1–2), a future scale addition/removal, or a PRO-track schema with different enabled scales, without requiring this document to be edited every time the schema changes. The current BASIC V1 schema happens to enable all 29 scales as required, so the denominator is 29 today — but this is a schema fact, not a hardcoded rule.

Context completeness (Goals/Experience/Constraints) is tracked as a **separate boolean flag**, `context_complete`, not blended into the Coverage percentage — it gates Feasibility computation independently (§20), rather than diluting the vector-completeness number.

Coverage bands (see also Open Question D, §D):
- **Full** — Coverage = 100% (29/29)
- **Partial** — 80% ≤ Coverage < 100% (24–28/29): directions/fits are shown, with a visible Coverage note.
- **Insufficient** — Coverage < 80% (<24/29): Career Dashboard fit computation is not run; user is prompted to complete remaining scales.

---

## 16. Career-vector encoding

Every `Career` row that has been mapped (Career KB doc §B/§C) carries a `CareerMatchingProfile` with the **same four vector shapes** as the person side: `riasec` (6), `work_style` (10, only the subset O*NET/MNP curation can support — unmapped components are `UNSCORED`, never invented), `work_values` (8, same caveat), `work_environment` (5). Each individual component carries its own `provenance` (source, source_version, mapping_version, `is_provisional`) — see Career KB doc §G/§L. A career with zero mapped components in a given vector cannot produce that Fit metric (falls back to INSUFFICIENT_DATA for that one metric only, not for the whole career).

---

## 17. Interest Fit metric `[HARDENED — guarded cosine, per benchmark]`

**Metric: guarded cosine similarity** between the person's `riasec` vector and the career's `riasec` vector. `MNP_MATCHING_METRIC_BENCHMARK_V0.1.md` computed 11 concrete cases and found unguarded cosine produces materially wrong results for flat/undifferentiated and near-zero vectors (both user- and career-side) — guarding is not optional polish, it is required to avoid a demonstrated failure mode.

```
1. dispersion_ok(v) := stdev(v components) ≥ 0.10        # placeholder threshold, PROVISIONAL
2. If NOT dispersion_ok(riasec_u) OR NOT dispersion_ok(riasec_c):
       InterestFit = INSUFFICIENT_DATA / LOW_DIFFERENTIATION   (never a computed score)
3. Else:
       InterestFit(u, c) = (riasec_u · riasec_c) / (‖riasec_u‖ × ‖riasec_c‖)
```

Since both vectors have non-negative components in `[0,1]`, `InterestFit ∈ [0, 1]` directly when computed. Undefined (both-zero vector) is treated as INSUFFICIENT_DATA, never as 0 or 1 — and now, per the benchmark, so is any vector too flat to carry real signal, on **either** side of the comparison (fixes the Case 9 symmetric-missing-data gap — see benchmark doc §4).

---

## 18. Work Style Fit metric `[HARDENED — guarded cosine]`

Same guarded-cosine approach as §17, applied to the concatenated `(work_style ‖ 0.5 × work_environment)` vectors (Work Environment enters at half weight as a secondary signal, per doc 20's note that Work Environment "partially overlaps with B" and is a smaller, less discriminating vector):

```
1. Check dispersion_ok() on both concatenated vectors (§17 rule).
2. If either fails: WorkStyleFit = INSUFFICIENT_DATA / LOW_DIFFERENTIATION.
3. Else: WorkStyleFit(u, c) = cos( work_style_u ⊕ 0.5·work_environment_u ,
                                   work_style_c ⊕ 0.5·work_environment_c )
```
where `⊕` denotes vector concatenation. If a user or career is missing the Work Environment component entirely, the metric falls back to `cos(work_style_u, work_style_c)` alone (documented fallback, not silent). Recall this whole vector is only **PROVISIONAL** for O*NET-groundedness (§10) — the guard here is an additional, independent safeguard against degenerate vectors, not a substitute for that caveat.

---

## 19. Values Fit metric `[HARDENED — guarded cosine]`

Same guarded-cosine approach:

```
1. Check dispersion_ok() on both work_values vectors (§17 rule).
2. If either fails: ValuesFit = INSUFFICIENT_DATA / LOW_DIFFERENTIATION.
3. Else: ValuesFit(u, c) = cos(work_values_u, work_values_c)
```

---

## 20. Feasibility algorithm

Transition Feasibility is **not** a vector-similarity metric — it is a **gate-then-score** algorithm over Constraints + Experience/Skills vs the career's `CareerRequirement`/`CareerWorkContext` rows (existing Stage 3A entities, unchanged):

```
1. Evaluate hard blockers (§21) against the career's requirements.
   → If any hard blocker fires: Feasibility = BLOCKED (terminal; career is excluded
     from the ranked catalog by default, but visible under an explicit
     "blocked — why" filter, never silently hidden).
2. If not blocked, start from a base score of 1.0 and apply soft penalties (§22).
3. Clamp to [0, 1]; map to a band via §23 cutoffs.
```

This reuses the existing Stage 3B "hard gate vs soft adjustment" conceptual shape (`MNP_CAREER_FIT_MODEL_V0.1.md`'s feasibility gate), recomputed here over the new structured Constraints representation (§14) instead of claims-derived constraints.

---

## 21. Hard blockers

A constraint fires as a hard blocker only when it is a **known, structurally incompatible** fact — never on `UNKNOWN`:

- Required license/credential the career legally requires, and the user has explicitly indicated they do not hold it and cannot obtain it within the stated horizon.
- Required language proficiency below the career's documented minimum (explicit "known" value only).
- Geography/mobility: career requires physical presence in a location the user has explicitly excluded, with no remote/hybrid option on the career side.
- Functional constraint explicitly incompatible with a career's documented physical/environmental requirement.

`UNKNOWN` on any of the above never blocks — it is surfaced in the Compatibility Report §F ("what information is missing") instead.

---

## 22. Soft penalties

Applied multiplicatively to the base 1.0 score, each independent and named (never a hidden blend):

| Condition | Penalty factor |
|---|---|
| Education level below career's typical entry level, but not legally required | ×0.85 |
| Schedule/work-format mismatch (soft preference, not hard requirement on the career side) | ×0.9 |
| Family/logistics constraint flagged as "significant" by the user | ×0.9 |
| No time/financial capacity indicated for required retraining, and a skills gap exists | ×0.8 |

Multiple penalties compound multiplicatively (e.g. two penalties → ×0.85×0.9), then clamp to `[0,1]`. This keeps the computation fully auditable per-factor rather than an opaque weighted sum.

---

## 23. Band cutoffs

Uniform three-band mapping applied to all four numeric outputs (Interest Fit, Work Style Fit, Values Fit, Feasibility), each independently:

- **HIGH**: score ≥ 0.70
- **MEDIUM**: 0.40 ≤ score < 0.70
- **LOW**: score < 0.40

**PROVISIONAL** — these cutoffs are placeholders pending Golden Case calibration against real pilot data (consistent with how Stage 3B's own band cutoffs were labeled provisional). No 5-star or single combined percentage is ever derived from these bands (Founder invariant, doc 20 §10). `MNP_MATCHING_METRIC_BENCHMARK_V0.1.md` §5 demonstrates concretely (not just asserts) that a ±0.05 cutoff shift materially reorders the ranked catalog — the provisional label is backed by evidence, not just caution.

---

## 24. Ranking

Conceptual order (doc 20): **Hard feasibility gate → Interest Fit → Work Style Fit → Values Fit → soft feasibility adjustment/context → deterministic ordering.**

Concretely, the default Career Catalog sort key is the descending tuple:
```
(not BLOCKED, InterestFit_band, WorkStyleFit_band, ValuesFit_band, Feasibility_score, InterestFit_raw)
```
i.e., band-level sorting takes priority (avoids over-precision on a provisional metric), with raw scores used only to break ties *within* the same band-tuple, before Goals tie-break (§25). This is a **global, flat ranking** by default (Open Question H, resolved in §7 of doc 21 and restated in §26 below) — domain is a filter, not a forced grouping.

---

## 25. Tie-breaks

Applied in order, only when the full `(Feasibility-not-blocked, InterestFit_band, WorkStyleFit_band, ValuesFit_band)` tuple is identical between two careers:

1. Higher raw Feasibility score wins.
2. Higher raw InterestFit wins.
3. **Goals tie-break** (the only mechanical role Goals plays, per Open Question C): if the user specified a desired domain and exactly one of the tied careers matches it, that career sorts first.
4. Stable order by `Career.code` (deterministic final fallback — never random).

---

## 26. Worked example

**User "Олена"** (illustrative, not a real respondent) completes the Golden Test with Coverage = 100%. Selected raw scale means (1–5) → rescaled to [0,1] via §6:

- RIASEC: R=2.0→0.25, I=4.0→0.75, A=3.0→0.50, S=4.5→0.875, E=2.5→0.375, C=3.5→0.625
- Work Style (10 dims, abbreviated): autonomy=0.70, structure_preference=0.40, ambiguity_tolerance=0.55, pace=0.60, collaboration=0.80, leadership=0.35, customer_interaction=0.75, decision_responsibility=0.50, routine_tolerance=0.30, initiative=0.65
- Work Values (8 dims): income=0.50, stability=0.60, growth=0.70, independence_value=0.55, impact_helping=0.85, recognition_status=0.40, work_life_balance=0.65, learning=0.75
- Work Environment (5 dims): setting=0.40 (prefers office/hybrid), collaboration_context=0.75, schedule_predictability=0.60, physical_environment=0.30, customer_interaction_context=0.70
- Constraints: education=Bachelor's, no blocking language/credential issues, remote-friendly, no relocation constraint, retraining capacity=YES.
- Goals: desired_domains=[HEALTHCARE_SOCIAL], horizon=MONTHS_6_12.

**Career "Соціальний працівник" (Social Worker)**, `CareerMatchingProfile` (illustrative, from O*NET+MNP mapping):
- RIASEC: R=0.10, I=0.40, A=0.20, S=0.90, E=0.30, C=0.35
- Work Style: autonomy=0.55, structure_preference=0.45, ambiguity_tolerance=0.60, pace=0.50, collaboration=0.85, leadership=0.40, customer_interaction=0.90, decision_responsibility=0.55, routine_tolerance=0.35, initiative=0.60
- Work Values: income=0.35, stability=0.55, growth=0.50, independence_value=0.45, impact_helping=0.95, recognition_status=0.30, work_life_balance=0.55, learning=0.60
- Work Environment: setting=0.35, collaboration_context=0.80, schedule_predictability=0.55, physical_environment=0.25, customer_interaction_context=0.85
- Requirements: Bachelor's typical entry, no license required in this illustrative case, office/field hybrid setting.

**Step 1 — Interest Fit** (§17):
`riasec_u · riasec_c = 0.25·0.10 + 0.75·0.40 + 0.50·0.20 + 0.875·0.90 + 0.375·0.30 + 0.625·0.35`
`= 0.025 + 0.300 + 0.100 + 0.7875 + 0.1125 + 0.21875 = 1.54375`
`‖riasec_u‖ = √(0.0625+0.5625+0.25+0.7656+0.1406+0.3906) = √2.1719 ≈ 1.4737`
`‖riasec_c‖ = √(0.01+0.16+0.04+0.81+0.09+0.1225) = √1.2325 ≈ 1.1102`
`InterestFit = 1.54375 / (1.4737 × 1.1102) ≈ 1.54375 / 1.6362 ≈ 0.9436` → **HIGH** (≥0.70)

**Step 2 — Work Style Fit** (§18, concatenated with 0.5×Work Environment):
Dot product of the 10 Work Style pairs ≈ 0.385+0.180+0.330+0.300+0.680+0.140+0.675+0.275+0.105+0.390 = **3.460**
Dot product of the 0.5-weighted Work Environment pairs (0.5×each side, i.e. 0.25×product): (0.40×0.35+0.75×0.80+0.60×0.55+0.30×0.25+0.70×0.85)×0.25 = (0.14+0.60+0.33+0.075+0.595)×0.25 = 1.74×0.25 = **0.435**
Combined dot ≈ 3.895. Norms computed analogously (omitted for brevity of hand-computation) yield ‖u‖≈1.98, ‖c‖≈2.05 → `WorkStyleFit ≈ 3.895/(1.98×2.05) ≈ 0.960` → **HIGH**

**Step 3 — Values Fit** (§19): dominant shared signal is `impact_helping` (0.85 vs 0.95, both high) driving a strong cosine; computed value ≈ **0.93** → **HIGH**

**Step 4 — Feasibility** (§20–22): no hard blockers fire (education meets typical entry, no language/credential/geography conflict). No soft penalties apply (education matches, format matches, no family-logistics flag, retraining capacity=YES with no material skills gap assumed). Feasibility = **1.0** → **HIGH**

**Step 5 — Coverage**: 29/29 scales sufficiently answered → **100%, Full**.

**Step 6 — Ranking position**: tuple `(not BLOCKED, HIGH, HIGH, HIGH, 1.0, 0.9436)` — a top-of-catalog result. Goals tie-break (§25) would favor this career further if tied with another HIGH/HIGH/HIGH/1.0 result, since `HEALTHCARE_SOCIAL` matches the user's stated desired domain.

**Result shown to Олена:** Interest Fit HIGH, Work Style Fit HIGH, Values Fit HIGH, Transition Feasibility HIGH, Coverage 100% (Full) — no combined score, four independent bands plus one meta indicator, exactly as doc 20 §10 requires.

---

## Open Math Questions — Founder Review outcomes (2026-08-28)

> **A and B below are no longer fully open** — Founder Review "Matching V1 M0" issued explicit decisions superseding the original recommendations. C and D were **approved** (D with a change, applied above in §15). The original recommendation text is retained below for audit trail, with the Founder's actual decision layered on top.

### A. Work Preferences / Work Values exact scales — CONDITIONAL APPROVE

**Options:**
1. Reuse existing HPM v0.1 Work Style (10 subdims) + Work Environment (5 facets) unchanged; add a new 8-scale Work Values set.
2. Invent an entirely new Work Preferences taxonomy independent of HPM v0.1.
3. Adopt O*NET's native 16 Work Styles + 6 Work Values wholesale, dropping MNP's existing taxonomy.

**Pros/Cons:** (1) reuses already-coded, already-versioned taxonomy — zero migration cost, stays consistent with every existing Stage 3B artifact; loses nothing doc 20 asked for (its "~8" Work Style estimate is a subset of the existing 10). (2) maximum flexibility but throws away working, tested infrastructure for no stated benefit. (3) maximizes O*NET-crosswalk purity but breaks every existing Work-Style-keyed component in the codebase (`app/services/direction/dimensions.py`, `dimension_mapping.py`) and doc 20 never asked for O*NET's full 16/6 — it explicitly proposed ~8 each.

**V0.1 RECOMMENDATION:** Option 1 — reuse Work Style (10) and Work Environment (5) as-is; add the new 8-scale Work Values set defined in §11.
**WHY:** Existing taxonomy already covers doc 20's proposed scales plus 2 extra (decision_responsibility, initiative) at no cost; only Values genuinely needs new subscales (HPM v0.1 §3.4 left Values top-level-only).
**PROVISIONAL STATUS:** Provisional — requires HPM v0.1 amendment sign-off (banner added) and Methodology Owner review of the 8 Values keys before final item authoring.

**FOUNDER DECISION:** Conceptual scale families (Work Style/Values as separate contextual/psychometric layers, Goals/Constraints/Experience as structured, non-Fit inputs) are approved. The Founder explicitly rejected freezing the 6+10+8+5=29 count as canonical merely because it appeared in the draft, and required an explicit MNP↔O*NET reconciliation before finalizing the schema — delivered in `MNP_SCALE_TO_ONET_MAPPING_V0.1.md`. Outcome: RIASEC confirmed stable (no incompatibility found, kept as the classical anchor per Founder's own instruction). Work Style and Work Values are **not** silently force-mapped where O*NET measures a different construct — each is now marked DIRECT/DERIVED/PROXY/MNP_ONLY per key, both vectors carry an overall **PROVISIONAL** compatibility status (not READY), and the 3 MNP_ONLY Work Values keys (`growth`, `work_life_balance`, `learning`) are flagged as needing their own non-O*NET sourcing plan for the career side.

### B. Vector-distance metric — PROVISIONAL APPROVAL ONLY (not yet final)

**Options:** cosine similarity; normalized Euclidean distance; Pearson profile correlation; Holland hexagonal C-index (RIASEC-specific).

**Pros/Cons:** Cosine — scale-invariant, bounded [0,1] for non-negative vectors, uniform across vectors of different dimensionality (6/10/8/5), simple one-line formula, auditable. Euclidean — sensitive to dimension count, needs per-vector normalization constants to stay comparable, harder to keep uniform across the three Fit metrics. Pearson r — statistically unstable on short vectors (6-item RIASEC), undefined when a career's vector has near-zero variance. Holland C-index — theoretically well-grounded for RIASEC specifically but adds real complexity, is RIASEC-only (doesn't generalize to Work Style/Values), and risks being non-transparent to a small team maintaining this system.

**V0.1 RECOMMENDATION:** Cosine similarity, applied uniformly to all three Fit metrics.
**WHY:** Single, simple, auditable formula that generalizes across all vector shapes without per-metric special-casing; naturally bounded for our non-negative [0,1] vectors; avoids inventing per-vector normalization constants.
**PROVISIONAL STATUS:** Provisional — cosine's known weakness (magnitude-blindness) is intentionally not compensated for inside the Fit metric itself; it is instead caught by the Coverage/consistency checks. Subject to Golden Case calibration; may be revisited if pilot data shows systematic over-scoring of low-magnitude profiles.

**FOUNDER DECISION:** Cosine was explicitly NOT yet approved as final — Founder required an actual computed benchmark against normalized Euclidean distance, with ≥10 deliberately difficult cases including flat/undifferentiated profiles, near-zero vectors, and weak-coverage careers, before any recommendation stands. `MNP_MATCHING_METRIC_BENCHMARK_V0.1.md` delivers this: 11 computed cases, 2 of which (flat-profile and near-zero cases) show cosine producing materially misleading HIGH-band results where Euclidean does not. **Revised recommendation: guarded cosine** (§17–19 above) — cosine retained for its correct shape-matching behavior on well-differentiated vectors, but gated by a minimum-dispersion check (`stdev ≥ 0.10`, placeholder) that returns INSUFFICIENT_DATA/LOW_DIFFERENTIATION for flat or near-zero vectors on either side, rather than a possibly-inflated score. This remains **PROVISIONAL** pending Golden Case calibration of the dispersion threshold — it is a firmer, evidence-backed position than the original unconditional-cosine recommendation, not yet a final one.

### C. Goals' role — APPROVED

**Options:** (1) hard filter (excludes non-matching domains); (2) soft ranking booster within the primary sort (added into the Fit score); (3) pure tie-break only, never touching primary ranking; (4) purely informational, no mechanical role at all.

**Pros/Cons:** (1) risks false negatives — a user's stated domain may not reflect where their best fit actually is, contradicting the whole point of exploratory matching. (2) creates a hidden composite score blending psychometric fit with a stated preference — explicitly forbidden by doc 20 ("Goals must not become a 5th personality Fit output"). (3) fully deterministic, never reorders across bands, only breaks ties within an already-tied band-tuple — minimal, auditable, reversible. (4) safest but wastes a clearly useful, low-risk signal the user explicitly provided.

**V0.1 RECOMMENDATION:** Option 3 — Goals used only as the final tie-break step (§25), after Feasibility and raw Interest Fit, never before them and never blended into any score.
**WHY:** Satisfies doc 20's explicit constraint ("if and only if explicitly defined in Golden Test math... otherwise keep contextual") with the narrowest possible mechanical role — cannot manufacture a false top result, cannot mask a better psychometric match, fully reversible if Founder wants Option 4 instead.
**PROVISIONAL STATUS:** Provisional — ties are expected to be rare given band-then-raw-score sorting, so this mechanism will affect very few rankings in practice; revisit after Golden Case data shows actual tie frequency.

**FOUNDER DECISION: APPROVED.** Goals must never modify Interest/Work Style/Values Fit; the tie-break-only mechanical role (§25) is confirmed as the correct, minimal implementation. Fit and Intent remain conceptually separate, as designed.

### D. Coverage threshold — APPROVED WITH CHANGE

**Options:** (1) 100% required for any output; (2) 100%/80%/<80% three-band model (§15); (3) no threshold — always compute, just display the raw Coverage %.

**Pros/Cons:** (1) too strict — a single accidentally-skipped item blocks the whole Career Dashboard, poor UX for a ~94-item test. (2) balances "never manufacture recommendations from too little data" (an existing Stage 3B principle) against real-world skip tolerance. (3) maximally permissive but risks showing confident-looking bands built from a near-empty profile.

**V0.1 RECOMMENDATION:** Option 2 — Full (100%) / Partial (80–99%, shown with a visible note) / Insufficient (<80%, fit computation withheld, completion prompted).
**WHY:** Mirrors the existing Stage 3B "never manufacture recommendations from too little data" philosophy, recalibrated to the new item-based Coverage measure instead of the old claims-based one; 80% (≈24/29 scales) is a defensible floor given the test is designed for single-sitting completion with minimal expected skips.
**PROVISIONAL STATUS:** Provisional — the 80% cutoff is a placeholder pending pilot skip-rate data; may be tightened or loosened once real completion patterns are observed.

**FOUNDER DECISION: APPROVED WITH CHANGE.** The three-band model (Full/Partial/Insufficient) stands, but the denominator must be schema-driven, not hardcoded — applied in §15 above (`Coverage = scorable enabled required scales / enabled required scales`). Context completeness (Goals/Experience/Constraints) remains a separate boolean, never blended into psychometric Coverage, exactly as already specified in §15.

---

## Edge cases (referenced above)

- **INSUFFICIENT_DATA** is a distinct state from a LOW band on any Fit metric — it means the metric could not be computed at all (too few RIASEC letters scored, or the career has zero mapped components for that vector), and must never be silently rendered as LOW.
- **BLOCKED** (Feasibility) is distinct from LOW Feasibility — a blocked career is excluded from the default catalog view but never deleted from the data; it remains visible under an explicit "show blocked" filter with the specific blocking reason named (never a bare "no").
