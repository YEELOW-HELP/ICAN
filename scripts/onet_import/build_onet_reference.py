"""Parse the official O*NET bulk text files into a single local reference
DB: data/onet/onet_reference.sqlite (gitignored, rebuilt from scripts).

All ~1000 O*NET-SOC occupations, every scale the four Matching V1 vector
families use, plus the alternate-title corpus the crosswalk suggester
needs. Nothing is interpreted or AI-reconstructed — this is a faithful,
filtered transcription of O*NET's own rows.

Idempotent: drops and recreates its tables each run (the source zips are
the single source of truth; there is no incremental state to preserve).

Usage:
    python -m scripts.onet_import.build_onet_reference
"""

from __future__ import annotations

import datetime as dt
import sqlite3
import sys

from scripts.onet_import.common import (
    LIVE_RELEASE,
    LIVE_RELEASE_LABEL,
    REFERENCE_DB,
    RIASEC_ELEMENTS,
    SCALE_RANGES,
    WORK_CONTEXT_ELEMENTS,
    WORK_STYLE_ELEMENTS,
    WORK_VALUES_ELEMENTS,
    WORK_VALUES_RELEASE,
    WORK_VALUES_RELEASE_LABEL,
    find_release_dir,
    log,
    read_tab_file,
)

_SCHEMA = """
CREATE TABLE stg_source (
    release_label   TEXT PRIMARY KEY,
    release         TEXT NOT NULL,
    built_at        TEXT NOT NULL
);
CREATE TABLE onet_occupation (
    soc          TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    description  TEXT,
    job_zone     INTEGER
);
CREATE TABLE onet_occupation_title (
    soc    TEXT NOT NULL,
    title  TEXT NOT NULL,
    kind   TEXT NOT NULL          -- 'primary' | 'alternate' | 'reported'
);
CREATE INDEX ix_title_norm ON onet_occupation_title (title);
-- One unified table for every numeric scale value the seed consumes.
CREATE TABLE onet_scale_value (
    soc            TEXT NOT NULL,
    family         TEXT NOT NULL,   -- 'riasec' | 'work_style' | 'work_context' | 'work_values'
    raw_key        TEXT NOT NULL,   -- R.. / leadership / collaboration_social / setting / independence_value ..
    element_id     TEXT NOT NULL,
    element_name   TEXT NOT NULL,
    scale_id       TEXT NOT NULL,   -- OI / WI / CX / CT / EX
    raw_value      REAL NOT NULL,
    release_label  TEXT NOT NULL,
    PRIMARY KEY (soc, family, raw_key)
);
CREATE INDEX ix_scale_family ON onet_scale_value (family);
CREATE TABLE onet_job_zone_reference (
    job_zone     INTEGER PRIMARY KEY,
    name         TEXT,
    education    TEXT,
    experience   TEXT,
    training     TEXT
);
"""


def _assert_scale_ranges(release_dir) -> None:
    """Trust O*NET's own Scales Reference.txt, never the data — abort if a
    pinned range disagrees."""
    seen: dict[str, tuple[float, float]] = {}
    for row in read_tab_file(release_dir / "Scales Reference.txt"):
        seen[row["Scale ID"]] = (float(row["Minimum"]), float(row["Maximum"]))
    for scale_id, expected in SCALE_RANGES.items():
        if scale_id in seen and seen[scale_id] != expected:
            raise SystemExit(
                f"Scale range mismatch for {scale_id}: pinned {expected}, "
                f"O*NET Scales Reference says {seen[scale_id]}. Refusing to build."
            )
    log(f"  scale ranges verified against Scales Reference.txt ({len(seen)} scales)")


def _load_occupations(cur, release_dir) -> None:
    n = 0
    for row in read_tab_file(release_dir / "Occupation Data.txt"):
        cur.execute(
            "INSERT INTO onet_occupation (soc, title, description) VALUES (?, ?, ?)",
            (row["O*NET-SOC Code"], row["Title"], row.get("Description")),
        )
        cur.execute(
            "INSERT INTO onet_occupation_title (soc, title, kind) VALUES (?, ?, 'primary')",
            (row["O*NET-SOC Code"], row["Title"]),
        )
        n += 1
    log(f"  occupations: {n}")


def _load_titles(cur, release_dir) -> None:
    n = 0
    for fname, kind, col in (
        ("Job Titles.txt", "alternate", "Job Title"),
        ("Sample of Reported Titles.txt", "reported", "Reported Job Title"),
    ):
        path = release_dir / fname
        if not path.exists():
            continue
        for row in read_tab_file(path):
            title = row.get(col) or row.get("Alternate Title") or ""
            if not title or title == "n/a":
                continue
            cur.execute(
                "INSERT INTO onet_occupation_title (soc, title, kind) VALUES (?, ?, ?)",
                (row["O*NET-SOC Code"], title, kind),
            )
            n += 1
    log(f"  alternate/reported titles: {n}")


def _load_job_zones(cur, release_dir) -> None:
    for row in read_tab_file(release_dir / "Job Zones.txt"):
        cur.execute(
            "UPDATE onet_occupation SET job_zone = ? WHERE soc = ?",
            (int(row["Job Zone"]), row["O*NET-SOC Code"]),
        )
    ref = release_dir / "Job Zone Reference.txt"
    if ref.exists():
        for row in read_tab_file(ref):
            cur.execute(
                "INSERT OR REPLACE INTO onet_job_zone_reference "
                "(job_zone, name, education, experience, training) VALUES (?, ?, ?, ?, ?)",
                (
                    int(row["Job Zone"]),
                    row.get("Name"),
                    row.get("Education"),
                    row.get("Experience"),
                    row.get("Job Training"),
                ),
            )
    log("  job zones loaded")


