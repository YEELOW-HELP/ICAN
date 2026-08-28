# MNP Matching Metric Benchmark V0.1

**Status:** PROVISIONAL v0.1 — hardening deliverable per Founder Review "Matching V1 M0" (2026-08-28). Every number below was actually computed (not estimated) with a short deterministic script; no ML, no LLM, no fitted coefficients. Supersedes the unconditional cosine recommendation in `MNP_GOLDEN_TEST_V0.1.md` §B/§17–19 — this document builds the case first and reaches a conclusion at the end, not the reverse.

---

## 1. Metrics under test

**Cosine similarity:** `cos(u,v) = (u·v) / (‖u‖·‖v‖)`. For non-negative `[0,1]` vectors, `cos ∈ [0,1]` directly.

**Normalized Euclidean similarity:** `euclid_sim(u,v) = 1 − (‖u−v‖ / √n)`, where `n` is the vector's dimensionality and `√n` is the maximum possible distance between two points in `[0,1]^n` — this bounds the metric to `[0,1]` on the same scale as cosine, making the two directly comparable.

All 6-dimensional test vectors below use RIASEC as the concrete example; the same shape of divergence applies identically to the 10-dim Work Style, 8-dim Work Values, and 5-dim Work Environment vectors (only `n` changes).

---

## 2. Worked test cases (all values computed, not estimated)

| # | Case | u | v | cosine | euclid_sim | Δ (cos−euclid) | Interpretation |
|---|---|---|---|---|---|---|---|
| 1 | Identical vectors | (0.8,0.3,0.5,0.7,0.2,0.4) | same | **1.000** | **1.000** | 0.000 | Both metrics agree trivially. |
| 2 | Proportional vectors (same shape, half magnitude) | (0.8,0.3,0.5,0.7,0.2,0.4) | 0.5×u | **1.000** | **0.736** | +0.264 | Cosine says "perfect match" purely from shape; Euclidean correctly notices the career/person differ substantially in overall intensity. |
| 3 | Same shape, materially different magnitude (flat-high vs. flat-low) | (0.9,0.9,0.9,0.9,0.9,0.9) | (0.1,0.1,0.1,0.1,0.1,0.1) | **1.000** | **0.200** | +0.800 | **Critical divergence.** A person who is flatly *very* interested in everything and a career that is flatly *barely* related to anything get a **perfect** cosine score. This is the single largest gap found. |
| 4 | Opposite preference patterns | (0.9,0.1,0.9,0.1,0.9,0.1) | (0.1,0.9,0.1,0.9,0.1,0.9) | 0.220 | 0.200 | +0.020 | Both metrics agree: genuinely opposite patterns score low. No practical divergence. |
| 5 | Flat/undifferentiated user profile vs. a normally peaked career | (0.5,0.5,0.5,0.5,0.5,0.5) | (0.9,0.2,0.8,0.3,0.7,0.1) | 0.849 (→ **HIGH** band) | 0.689 (→ **MEDIUM** band) | +0.160 | A user who answered "3 — Важко сказати" on every item (i.e., gave no real signal) is rated HIGH-fit by cosine and only MEDIUM by Euclidean. Cosine rewards direction-only alignment even when the user vector carries no real discriminating information. |
| 6 | Highly peaked, identical | (1,0,0,0,0,0) | same | 1.000 | 1.000 | 0.000 | Agreement, as expected. |
| 7 | Highly peaked, partial overlap | (1,0,0,0,0,0) | (0.7,0.7,0,0,0,0) | 0.707 | 0.689 | +0.018 | Close agreement — once both vectors are already sparse/peaked, the two metrics converge. |
| 8 | Sparse/missing dimensions (2 of 6 RIASEC letters UNSCORED) | — | — | N/A | N/A | — | Per Golden Test §9, >1 unscored letter → INSUFFICIENT_DATA for *both* metrics; this guard works correctly regardless of which metric is chosen and is unaffected by this benchmark. |
| 9 | Career with weak source coverage (only 2 of 6 RIASEC components mapped) | fully-scored user | (0.7, ∅, ∅, ∅, ∅, 0.3) | **GAP FOUND** | — | — | The Golden Test doc specifies the missing-data guard only for the *user* side (§9); it does not yet specify the symmetric case where the *career* vector is incomplete. See §4 below — this benchmark surfaces a real spec gap, now fixed. |
| 10 | Near-zero/minimal-effort user profile | (0.05,0.05,0.05,0.05,0.05,0.05) | (0.7,0.2,0.6,0.3,0.5,0.1) | **0.880** (→ **HIGH**) | 0.589 (→ **MEDIUM**) | +0.291 | **Most damaging failure mode found.** A user who essentially answered "none of this describes me" (near-zero on every RIASEC item — a strong signal of disengagement, not of a real interest profile) is scored **HIGH** fit against almost any career with positive-valued components, purely because cosine is direction-only and any small positive vector "points toward" any other positive vector to some degree. |
| 11 | Flat/undifferentiated **career** vector (e.g. unmapped or placeholder-default) vs. a well-differentiated user | (0.9,0.1,0.8,0.2,0.7,0.3) | (0.5,0.5,0.5,0.5,0.5,0.5) | 0.849 (→ **HIGH**) | 0.689 (→ **MEDIUM**) | +0.160 | Same failure mode as #5/#10, mirrored onto the career side: a career whose `CareerMatchingProfile` is provisional/flat (Career KB doc §L) would be shown as a **HIGH** Interest Fit for almost any user under cosine — a serious risk given provisional vectors are explicitly expected to exist during the pilot. |

