"""Per-dimension distribution / coverage / discriminative-power metrics
over `onet_rating` (and, by the same shape, `onet_work_value`).

`discriminative_power` here = stdev of an element's normalized value
*across occupations* — how much that dimension actually separates jobs.
A dimension that is ~constant across all occupations cannot drive a
matching result, no matter how it is weighted.
"""

from __future__ import annotations

import sqlite3
import statistics
from dataclasses import dataclass

from data_explorer import config


@dataclass(frozen=True)
class DimensionStat:
    table_key: str
    element_id: str
    element_name: str
    scale_id: str
    n_occupations: int          # occupations with a real value
    total_occupations: int      # occupations in the family's population
    coverage: float             # n / total
    mean: float | None
    stdev: float | None         # across occupations = discriminative power
    variance: float | None
    minimum: float | None
    maximum: float | None
    selected_by_mnp: bool

    @property
    def missingness(self) -> float:
        return round(1.0 - self.coverage, 4)


def _population(cur, table_key: str) -> int:
    (n,) = cur.execute(
        "SELECT count(DISTINCT soc) FROM onet_rating WHERE table_key = ?", (table_key,)
    ).fetchone()
    return n


def family_stats(conn: sqlite3.Connection, table_key: str, *, scale_id: str | None = None) -> list[DimensionStat]:
    cur = conn.cursor()
    total = _population(cur, table_key)
    selected = set(config.MNP_SELECTED_ONET.get(table_key, []))

    q = (
        "SELECT element_id, element_name, scale_id, "
        "       COALESCE(normalized_value, raw_value) AS v "
        "FROM onet_rating WHERE table_key = ?"
    )
    args: list = [table_key]
    if scale_id:
        q += " AND scale_id = ?"
        args.append(scale_id)

    buckets: dict[tuple[str, str, str], list[float]] = {}
    for eid, ename, sid, v in cur.execute(q, args):
        if v is None:
            continue
        buckets.setdefault((eid, ename, sid), []).append(float(v))

    out: list[DimensionStat] = []
    for (eid, ename, sid), vals in sorted(buckets.items()):
        n = len(vals)
        sd = statistics.pstdev(vals) if n > 1 else None
        out.append(DimensionStat(
            table_key=table_key, element_id=eid, element_name=ename, scale_id=sid,
            n_occupations=n, total_occupations=total,
            coverage=round(n / total, 4) if total else 0.0,
            mean=round(statistics.fmean(vals), 4) if vals else None,
            stdev=round(sd, 4) if sd is not None else None,
            variance=round(statistics.pvariance(vals), 5) if n > 1 else None,
            minimum=round(min(vals), 4), maximum=round(max(vals), 4),
            selected_by_mnp=(eid in selected),
        ))
    return out


def work_style_full_vs_selected(conn: sqlite3.Connection) -> dict:
    """The brief §14 comparison: ALL O*NET Work Style elements vs the ~4
    the MNP matching engine currently selects."""
    stats = family_stats(conn, "work_style", scale_id="WI")
    sel = [s for s in stats if s.selected_by_mnp]
    rest = [s for s in stats if not s.selected_by_mnp]

    def _avg(xs, attr):
        vals = [getattr(x, attr) for x in xs if getattr(x, attr) is not None]
        return round(statistics.fmean(vals), 4) if vals else None

    return {
        "all_elements": stats,
        "n_all": len(stats),
        "n_selected": len(sel),
        "mean_discriminative_power_all": _avg(stats, "stdev"),
        "mean_discriminative_power_selected": _avg(sel, "stdev"),
        "mean_discriminative_power_unselected": _avg(rest, "stdev"),
        "mean_coverage_all": _avg(stats, "coverage"),
        "most_discriminative": sorted(stats, key=lambda s: s.stdev or 0, reverse=True)[:6],
        "least_discriminative": sorted(stats, key=lambda s: s.stdev or 0)[:6],
    }
