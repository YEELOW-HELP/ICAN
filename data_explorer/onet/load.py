"""Load the full O*NET occupational picture into the reference DB.

RAW and normalized values are kept distinct (brief §6): `raw_value` is
O*NET's own number; `normalized_value` is a plain linear rescale of that
scale's official [min,max] to [0,1] and is only computed for the bounded
numeric scales (OI/WI/IM/LV/CX/CT/EX) — category/percentage/rank scales
(RL/RW/OJ/CXP/...) keep `normalized_value = NULL`. A genuinely missing
value is an absent row, never 0.
"""

from __future__ import annotations

import sqlite3

from data_explorer import config
from data_explorer.io import log, read_tab

_DDL = """
CREATE TABLE onet_occupation (
    soc          TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    description  TEXT,
    job_zone     INTEGER
);
CREATE TABLE onet_occupation_title (
    soc    TEXT NOT NULL,
    title  TEXT NOT NULL,
    kind   TEXT NOT NULL            -- 'primary' | 'alternate' | 'reported'
);
CREATE INDEX ix_onet_title ON onet_occupation_title (title);
CREATE INDEX ix_onet_title_soc ON onet_occupation_title (soc);

CREATE TABLE onet_rating (
    soc              TEXT NOT NULL,
    table_key        TEXT NOT NULL,   -- interest / work_style / ability / skill_essential / knowledge / ...
    family           TEXT NOT NULL,   -- Content Model family label
    element_id       TEXT NOT NULL,
    element_name     TEXT NOT NULL,
    scale_id         TEXT NOT NULL,
    category         TEXT,            -- for Work Context / Education / T&E category rows
    raw_value        REAL NOT NULL,
    normalized_value REAL,            -- [0,1] for bounded scales, NULL otherwise
    release_label    TEXT NOT NULL,
    PRIMARY KEY (soc, table_key, element_id, scale_id, category)
);
CREATE INDEX ix_onet_rating_family ON onet_rating (table_key, element_id);

CREATE TABLE onet_work_value (
    soc              TEXT NOT NULL,
    element_id       TEXT NOT NULL,
    element_name     TEXT NOT NULL,
    short_key        TEXT,
    scale_id         TEXT NOT NULL,
    raw_value        REAL NOT NULL,
    normalized_value REAL NOT NULL,
    release_label    TEXT NOT NULL,
    PRIMARY KEY (soc, element_id)
);

CREATE TABLE onet_task (
    task_id    TEXT PRIMARY KEY,
    soc        TEXT NOT NULL,
    task       TEXT NOT NULL,
    task_type  TEXT
);
CREATE INDEX ix_onet_task_soc ON onet_task (soc);
CREATE TABLE onet_task_rating (
    task_id   TEXT NOT NULL,
    scale_id  TEXT NOT NULL,
    category  TEXT,
    raw_value REAL NOT NULL,
    PRIMARY KEY (task_id, scale_id, category)
);

CREATE TABLE onet_software_skill (
    soc               TEXT NOT NULL,
    element_id        TEXT NOT NULL,
    element_name      TEXT NOT NULL,   -- software category, e.g. "Document management software"
    workplace_example TEXT,            -- e.g. "Adobe Acrobat"
    hot_technology    INTEGER NOT NULL,
    in_demand         INTEGER NOT NULL
);
CREATE INDEX ix_onet_sw_soc ON onet_software_skill (soc);

CREATE TABLE onet_related_occupation (
    soc              TEXT NOT NULL,
    related_soc      TEXT NOT NULL,
    relatedness_tier TEXT,
    idx              INTEGER,
    PRIMARY KEY (soc, related_soc)
);

CREATE TABLE onet_dwa (
    gwa_element_id  TEXT NOT NULL,
    iwa_element_id  TEXT NOT NULL,
    dwa_element_id  TEXT NOT NULL,
    dwa_name        TEXT NOT NULL,
    PRIMARY KEY (dwa_element_id)
);
"""


def _norm(scale_id: str, raw: float) -> float | None:
    if scale_id not in config.ONET_SCALE_RANGES:
        return None
    lo, hi = config.ONET_SCALE_RANGES[scale_id]
    return round((raw - lo) / (hi - lo), 6)


def _load_occupations(cur, d) -> None:
    n = 0
    for row in read_tab(d / "Occupation Data.txt"):
        soc = row["O*NET-SOC Code"]
        cur.execute("INSERT INTO onet_occupation (soc, title, description) VALUES (?,?,?)",
                    (soc, row["Title"], row.get("Description")))
        cur.execute("INSERT INTO onet_occupation_title VALUES (?,?, 'primary')", (soc, row["Title"]))
        n += 1
    log(f"  onet_occupation: {n}")

    t = 0
    for fname, kind, col in (("Job Titles.txt", "alternate", "Job Title"),
                             ("Sample of Reported Titles.txt", "reported", "Reported Job Title")):
        p = d / fname
        if not p.exists():
            continue
        for row in read_tab(p):
            title = (row.get(col) or "").strip()
            if title and title != "n/a":
                cur.execute("INSERT INTO onet_occupation_title VALUES (?,?,?)",
                            (row["O*NET-SOC Code"], title, kind))
                t += 1
    log(f"  onet_occupation_title (alt/reported): {t}")

    p = d / "Job Zones.txt"
    for row in read_tab(p):
        cur.execute("UPDATE onet_occupation SET job_zone=? WHERE soc=?",
                    (int(row["Job Zone"]), row["O*NET-SOC Code"]))
    log("  job zones attached")


