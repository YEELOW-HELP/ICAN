"""Load O*NET's self-describing metadata into the reference DB and emit a
human-readable data dictionary.

Tables produced:
  onet_content_model   element_id, element_name, description   (the whole taxonomy tree)
  onet_scale           scale_id, scale_name, minimum, maximum  (verbatim Scales Reference)
  onet_scale_anchor    element_id, element_name, scale_id, anchor_value, anchor_description
  onet_category        element_id, element_name, scale_id, category, category_description
"""

from __future__ import annotations

import sqlite3

from data_explorer import config
from data_explorer.io import log, read_tab

_DDL = """
CREATE TABLE onet_content_model (
    element_id    TEXT PRIMARY KEY,
    element_name  TEXT NOT NULL,
    description   TEXT,
    parent_id     TEXT,
    depth         INTEGER
);
CREATE TABLE onet_scale (
    scale_id    TEXT PRIMARY KEY,
    scale_name  TEXT NOT NULL,
    minimum     REAL NOT NULL,
    maximum     REAL NOT NULL
);
CREATE TABLE onet_scale_anchor (
    element_id          TEXT NOT NULL,
    element_name        TEXT,
    scale_id            TEXT NOT NULL,
    anchor_value        REAL NOT NULL,
    anchor_description  TEXT
);
CREATE TABLE onet_category (
    element_id           TEXT NOT NULL,
    element_name         TEXT,
    scale_id             TEXT NOT NULL,
    category             TEXT NOT NULL,
    category_description  TEXT,
    PRIMARY KEY (element_id, scale_id, category)
);
"""


def _parent(element_id: str) -> str | None:
    return element_id.rsplit(".", 1)[0] if "." in element_id else None


def load(conn: sqlite3.Connection) -> None:
    d = config.onet_release_dir()
    conn.executescript(_DDL)
    cur = conn.cursor()

    n = 0
    for row in read_tab(d / "Content Model Reference.txt"):
        eid = row["Element ID"]
        cur.execute(
            "INSERT OR IGNORE INTO onet_content_model VALUES (?,?,?,?,?)",
            (eid, row["Element Name"], row.get("Description"), _parent(eid), eid.count(".")),
        )
        n += 1
    log(f"  onet_content_model: {n}")

    seen_scales: dict[str, tuple[float, float]] = {}
    for row in read_tab(d / "Scales Reference.txt"):
        sid = row["Scale ID"]
        lo, hi = float(row["Minimum"]), float(row["Maximum"])
        seen_scales[sid] = (lo, hi)
        cur.execute("INSERT OR IGNORE INTO onet_scale VALUES (?,?,?,?)", (sid, row["Scale Name"], lo, hi))
    # trust O*NET's own file, abort on a pinned-range disagreement
    for sid, expected in config.ONET_SCALE_RANGES.items():
        if sid in seen_scales and seen_scales[sid] != expected:
            raise SystemExit(
                f"O*NET scale {sid}: pinned {expected} but Scales Reference says {seen_scales[sid]}"
            )
    log(f"  onet_scale: {len(seen_scales)} (pinned ranges verified)")

    anchor_file = d / "Level Scale Anchors.txt"
    if anchor_file.exists():
        n = 0
        for row in read_tab(anchor_file):
            cur.execute(
                "INSERT INTO onet_scale_anchor VALUES (?,?,?,?,?)",
                (row["Element ID"], row.get("Element Name"), row["Scale ID"],
                 float(row["Anchor Value"]), row.get("Anchor Description")),
            )
            n += 1
        log(f"  onet_scale_anchor: {n}")

    n = 0
    for fname in ("Education Categories.txt", "Training and Experience Categories.txt",
                  "Work Context Categories.txt", "Task Categories.txt"):
        p = d / fname
        if not p.exists():
            continue
        for row in read_tab(p):
            cur.execute(
                "INSERT OR IGNORE INTO onet_category VALUES (?,?,?,?,?)",
                (row.get("Element ID", ""), row.get("Element Name"), row.get("Scale ID", ""),
                 str(row.get("Category", "")), row.get("Category Description")),
            )
            n += 1
    log(f"  onet_category: {n}")
