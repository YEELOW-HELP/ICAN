"""Emit the committed, scoped O*NET source artifact the offline `career_kb`
seed consumes:  app/services/career_kb/onet_source_v3.json

"Scoped" = one record per O*NET-SOC code that an MNP career actually maps
to (today: the 24-Alpha crosswalk in `onet_alpha_fixture.py`; the scope
auto-widens as `CareerExternalMapping` rows are added and this script is
re-run). This keeps the committed file small and keeps CI network-free
(Founder Review "M3" §18) — the full ~1000-occupation reference stays in
the gitignored data/onet/onet_reference.sqlite for crosswalk work.

Deterministic: same reference DB + same crosswalk -> byte-identical JSON
(sorted keys, fixed float formatting).

Usage:
    python -m scripts.onet_import.export_source_artifact
"""

from __future__ import annotations

import datetime as dt
import json
import sqlite3
import sys

from app.services.career_kb.onet_alpha_fixture import load_onet_source
from scripts.onet_import.common import (
    LIVE_RELEASE_LABEL,
    REFERENCE_DB,
    SCOPED_SOURCE_ARTIFACT,
    WORK_VALUES_RELEASE_LABEL,
    log,
)

ARTIFACT_VERSION = "onet_source_v3"


def _mapped_soc_codes() -> list[str]:
    """Every O*NET-SOC code referenced by the current crosswalk, sorted &
    de-duplicated. `community_outreach_coordinator` contributes none
    (deliberately UNMAPPED)."""
    codes: set[str] = set()
    for record in load_onet_source():
        for occ in record.onet_occupations:
            codes.add(occ.soc_code)
    return sorted(codes)


def _round(v: float) -> float:
    return round(float(v), 4)


def _occupation_record(conn: sqlite3.Connection, soc: str) -> dict:
    row = conn.execute(
        "SELECT title, description, job_zone FROM onet_occupation WHERE soc = ?", (soc,)
    ).fetchone()
    if row is None:
        raise SystemExit(
            f"O*NET-SOC {soc} is in the crosswalk but absent from the reference DB "
            f"({REFERENCE_DB}). Rebuild it or fix the crosswalk."
        )
    title, description, job_zone = row

    families: dict[str, dict[str, float]] = {
        "riasec": {}, "work_style": {}, "work_context": {}, "work_values": {}
    }
    for family, raw_key, element_id, element_name, scale_id, raw_value, release_label in conn.execute(
        "SELECT family, raw_key, element_id, element_name, scale_id, raw_value, release_label "
        "FROM onet_scale_value WHERE soc = ? ORDER BY family, raw_key",
        (soc,),
    ):
        families[family][raw_key] = _round(raw_value)

    return {
        "soc": soc,
        "title": title,
        "description": description,
        "job_zone": job_zone,
        "riasec_oi": families["riasec"],
        "work_style_wi": families["work_style"],
        "work_context": families["work_context"],
        "work_values_ex": families["work_values"],
    }


def main() -> int:
    if not REFERENCE_DB.exists():
        raise SystemExit(
            f"{REFERENCE_DB} not found. Run:\n"
            "  python -m scripts.onet_import.download_onet\n"
            "  python -m scripts.onet_import.build_onet_reference"
        )

    soc_codes = _mapped_soc_codes()
    conn = sqlite3.connect(REFERENCE_DB)
    try:
        occupations = {soc: _occupation_record(conn, soc) for soc in soc_codes}
    finally:
        conn.close()

    artifact = {
        "_meta": {
            "artifact_version": ARTIFACT_VERSION,
            "generated_by": "scripts.onet_import.export_source_artifact",
            "generated_at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d"),
            "live_scales_source": LIVE_RELEASE_LABEL,
            "work_values_source": WORK_VALUES_RELEASE_LABEL,
            "scale_ranges": {"OI": [1, 7], "WI": [-3, 3], "CX": [1, 5], "CT": [1, 3], "EX": [1, 7]},
            "soc_count": len(occupations),
            "note": (
                "Scoped to O*NET-SOC codes referenced by CareerExternalMapping. "
                "riasec_oi / work_style_wi / work_context come from O*NET 31.0; "
                "work_values_ex comes from O*NET 30.2 (last release with Work Values.txt) "
                "and covers only the 3 DIRECT-mappable MNP keys. Regenerate with "
                "scripts.onet_import.export_source_artifact after any O*NET release "
                "or crosswalk change."
            ),
        },
        "occupations": occupations,
    }

    SCOPED_SOURCE_ARTIFACT.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    log(f"wrote {SCOPED_SOURCE_ARTIFACT}  ({len(occupations)} occupations)")
    for soc, rec in occupations.items():
        log(
            f"  {soc}  {rec['title'][:40]:40}  "
            f"OI:{len(rec['riasec_oi'])}/6 WI:{len(rec['work_style_wi'])}/5 "
            f"CX/CT:{len(rec['work_context'])}/6 EX:{len(rec['work_values_ex'])}/3 "
            f"JZ:{rec['job_zone']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
