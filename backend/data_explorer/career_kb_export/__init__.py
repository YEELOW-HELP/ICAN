"""MNP Career KB -> MNP_CAREER_KB_V1.xlsx exporter.

The production MNP Career KB (the `mnp_*` tables — `mnp_careers`,
`mnp_career_skill_requirements`, `mnp_career_requirements`,
`mnp_career_tasks`, `mnp_career_relations`, `mnp_external_mappings`,
`mnp_market_snapshots`, ...) is the single source of truth. This module
produces a **read / review / analysis** Excel view of it for the Founder
and methodologist.

Excel is NOT a source of truth and there is NO Excel -> DB path here
(brief §14 — deliberately out of scope). Reuses `data_explorer.mnp_snapshot`
(read-only). No AI. No fabricated market numbers — missing data is a blank
cell / `UNKNOWN`, never `0`.
"""