def _insert_scale(cur, soc, family, raw_key, element_id, element_name, scale_id, raw_value, label) -> None:
    cur.execute(
        "INSERT OR IGNORE INTO onet_scale_value "
        "(soc, family, raw_key, element_id, element_name, scale_id, raw_value, release_label) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (soc, family, raw_key, element_id, element_name, scale_id, float(raw_value), label),
    )


def _load_riasec(cur, release_dir, label) -> None:
    n = 0
    for row in read_tab_file(release_dir / "Career Interest Types.txt"):
        if row["Scale ID"] != "OI" or row["Element ID"] not in RIASEC_ELEMENTS:
            continue
        _insert_scale(
            cur, row["O*NET-SOC Code"], "riasec", RIASEC_ELEMENTS[row["Element ID"]],
            row["Element ID"], row["Element Name"], "OI", row["Data Value"], label,
        )
        n += 1
    log(f"  riasec (OI) values: {n}")


def _load_work_styles(cur, release_dir, label) -> None:
    n = 0
    for row in read_tab_file(release_dir / "Work Styles.txt"):
        if row["Scale ID"] != "WI" or row["Element ID"] not in WORK_STYLE_ELEMENTS:
            continue
        _insert_scale(
            cur, row["O*NET-SOC Code"], "work_style", WORK_STYLE_ELEMENTS[row["Element ID"]],
            row["Element ID"], row["Element Name"], "WI", row["Data Value"], label,
        )
        n += 1
    log(f"  work_style (WI) values: {n}")


def _load_work_context(cur, release_dir, label) -> None:
    wanted = {eid: (key, scale) for key, (eid, scale) in WORK_CONTEXT_ELEMENTS.items()}
    n = 0
    for row in read_tab_file(release_dir / "Work Context.txt"):
        eid = row["Element ID"]
        if eid not in wanted or row.get("Category", "n/a") != "n/a":
            continue
        key, expected_scale = wanted[eid]
        if row["Scale ID"] != expected_scale:
            continue
        _insert_scale(
            cur, row["O*NET-SOC Code"], "work_context", key,
            eid, row["Element Name"], row["Scale ID"], row["Data Value"], label,
        )
        n += 1
    log(f"  work_context (CX/CT) values: {n}")


def _load_work_values(cur, release_dir, label) -> None:
    path = release_dir / "Work Values.txt"
    if not path.exists():
        raise SystemExit(f"Work Values.txt missing from {release_dir} — wrong release pinned?")
    n = 0
    for row in read_tab_file(path):
        if row["Scale ID"] != "EX" or row["Element ID"] not in WORK_VALUES_ELEMENTS:
            continue
        _insert_scale(
            cur, row["O*NET-SOC Code"], "work_values", WORK_VALUES_ELEMENTS[row["Element ID"]],
            row["Element ID"], row["Element Name"], "EX", row["Data Value"], label,
        )
        n += 1
    log(f"  work_values (EX, {label}): {n}")


def main() -> int:
    live_dir = find_release_dir(LIVE_RELEASE)
    wv_dir = find_release_dir(WORK_VALUES_RELEASE)
    log(f"live release  : {live_dir}")
    log(f"work-values   : {wv_dir}")

    _assert_scale_ranges(live_dir)

    REFERENCE_DB.parent.mkdir(parents=True, exist_ok=True)
    if REFERENCE_DB.exists():
        REFERENCE_DB.unlink()
    conn = sqlite3.connect(REFERENCE_DB)
    try:
        conn.executescript(_SCHEMA)
        cur = conn.cursor()
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        cur.execute(
            "INSERT INTO stg_source VALUES (?, ?, ?)", (LIVE_RELEASE_LABEL, LIVE_RELEASE, now)
        )
        cur.execute(
            "INSERT INTO stg_source VALUES (?, ?, ?)",
            (WORK_VALUES_RELEASE_LABEL, WORK_VALUES_RELEASE, now),
        )

        _load_occupations(cur, live_dir)
        _load_titles(cur, live_dir)
        _load_job_zones(cur, live_dir)
        _load_riasec(cur, live_dir, LIVE_RELEASE_LABEL)
        _load_work_styles(cur, live_dir, LIVE_RELEASE_LABEL)
        _load_work_context(cur, live_dir, LIVE_RELEASE_LABEL)
        _load_work_values(cur, wv_dir, WORK_VALUES_RELEASE_LABEL)

        conn.commit()

        (occ,) = cur.execute("SELECT count(*) FROM onet_occupation").fetchone()
        (sv,) = cur.execute("SELECT count(*) FROM onet_scale_value").fetchone()
        by_family = cur.execute(
            "SELECT family, count(*) FROM onet_scale_value GROUP BY family ORDER BY family"
        ).fetchall()
        log(f"\nbuilt {REFERENCE_DB}")
        log(f"  occupations   : {occ}")
        log(f"  scale values  : {sv}  {dict(by_family)}")
    finally:
        conn.close()

    log("\nnext: python -m scripts.onet_import.export_source_artifact")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
