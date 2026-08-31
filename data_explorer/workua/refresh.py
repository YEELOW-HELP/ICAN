"""`refresh-workua-career-inventory` -- re-crawl the Work.ua Career Guide,
diff against the previous snapshot, REPORT.

This never edits, adds, or archives an MNP Career. Work.ua is not the MNP
master taxonomy (Founder brief §28): a profession disappearing from
Work.ua does NOT archive the MNP Career -- it only shows up in the diff
for a human curation decision.
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from pathlib import Path

from data_explorer.workua import inventory as inv


@dataclass
class InventoryDiff:
    snapshot_date: str
    previous_date: str | None
    current_count: int
    previous_count: int | None
    new: list[inv.WorkuaProfession]
    removed: list[inv.WorkuaProfession]
    unchanged: list[inv.WorkuaProfession]
    snapshot_path: Path

    def as_report(self) -> str:
        lines = [
            "WORK.UA CAREER GUIDE -- INVENTORY REFRESH",
            f"  snapshot date     : {self.snapshot_date}",
            f"  snapshot file     : {self.snapshot_path}",
            f"  current count     : {self.current_count}",
        ]
        if self.previous_date:
            lines += [
                f"  previous snapshot : {self.previous_date} ({self.previous_count})",
                f"  NEW ON WORK.UA    : {len(self.new)}",
                *[f"      + {p.title_uk}  ({p.slug})" for p in self.new],
                f"  REMOVED           : {len(self.removed)}",
                *[f"      - {p.title_uk}  ({p.slug})" for p in self.removed],
                f"  UNCHANGED         : {len(self.unchanged)}",
                "",
                "Next step is a HUMAN curation decision in the Career KB Editor.",
                "This command changed nothing in the Career KB.",
            ]
        else:
            lines.append("  (first snapshot -- no previous inventory to diff against)")
        return "\n".join(lines)


def run(*, write: bool = True, fetch=inv._fetch) -> InventoryDiff:
    professions = inv.crawl(fetch=fetch)
    today = dt.date.today().isoformat()

    prev_path = inv.latest_snapshot()
    prev = inv.load_snapshot(prev_path) if prev_path else []
    prev_slugs = {p.slug for p in prev}
    cur_slugs = {p.slug for p in professions}

    new = [p for p in professions if p.slug not in prev_slugs]
    removed = [p for p in prev if p.slug not in cur_slugs]
    unchanged = [p for p in professions if p.slug in prev_slugs]

    snap_path = inv.snapshot_path(today)
    if write:
        inv.write_snapshot(professions, date=today)
        meta = {
            "source": "WORK_UA_CAREER_GUIDE",
            "source_url": inv.CAREER_GUIDE_URL,
            "discovered_at": today,
            "profession_count": len(professions),
            "page_count": max(p.page for p in professions),
        }
        snap_path.with_suffix(".meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    return InventoryDiff(
        snapshot_date=today,
        previous_date=(prev_path.stem.replace("workua_career_inventory_", "") if prev_path else None),
        current_count=len(professions),
        previous_count=(len(prev) if prev_path else None),
        new=new, removed=removed, unchanged=unchanged, snapshot_path=snap_path,
    )
