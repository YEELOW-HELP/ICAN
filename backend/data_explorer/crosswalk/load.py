"""Load the official ESCO<->O*NET-SOC crosswalk into the reference DB and
resolve each ESCO/ISCO code to a real ESCO occupation URI where possible.
"""

from __future__ import annotations

import sqlite3

from data_explorer import config
from data_explorer.io import log, read_xlsx_rows

_DDL = """
CREATE TABLE xwalk_esco_onet (
    esco_isco_code    TEXT NOT NULL,   -- ESCO code (e.g. '0110.10') or ISCO 4-digit group code
    esco_isco_title   TEXT,
    esco_occupation_uri TEXT,          -- resolved from esco_occupation.code where possible
    onet_soc          TEXT NOT NULL,   -- O*NET-SOC 2019
    onet_title        TEXT,
    code_level        TEXT NOT NULL,   -- 'esco_occupation' | 'isco_group'
    mapping_relation  TEXT NOT NULL,   -- always 'unspecified' for this flat file (see module docstring)
    source_label      TEXT NOT NULL,
    PRIMARY KEY (esco_isco_code, onet_soc)
);
CREATE INDEX ix_xwalk_esco ON xwalk_esco_onet (esco_occupation_uri);
CREATE INDEX ix_xwalk_onet ON xwalk_esco_onet (onet_soc);
"""

_HEADER = "ESCO/ISCO Code"


def load(conn: sqlite3.Connection) -> None:
    path = config.CROSSWALK_VENDOR_DIR / "ESCO_to_ONET-SOC.xlsx"
    if not path.exists():
        raise SystemExit(f"{path} not found — run: python -m data_explorer.cli download")
    conn.executescript(_DDL)
    cur = conn.cursor()

    # esco_occupation.code -> uri  (needs esco.load to have run first)
    code_to_uri: dict[str, str] = {}
    try:
        for code, uri in cur.execute(
            "SELECT code, uri FROM esco_occupation WHERE code IS NOT NULL AND code <> ''"
        ):
            code_to_uri[str(code)] = uri
    except sqlite3.OperationalError:
        log("  ! esco_occupation table not present — crosswalk URIs left unresolved")

    n = matched = 0
    past_header = False
    for vals in read_xlsx_rows(path):
        # the workbook has 2 title rows + a blank before the real header
        if not past_header:
            if vals and _HEADER in (str(vals[0]) if vals[0] else ""):
                past_header = True
            continue
        if len(vals) < 4 or not vals[0] or not vals[2]:
            continue
        esco_code, esco_title, onet_soc, onet_title = (str(vals[0]).strip(), vals[1], str(vals[2]).strip(), vals[3])
        uri = code_to_uri.get(esco_code)
        if uri:
            matched += 1
        cur.execute(
            "INSERT OR IGNORE INTO xwalk_esco_onet VALUES (?,?,?,?,?,?,?,?)",
            (esco_code, esco_title, uri, onet_soc, onet_title,
             "esco_occupation" if "." in esco_code else "isco_group",
             "unspecified", config.CROSSWALK_LABEL),
        )
        n += 1
    log(f"  xwalk_esco_onet: {n} pairs ({matched} resolved to an ESCO occupation URI)")
