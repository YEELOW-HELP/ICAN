# MNP BASIC Short-Form Strategy V0.1

**Status:** PROVISIONAL v0.1 — hardening deliverable per Founder Review "Matching V1 M0" (2026-08-28). The ~94-item count in `MNP_GOLDEN_TEST_V0.1.md` §2 is hereby explicitly reclassified as a **research item bank / planning estimate**, not the approved BASIC test length. This document defines the full bank, a proposed short form, and the deterministic rules needed to run a shorter test without silently degrading validity.

---

## 1. Full item bank (unchanged from Golden Test doc §1–2)

| Block | Scales | Items/scale (full bank) | Full-bank total |
|---|---|---|---|
| RIASEC | 6 | 5 | 30 |
| Work Style | 10 | 2 (6 scales) / 3 (4 scales: autonomy, leadership, collaboration, pace) | 24 |
| Work Values | 8 | 2 | 16 |
| Work Environment | 5 | 2 (4 scales) / 1 (1 scale) | 8 |
| Goals | 2 structured | — | 2 |
| Constraints | 10 structured | — | 10 |
| Experience/Skills | 4 structured | — | 4 |
| **Total** | | | **94** |

This full bank remains the target for **content authoring** (Methodology Owner sign-off, tracked separately, not resolved by this document) and is also the bank a future PRO-track "extended assessment" could draw from. It is not, by itself, the BASIC test length.

---

## 2. Proposed BASIC short form

**Target: 40–60 items**, per Founder's stated exploration range. Reduction strategy: cut items **per scale**, not by removing whole scales — every scale must remain independently scorable (no scale is dropped entirely, since every scale feeds a Fit metric or Feasibility).