def _load_rating_table(cur, d, table_key: str, spec: dict, release_label: str) -> None:
    p = d / spec["file"]
    if not p.exists():
        log(f"  ! {spec['file']} missing — skipped ({table_key})")
        return
    scales = spec["scales"]
    has_cat = spec.get("has_category", False)
    cat_keep = spec.get("category_keep")
    n = 0
    for row in read_tab(p):
        sid = row["Scale ID"]
        if sid not in scales:
            continue
        cat = row.get("Category") if has_cat else None
        if cat_keep is not None and cat not in cat_keep:
            continue
        raw = float(row["Data Value"])
        cur.execute(
            "INSERT OR IGNORE INTO onet_rating VALUES (?,?,?,?,?,?,?,?,?,?)",
            (row["O*NET-SOC Code"], table_key, spec["family"], row["Element ID"], row["Element Name"],
             sid, ("" if cat is None else str(cat)), raw, _norm(sid, raw), release_label),
        )
        n += 1
    log(f"  onet_rating[{table_key}]: {n}")


def _load_work_values(cur) -> None:
    d = config.onet_release_dir(config.ONET_WORK_VALUES_RELEASE)
    p = d / "Work Values.txt"
    if not p.exists():
        raise SystemExit(f"Work Values.txt missing from {d}")
    n = 0
    for row in read_tab(p):
        if row["Scale ID"] != "EX":
            continue
        raw = float(row["Data Value"])
        eid = row["Element ID"]
        cur.execute(
            "INSERT OR IGNORE INTO onet_work_value VALUES (?,?,?,?,?,?,?,?)",
            (row["O*NET-SOC Code"], eid, row["Element Name"],
             config.WORK_VALUES_ELEMENTS.get(eid), "EX", raw, _norm("EX", raw),
             config.ONET_WORK_VALUES_LABEL),
        )
        n += 1
    log(f"  onet_work_value (30.2): {n}")


def _load_tasks(cur, d) -> None:
    n = 0
    for row in read_tab(d / "Task Statements.txt"):
        cur.execute("INSERT OR IGNORE INTO onet_task VALUES (?,?,?,?)",
                    (row["Task ID"], row["O*NET-SOC Code"], row["Task"], row.get("Task Type")))
        n += 1
    log(f"  onet_task: {n}")
    r = 0
    p = d / "Task Ratings.txt"
    if p.exists():
        for row in read_tab(p):
            cur.execute("INSERT OR IGNORE INTO onet_task_rating VALUES (?,?,?,?)",
                        (row["Task ID"], row["Scale ID"], str(row.get("Category", "")),
                         float(row["Data Value"])))
            r += 1
    log(f"  onet_task_rating: {r}")


def _load_software(cur, d) -> None:
    p = d / "Software Skills.txt"
    if not p.exists():
        return
    n = 0
    for row in read_tab(p):
        cur.execute(
            "INSERT INTO onet_software_skill VALUES (?,?,?,?,?,?)",
            (row["O*NET-SOC Code"], row["Element ID"], row["Element Name"],
             row.get("Workplace Example"),
             1 if row.get("Hot Technology") == "Y" else 0,
             1 if row.get("In Demand") == "Y" else 0),
        )
        n += 1
    log(f"  onet_software_skill: {n}")


def _load_related(cur, d) -> None:
    p = d / "Related Occupations.txt"
    if not p.exists():
        return
    n = 0
    for row in read_tab(p):
        idx = row.get("Index")
        cur.execute(
            "INSERT OR IGNORE INTO onet_related_occupation VALUES (?,?,?,?)",
            (row["O*NET-SOC Code"], row["Related O*NET-SOC Code"],
             row.get("Relatedness Tier"), int(idx) if idx and idx.isdigit() else None),
        )
        n += 1
    log(f"  onet_related_occupation: {n}")


def _load_dwa(cur, d) -> None:
    p = d / "GWAs to IWAs to DWAs.txt"
    if not p.exists():
        return
    n = 0
    for row in read_tab(p):
        cur.execute("INSERT OR IGNORE INTO onet_dwa VALUES (?,?,?,?)",
                    (row["GWA Element ID"], row["IWA Element ID"],
                     row["DWA Element ID"], row["DWA Element Name"]))
        n += 1
    log(f"  onet_dwa: {n}")


def load(conn: sqlite3.Connection) -> None:
    d = config.onet_release_dir()
    conn.executescript(_DDL)
    cur = conn.cursor()

    _load_occupations(cur, d)
    for table_key, spec in config.ONET_RATING_TABLES.items():
        _load_rating_table(cur, d, table_key, spec, config.ONET_RELEASE_LABEL)
    _load_work_values(cur)
    _load_tasks(cur, d)
    _load_software(cur, d)
    _load_related(cur, d)
    _load_dwa(cur, d)
