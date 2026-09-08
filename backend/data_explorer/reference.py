"""Build the unified DATA EXPLORER reference DB:
    data/data_explorer/reference.sqlite

Contains everything: `onet_*`, `esco_*`, `xwalk_*`, and a `stg_source`
provenance table. Idempotent — drops and recreates from the vendored
source files each run (the downloaded archives are the single source of
truth; there is no incremental state to preserve).
"""

from __future__ import annotations

import datetime as dt
import sqlite3

from data_explorer import config
from data_explorer.crosswalk import load as crosswalk_load
from data_explorer.esco import load as esco_load
from data_explorer.io import log, sha256
from data_explorer.onet import dictionary as onet_dictionary
from data_explorer.onet import load as onet_load

_SOURCE_DDL = """
CREATE TABLE stg_source (
    source_label   TEXT PRIMARY KEY,
    kind           TEXT NOT NULL,
    version        TEXT NOT NULL,
    official_url   TEXT NOT NULL,
    file           TEXT,
    sha256         TEXT,
    downloaded_at  TEXT,
    built_at       TEXT NOT NULL,
    license        TEXT,
    attribution    TEXT NOT NULL
);
"""


def _record_sources(conn: sqlite3.Connection) -> None:
    conn.executescript(_SOURCE_DDL)
    cur = conn.cursor()
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

    def _sha(p):
        return sha256(p) if p.exists() else None

    onet31_zip = config.ONET_VENDOR_DIR / f"db_{config.ONET_RELEASE}_text.zip"
    onet302_zip = config.ONET_VENDOR_DIR / f"db_{config.ONET_WORK_VALUES_RELEASE}_text.zip"
    xwalk = config.CROSSWALK_VENDOR_DIR / "ESCO_to_ONET-SOC.xlsx"

    rows = [
        (config.ONET_RELEASE_LABEL, "onet", "31.0",
         config.ONET_URL.format(release=config.ONET_RELEASE), onet31_zip.name, _sha(onet31_zip),
         None, now, "CC BY 4.0", config.ATTRIBUTION[config.ONET_RELEASE_LABEL]),
        (config.ONET_WORK_VALUES_LABEL, "onet", "30.2",
         config.ONET_URL.format(release=config.ONET_WORK_VALUES_RELEASE), onet302_zip.name, _sha(onet302_zip),
         None, now, "CC BY 4.0", config.ATTRIBUTION[config.ONET_WORK_VALUES_LABEL]),
        (config.CROSSWALK_LABEL, "crosswalk", "onetcenter",
         config.CROSSWALK_URL, xwalk.name, _sha(xwalk),
         None, now, "open", config.ATTRIBUTION[config.CROSSWALK_LABEL]),
    ]
    for lang in config.ESCO_LANGUAGES:
        z = config.ESCO_VENDOR_DIR / f"esco_{config.ESCO_VERSION}_classification_{lang}_csv.zip"
        rows.append((
            f"{config.ESCO_LABEL}_{lang}", "esco", config.ESCO_VERSION,
            config.ESCO_URL.format(version=config.ESCO_VERSION, lang=lang), z.name, _sha(z),
            None, now, "open (free of charge)", config.ATTRIBUTION[config.ESCO_LABEL],
        ))
    cur.executemany("INSERT INTO stg_source VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
    log(f"  stg_source: {len(rows)} datasets recorded")


def build() -> None:
    config.REFERENCE_DB.parent.mkdir(parents=True, exist_ok=True)
    if config.REFERENCE_DB.exists():
        config.REFERENCE_DB.unlink()
    conn = sqlite3.connect(config.REFERENCE_DB)
    try:
        conn.execute("PRAGMA journal_mode=OFF")
        conn.execute("PRAGMA synchronous=OFF")
        log("[1/5] provenance")
        _record_sources(conn)
        log("[2/5] O*NET data dictionary")
        onet_dictionary.load(conn)
        log("[3/5] O*NET occupational data")
        onet_load.load(conn)
        log("[4/5] ESCO classification (en + uk)")
        esco_load.load(conn)
        log("[5/6] official ESCO<->O*NET crosswalk")
        crosswalk_load.load(conn)
        conn.commit()
        log("[6/6] MNP <-> external mapping candidates")
        from data_explorer.explorer import mapping_review
        mapping_review.build(conn)
        _summary(conn)
    finally:
        conn.close()
    log(f"\nbuilt {config.REFERENCE_DB}")


def _summary(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    tables = [r[0] for r in cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    log("\n--- reference.sqlite table row counts ---")
    for t in tables:
        (c,) = cur.execute(f"SELECT count(*) FROM {t}").fetchone()  # noqa: S608 - trusted table names
        log(f"  {t:34} {c:>10,}")