| Block | Full-bank items/scale | Short-form items/scale | Short-form total | Reduction rationale |
|---|---|---|---|---|
| RIASEC | 5/scale (30) | **3/scale** (18) | 18 | Short-form Interest Profilers (O*NET's own "Mini IP") commonly use 3–6 items/scale; 3 preserves discriminability while halving length. |
| Work Style | 2–3/scale (24) | **2/scale, uniformly** (20) | 20 | Drop the 3rd item on the 4 reliability-critical scales (autonomy, leadership, collaboration, pace); accept slightly lower per-scale reliability in BASIC, offset by the PRO track's option to re-administer the full bank later. |
| Work Values | 2/scale (16) | **2/scale, unchanged** (16) | 16 | Already minimal (2 is the floor for any reverse-item policy, §4); no further cut possible without dropping a scale entirely, which is not permitted. |
| Work Environment | 1–2/scale (8) | **1/scale, uniformly** (5) | 5 | Environment is explicitly the lowest-priority, most overlapping-with-Work-Style block (Founder doc 20's own framing) — safest place to cut to the floor. |
| Goals | 2 structured (2) | 2 (2) | 2 | Structured pickers, not reducible. |
| Constraints | 10 structured (10) | 10 (10) | 10 | Not reducible — each question maps to a distinct hard/soft feasibility input; dropping any one silently reintroduces an "unknown treated as passing" risk. |
| Experience/Skills | 4 structured (4) | 4 (4) | 4 | Not reducible — minimal factual set. |
| **Total** | 94 | | **75** | |

**This lands at 75, above the 40–60 exploration target.** Reaching 40–60 requires a second-pass structural decision, not just item-trimming, since the structured blocks (26 items: Goals+Constraints+Experience) are already at their floor and the four Likert blocks are already near their psychometric floor per-scale (RIASEC 3, Work Style 2, Work Values 2, Environment 1).

**Two paths to reach 40–60, both requiring explicit Founder sign-off before M1 (not silently chosen here):**

- **Path 1 — Scale consolidation:** merge conceptually adjacent Work Style scales flagged PROXY/MNP_ONLY in `MNP_SCALE_TO_ONET_MAPPING_V0.1.md` (e.g., `pace` + `routine_tolerance`, both PROXY with no clean O*NET counterpart) into fewer, broader scales. This would need its own construct-validity review — not done here, since it changes the taxonomy, not just the item count.
- **Path 2 — Accept ~70–75 as the BASIC length**, treating "40–60" as an aspirational target rather than a hard requirement, given Constraints/Goals/Experience cannot ethically shrink further without weakening Feasibility (a hard-blocker-capable computation) and RIASEC cannot shrink below 3/scale without falling below standard short-form practice.

**V0.1 recommendation: Path 2** — hold at **75 items** for BASIC V1, explicitly presented to the Founder as "short-form, not yet at the 40–60 target," rather than force a scale-consolidation exercise that risks corrupting the Feasibility/Constraints layer just to hit a number. At ~75 items and ~8–10 sec/item for single-tap Likert/picker items, target completion time is **≈10–13 minutes** — inside the product's "12–18 min" envelope even before optimizing further.

**PROVISIONAL STATUS:** this is a structural proposal, not a validated final length; a pilot timing study (real users completing the 75-item form) is the actual authority on whether 75 is acceptable, and Path 1 remains available as a v0.2 option if pilot data shows unacceptable drop-off/fatigue.

---

## 3. Minimum items per scale (floor, below which a scale is not administered in BASIC at all)

| Scale type | Minimum items | Rationale |
|---|---|---|
| RIASEC | 2 | Below 2, a single-item scale has no internal reliability check at all (no way to detect an inconsistent/careless response within the scale itself). |
| Work Style | 2 | Same reasoning; also the minimum needed to support the reverse-item policy (§4). |
| Work Values | 2 | Same. |
| Work Environment | 1 | Explicitly accepted as a floor exception for BASIC — Work Environment already has the weakest O*NET grounding (Career KB mapping doc §D) and the lowest priority per Founder doc 20; a single item per facet is a deliberate, named trade-off, not an oversight. |

No scale in BASIC drops below these floors; if a future length reduction would require it, the scale must instead be dropped from BASIC scoring entirely and marked `MNP_ONLY / not administered in BASIC`, never silently degraded to a zero-reliability single item outside the Work Environment exception.

---

## 4. Reverse-scored item policy

- Every scale with **≥2 items** in the short form must retain **at least one** reverse-worded item wherever the underlying construct has a natural reverse phrasing (per Golden Test doc §5) — this is a hard floor, not reduced by the short-form pass. A 2-item scale in the short form is therefore always exactly 1 straight + 1 reverse item, never 2 straight items, to preserve at least a minimal acquiescence-bias check.
- Scales where no natural reverse phrasing exists (rare; to be confirmed during item authoring) are exempted, but the exemption must be recorded explicitly in the item bank metadata (`reverse_exempt: true, reason: "..."`) — never silently absent.
- The reverse-scoring formula is unchanged from Golden Test doc §5 (`corrected = 6 − raw` on the 5-point scale).

---

## 5. Deterministic rule for insufficient scale data

This restates and tightens Golden Test doc §7 for the short-form context, where the "sufficiently answered" threshold has less room to tolerate skips given fewer items per scale:

- A 2-item scale requires **both** items answered (0 tolerated skips) — `ceil(0.8×2) = 2`.
- A 3-item scale (RIASEC short form) requires **at least 3** — `ceil(0.8×3) = 3` — i.e., **also zero tolerated skips** at this length (the 80% threshold rounds up to "all of them" below 5 items). This is a direct, mechanical consequence of applying the existing §7 formula to shorter scales, not a new rule — but it is worth stating explicitly here because it means **the short form has effectively zero skip-tolerance per scale**, a real UX implication: any single skipped item drops that entire scale to UNSCORED, not just reduces its precision.
- **Consequence for Coverage:** because skip-tolerance drops to zero at short-form lengths, the schema-driven Coverage formula (Golden Test doc §15, hardened to `scored_required_scales / enabled_required_scales`) will be **more sensitive to individual skips** under the short form than it would be under the full 94-item bank. This is flagged as a genuine UX/product tension the Founder should weigh: shorter test = faster completion, but any stray skip costs an entire scale rather than a fraction of one. **Recommended mitigation (not yet approved):** the BASIC short-form UI should treat every question as required-to-advance (no skip button) rather than allowing skips at all, sidestepping the zero-tolerance cliff by preventing partial-scale answers in the first place. This is a UX/frontend decision for M5, noted here only as a consequence of the math, not decided by this document.

---

## 6. Interaction with Coverage and band cutoffs

The short form does not change the Coverage *formula* (now schema-driven per the Golden Test doc hardening, §7 below) — it changes the *denominator's* practical size (29 Likert scales either way; only item-count-per-scale shrinks) and removes per-scale skip tolerance (§5 above). It has no interaction with the band-cutoff sensitivity findings in `MNP_MATCHING_METRIC_BENCHMARK_V0.1.md` §5, which are driven by the matching engine, not the test length.
