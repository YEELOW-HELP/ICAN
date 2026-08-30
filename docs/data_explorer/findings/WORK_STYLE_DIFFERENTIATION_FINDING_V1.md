# METHODOLOGY_FINDING — Work Style differentiation (O*NET, brief §14)

**Type:** research finding. **Raised by:** MNP DATA EXPLORER V1. **Date:** 2026-08-30. **Production code unchanged.**

## FACTS

- O*NET 31.0 exposes **21 Work Style elements** (scale `WI`, −3…+3). The prior MNP matching workstream selected **5** of them (`leadership`, `initiative`, `ambiguity_tolerance`, + a `social`+`cooperation` composite).
- A known problem (from the prior workstream's M4.6 pass): the 4-element MNP Work Style career vector often fails the guarded-cosine differentiation check — its spread across occupations is too small.

## DATA — discriminative power (stdev of the normalised value across occupations)

| set | elements | mean coverage | mean discriminative power |
|---|---|---|---|
| ALL O*NET Work Styles | 21 | 1.0 | **0.1181** |
| MNP-selected (5) | 5 | — | **0.1404** |
| the other 16 | 16 | — | **0.1111** |

### Most discriminative Work Style elements (across all occupations)

| element | id | coverage | mean | stdev (discriminative power) | MNP-selected? |
|---|---|---|---|---|---|
| Innovation | `1.D.1.a` | 1.0 | 0.6273 | **0.1663** | no |
| Leadership Orientation | `1.D.1.i` | 1.0 | 0.6134 | **0.1642** | yes |
| Intellectual Curiosity | `1.D.1.c` | 1.0 | 0.6899 | **0.1628** | no |
| Social Orientation | `1.D.2.f` | 1.0 | 0.6659 | **0.1627** | yes |
| Empathy | `1.D.2.c` | 1.0 | 0.6339 | **0.1578** | no |
| Tolerance for Ambiguity | `1.D.1.d` | 1.0 | 0.6095 | **0.1446** | yes |

### Least discriminative

| element | id | coverage | mean | stdev | MNP-selected? |
|---|---|---|---|---|---|
| Dependability | `1.D.3.c` | 1.0 | 0.9068 | 0.0476 | no |
| Attention to Detail | `1.D.3.b` | 1.0 | 0.8888 | 0.0804 | no |
| Perseverance | `1.D.1.h` | 1.0 | 0.7525 | 0.083 | no |
| Self-Confidence | `1.D.1.g` | 1.0 | 0.7029 | 0.0947 | no |
| Stress Tolerance | `1.D.4.a` | 1.0 | 0.7455 | 0.0973 | no |
| Humility | `1.D.2.a` | 1.0 | 0.5663 | 0.0985 | no |

## RESULT

The full Work Style table's mean discriminative power is **0.1181**; the MNP-selected subset's is **0.1404**. The selected subset is at least as discriminative as the table average.

## INTERPRETATION

O*NET Work Styles `WI` (impact-on-performance) values are compressed for most occupations — the domain genuinely does not separate jobs as strongly as Interests (`OI`) does. Adding elements helps only if the *added* elements carry spread.

## OPTIONS

1. Keep 4 elements; accept that Work Style Fit is often `INSUFFICIENT`/`LOW_DIFFERENTIATION` and lean on Interest + Feasibility.
2. Expand the selected set to the most-discriminative elements above (data-driven, still O*NET-native).
3. Use a per-family differentiation threshold tuned to each domain's real spread.
4. Treat Work Style as a *secondary* signal only (consistent with Founder Decision #22 for RIASEC).

## RECOMMENDATION

Do **not** change the guard threshold or weights in production. Put options 2 + 3 in front of the Founder with this table. If expanding the set: prefer the elements marked 'no' in *Most discriminative* above. Re-run this finding after any O*NET release bump.

*(Generated from `data/data_explorer/reference.sqlite`. Rebuild + re-run: `python -m data_explorer.cli build && python -m data_explorer.cli analysis`.)*
