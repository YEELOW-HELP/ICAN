# EXCEL DATA EXPLORER GUIDE

`MNP_ESCO_ONET_DATA_EXPLORER.xlsx` — the working tool for the Founder and
methodologist to explore the real ESCO + O*NET data without touching code.

## Get / rebuild it

```bash
pip install -r requirements-datalab.txt
python -m data_explorer.cli download     # once
python -m data_explorer.cli build        # (re)build reference.sqlite
python -m data_explorer.cli analysis     # refresh the analysis + findings
python -m data_explorer.cli golden       # (re)export the golden fixtures
python -m data_explorer.cli excel        # -> data/data_explorer/exports/MNP_ESCO_ONET_DATA_EXPLORER.xlsx
```

The workbook is **generated and gitignored** (it is a ~1.5 MB binary
rebuilt from the DB). No VBA, no macros, no external-API dependency when
opened — it works offline.

Every data sheet is a real **Excel Table** (banded, sortable) with
**AutoFilter** and a **frozen header row**. Human-entry sheets have
**dropdowns**.

## Sheets

| sheet | what | how to use |
|---|---|---|
| `00_README` | orientation + rules | read first |
| `01_SOURCES` / `02_SOURCE_VERSIONS` | every dataset, version, sha256, licence, attribution | provenance check |
| `10_MNP_CAREERS` | the MNP Career KB (5 ACTIVE alpha careers): skills, requirements, MNP-curated attributes, external mappings | `external_mappings` shows `(UNMAPPED)` — candidates are on `50_MAPPING_REVIEW` |
| `11_ESCO_OCCUPATIONS` | full ESCO catalogue, en + uk, essential/optional skill counts | filter by `isco_group` |
| `12_ONET_OCCUPATIONS` | full O*NET catalogue, job zone, row counts | |
| `13_CAREER_CROSSWALK` | the official ESCO↔O*NET-SOC crosswalk | filter by `onet_soc` or `esco_isco_code` |
| `20_ONET_RATINGS` | **ALL** O*NET dimensions for the focus occupations (RAW **and** normalized) | filter `table_key` = interest / work_style / ability / skill_essential / skill_transferable / knowledge / work_activity / work_context / education / training_experience. **Blank `normalized_value` = category scale. Blank row = UNKNOWN, never 0.** |
| `22_ONET_WORK_STYLES_FULL` | all 21 O*NET Work Styles + discriminative power, MNP-selected flag | the data behind `findings/WORK_STYLE_DIFFERENTIATION_FINDING_V1.md` |
| `23_ESCO_OCC_SKILLS` | ESCO occupation↔skill (essential/optional), en + uk, for the focus occupations | candidate MNP skill requirements |
| `40_CAREER_EXPLORER` | **filter `mnp_career`** → identity + mapping candidates + which O*NET dimensions MNP USES vs IGNORES | SOURCE FACT vs MNP INTERPRETATION on one screen |
| `41_DIMENSION_ANALYSIS` | per-dimension coverage / mean / stdev / discriminative power | research metrics only — never changes methodology |
| `42_DATA_QUALITY` | the quality checks; any `error` with count > 0 blocks Golden use | |
| `50_MAPPING_REVIEW` | MNP↔external mapping **candidates** — set `review_state` + `proposed_mapping_type` from the dropdowns | **candidates only**; `exact` may only be set by a human who read both concept definitions; nothing is auto-written to `MnpExternalMapping` |
| `55_PERSON_PROFILE_TEMPLATE` / `58_EXPECTED_RESULT_TEMPLATE` | scratch pads with dropdowns | the canonical authoring format is YAML — see `HUMAN_CLASSIFICATION_GUIDE.md` |
| `60_GOLDEN_EXPORT` | the exported Human Expected Results | full fixtures are the JSON files in `evals/golden_data_explorer/` |

## Focus set

`20_ONET_RATINGS` and `23_ESCO_OCC_SKILLS` are scoped to the occupations
that any `50_MAPPING_REVIEW` candidate points at (~30 O*NET + ~15 ESCO)
so the workbook stays a *tool*, not a 400 000-row dump. The full data is
always in `data/data_explorer/reference.sqlite` — query it directly with
any SQLite browser for anything the workbook doesn't show.

## Rules baked in

- **UNKNOWN ≠ 0** — a missing value is a blank cell / absent row.
- **No AI** anywhere in how this workbook is built.
- **No Ukrainian market data, no Lightcast** — out of scope for V1.
- The workbook is **read-only for the data**; only `50_MAPPING_REVIEW` and
  the two template sheets are meant to be typed into, and even then
  nothing flows back to production automatically.