---

## 3. Where cosine produces unintuitive outcomes — summary

Cases 3, 5, 10, and 11 are not edge-case curiosities — they describe realistic pilot scenarios:
- **Case 3 / proportionality-blindness:** a person who rates everything similarly (whether high or low) gets treated as "perfectly shaped" against anything else with the same relative pattern, regardless of actual intensity match.
- **Case 5 / 11 / flat-vector inflation:** either side (user *or* career) having a flat, undifferentiated, or provisional-default vector produces an artificially high cosine score against almost anything, because cosine has no mechanism to penalize a lack of real signal.
- **Case 10 / near-zero instability:** cosine is mathematically most unstable exactly where user disengagement or a skipped test would push values toward zero — the worst possible place for a metric to become unreliable, since it is silently indistinguishable from "not enough information" and can look like a strong match instead of a missing one.

**Euclidean similarity does not have these failure modes** (it correctly penalizes magnitude mismatch and undifferentiated profiles), but it has its own known weakness: it is sensitive to the number of dimensions and to each scale's absolute range, requiring the `√n`-normalization applied here to stay comparable across RIASEC(6)/Work Style(10)/Work Values(8)/Work Environment(5) — a normalization the original M0 draft did not specify at all for a Euclidean alternative.

---

## 4. Spec gap found and fixed (Case 9)

`MNP_GOLDEN_TEST_V0.1.md` §9 defines missing-data handling only for the **user** side of RIASEC ("if more than 1 of 6 letters is unscored... INSUFFICIENT_DATA"). It does not specify the symmetric case where the **career** side is incomplete (a `CareerMatchingProfile` with some RIASEC components `UNSCORED` per Career KB doc §K/§L). This benchmark exposes that gap.

**Fix (applied to the Golden Test doc, §9, amendment):** the INSUFFICIENT_DATA rule is symmetric — if more than 1 of the 6 RIASEC components (or the corresponding fraction for Work Style/Values/Environment) is `UNSCORED` on **either** the user side or the career side, that Fit metric is INSUFFICIENT_DATA for that pairing. It is never computed over a silently-reduced joint subset of scored dimensions on one side while assuming full data on the other.

---

## 5. Band-cutoff sensitivity analysis

Using six illustrative computed InterestFit (cosine) scores across one user's candidate career set: `0.94, 0.85, 0.71, 0.68, 0.52, 0.38`.

| Cutoff variant | HIGH ≥ | LOW < | Resulting bands |
|---|---|---|---|
| A (current Golden Test default) | 0.70 | 0.40 | H, H, H, M, M, L |
| B (−0.05 shift) | 0.65 | 0.35 | H, H, H, **H**, **M**, M |
| C (+0.05 shift) | 0.75 | 0.45 | H, H, **M**, M, M, L |

A mere ±0.05 shift in the cutoff **changes the band of 2 of 6 careers** in this illustrative set (0.68 and 0.38 under variant B; 0.71 under variant C). Because ranking (Golden Test §24) sorts primarily by band tuple before raw score, a band change is not cosmetic — it **reorders the catalog**, moving a career from the middle of the list to the top (or vice versa). This confirms, with an actual demonstration rather than an assertion, that the 0.70/0.40 cutoffs must remain explicitly PROVISIONAL pending Golden Case calibration (as already stated in the Golden Test doc) — this benchmark adds the missing evidence for *why* that caution is warranted, not just that it is.

---

## 6. Recommendation for V0.1

**Do not adopt pure cosine similarity unconditionally.** The evidence above shows it can silently reward exactly the two situations Matching V1 most needs to avoid rewarding: (a) a low-information/disengaged response pattern, and (b) an unmapped or provisional career vector.

**Recommended V0.1 metric: guarded cosine similarity** —
1. Compute cosine similarity as originally specified (Golden Test §17–19) — it remains the right *shape*-comparison tool once both vectors carry real signal, per cases 4, 6, 7 where it performs identically to (or better than) Euclidean.
2. **Before** trusting the cosine result, check a **minimum-dispersion gate** on both vectors: `stdev(vector components) ≥ 0.10` (a placeholder threshold, itself PROVISIONAL and subject to Golden Case calibration). A vector that fails this gate (flat, near-zero, or provisional-default) does not produce a Fit score — it returns **INSUFFICIENT_DATA / LOW_DIFFERENTIATION**, explicitly distinguished in the Compatibility Report from both a computed LOW score and a missing-scale INSUFFICIENT_DATA (Golden Test doc's existing edge-case section).
3. This gate applies **symmetrically** to the user vector and the career vector (fixing the Case 9 gap, §4 above) — a provisional/flat `CareerMatchingProfile` is exactly as disqualifying as a disengaged user response pattern.

**Why not switch to Euclidean outright:** Euclidean has no equivalent failure mode in this benchmark, but it is a less standard, less immediately interpretable metric for a "how similar are these two profiles" narrative in the Compatibility Report, and it does not intrinsically reward the "matching pattern regardless of absolute level" property that is legitimately desirable for genuinely well-differentiated profiles (cases 4, 6, 7 show near-identical behavior anyway). Guarding cosine keeps its good behavior while removing its demonstrated failure modes, rather than trading one metric's weaknesses for another's.

**PROVISIONAL STATUS:** the `stdev ≥ 0.10` gate constant is a placeholder pending Golden Case calibration with real pilot data — this benchmark demonstrates the *need* for a gate and a plausible mechanism, not a final calibrated value.
