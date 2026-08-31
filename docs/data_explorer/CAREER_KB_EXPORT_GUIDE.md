# CAREER KB EXPORT GUIDE — `MNP_CAREER_KB_V1.xlsx`

A human-readable **read / review / analysis** view of the MNP Career
Knowledge Base for the Founder and methodologist.

- The production Career KB (the `mnp_*` tables) is the **single source of
  truth**. This workbook is generated **from** it.
- Excel is **not** a source of truth. There is **no Excel → DB path**
  (deliberately out of scope — we do not want uncontrolled changes to the
  production Career KB). A future flow (Excel → validation → diff/preview
  → human approval → KB) is possible; the sheet shapes are ready for it.
- No AI. `UNKNOWN ≠ 0` — a missing value is a blank cell, never `0`. No
  fabricated market numbers.

## Command

```bash
pip install -r requirements-datalab.txt
python -m data_explorer.cli export-careers-excel
```

Output (always the same path, overwritten):
```
data/data_explorer/exports/MNP_CAREER_KB_V1.xlsx
```
gitignored (a small binary, fully reproducible from the KB).

## Where the data comes from

`data_explorer/mnp_snapshot.py` reads the Career KB **read-only**. Today
the approved KB ships as an in-code seed
(`app/services/career_kb_mnp/seed_alpha.py`, 5 ACTIVE careers); the
snapshot runs it into an ephemeral in-memory SQLite and reads it back.
When a real MNP database is available, set `MNP_DATABASE_URL` and it reads
that instead (still read-only).

| Sheet | Source table(s) |
|---|---|
| `10_CAREERS` | `mnp_careers` + `mnp_career_families` |
| `20_SKILLS` | `mnp_career_skill_requirements` + `mnp_skills` (+ `mnp_external_mappings` for `skill_code`) |
| `30_REQUIREMENTS` | `mnp_career_requirements` |
| `40_RESPONSIBILITIES` | `mnp_career_tasks` |
| `50_CAREER_PATHS` | `mnp_career_relations` |
| `60_PROS_CONS` | *(no entity — empty by design, see the finding)* |
| `70_MARKET_DATA` | `mnp_market_snapshots` + `mnp_salary_snapshots` |
| `80_EXTERNAL_REFS` | `mnp_external_mappings` (entity_type=career) |
| `90_PROVENANCE` | flattened `source` / `source_version` / `confidence` from every row above |

Coverage gaps between the addendum spec and the model are recorded in
`findings/CAREER_KB_ENTITY_COVERAGE_FINDING_V1.md` — no production table
was invented.

## Excel quality

Every data sheet: Excel Table (banded, sortable) · AutoFilter · frozen
header · readable widths · wrap-text notes · header formatting.
`review_status` columns have dropdowns. `00_README` carries `generated_at`
and `dataset_version`. No VBA, no macros.

## Determinism

Given the same source data, the export is byte-identical. The only
non-deterministic cells are `00_README`'s `generated_at` date and — when
the source is a *fresh* in-memory seed — the row UUIDs in `entity_id`
columns and `10_CAREERS.updated_at` (a wall-clock server default). A real
MNP DB has stable ids, so a real export is fully deterministic.

## Scaling (5 → 50 → 500+)

One Career KB serves three consumers: the **website** (DB → API →
frontend), this **Excel** view, and the **Matching Engine**. As the
catalogue grows, this exporter needs no change — it reads whatever ACTIVE
careers the KB holds. The finding lists the entities to add to the model
when pros/cons, ordered career-path steps, and real market data are
needed.
