# MNP DATA EXPLORER V1

A **research / data-lab** layer for «МОЖУ: Мій Напрям». It is *not* a
production feature — it exists so the Founder, methodologist and developer
can look at the real ESCO and O*NET data with their own eyes, compare the
two, decide what MNP should use, hand-build MNP Career Profiles and Person
Profiles, hand-compare Person ↔ Career, record Human Expected Results, and
export a Golden Dataset + a human-readable Excel workbook.

## Hard rules

- **Dependency direction is one-way:** `data_explorer → app.db.models_*`
  (read-only). The production MNP runtime never imports `data_explorer`.
- **No AI anywhere here** — no LLM, no AI mapping/classification/summaries.
- **No Ukrainian market layer**, no Lightcast, no WEF, no scraping. Only
  O*NET + ESCO + their official crosswalk (+ ISCO where it is already a
  key of those datasets).
- External ids are never MNP primary ids (Founder Decision #16).
- `UNKNOWN != ABSENT`; a missing numeric value is never treated as `0`.
- This module **never edits approved methodology**. A data-driven problem
  with the methodology becomes a `findings/*.md` document for the Founder
  to decide on.

## Two deliverable forms

| Form | What |
|---|---|
| **A. Code module** | `data_explorer/` — reproducible ETL + analysis + human-lab + exporters |
| **B. Excel workbook** | `data/data_explorer/exports/MNP_ESCO_ONET_DATA_EXPLORER.xlsx` — the working tool for a non-coder (BLOCK 3) |

## Layout

```
data_explorer/
  config.py            version pins, paths, provenance, O*NET element maps
  io.py                downloads (sha256, idempotent), tab/csv/xlsx readers
  onet/                O*NET importer: download, dictionary, load (full occupational picture)
  esco/                ESCO importer: download, load (en + uk)
  crosswalk/           official ESCO↔O*NET crosswalk: download, load
  reference.py         builds data/data_explorer/reference.sqlite (unified)
  docs_gen/            generators for the data dictionaries + source inventory
  analysis/            dimension analysis + data-quality report          (BLOCK 2)
  human_lab/           Person Profile, Career Comparison, Expected Result, Golden export  (BLOCK 2)
  excel/               MNP_ESCO_ONET_DATA_EXPLORER.xlsx generator        (BLOCK 3)
  cli.py               python -m data_explorer.cli <command>

docs/data_explorer/    this folder — README, dictionaries, mapping spec, findings
data/data_explorer/    GITIGNORED — vendored source archives, reference.sqlite, exports, human-lab inputs
```

## Quick start

```bash
pip install -r requirements-datalab.txt
python -m data_explorer.cli download      # O*NET 31.0 + 30.2, ESCO v1.2.1 (en+uk), official crosswalk
python -m data_explorer.cli build         # -> data/data_explorer/reference.sqlite
python -m data_explorer.cli dictionary    # regenerate ONET/ESCO_DATA_DICTIONARY.md from the DB
python -m data_explorer.cli inventory     # regenerate SOURCE_DATA_INVENTORY.md
```

## Datasets (see `SOURCE_DATA_INVENTORY.md` for the full table)

| Source | Version | Licence | Ukrainian? |
|---|---|---|---|
| O*NET | **31.0** (Aug 2026) | CC BY 4.0 | no |
| O*NET Work Values | **30.2** (last release with `Work Values.txt`) | CC BY 4.0 | — |
| ESCO | **v1.2.1** | free / open | **yes** (`uk`, by the ETF) |
| ESCO↔O*NET crosswalk | O*NET Resource Center (AI + human validated) | open | — |

## Source of truth

Approved methodology lives in `docs/mnp_v1/` (this branch, from
`mnp-v1-implementation`). Where an approved schema doc is missing as a
file, the effective schema is the code in
`app/db/models_career_kb_mnp.py` / `models_career_card.py` /
`models_matching_mnp.py` — see `findings/MISSING_APPROVED_DOCS_FINDING_V1.md`.

## Git

Branch `mnp-data-explorer-v1`, off `mnp-v1-implementation`. Reuses the
O*NET download / tab-reader / scale-validation logic from commit
`6d27bf3` (prior data-foundation workstream). **Founder merges — this
branch opens a PR and stops.**
