"""Data-quality checks over the reference DB (brief §23). Read-only,
reports facts — never fixes anything, never treats a missing value as 0.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field


@dataclass
class QualityReport:
    checks: list[tuple[str, str, int]] = field(default_factory=list)  # (severity, description, count)

    def add(self, severity: str, description: str, count: int) -> None:
        self.checks.append((severity, description, count))

    def as_rows(self) -> list[dict]:
        return [{"severity": s, "check": d, "count": c} for s, d, c in self.checks]


def run(conn: sqlite3.Connection) -> QualityReport:
    cur = conn.cursor()
    r = QualityReport()

    def one(sql: str, *a) -> int:
        return cur.execute(sql, a).fetchone()[0]

    # scale validity — normalized values must be in [0,1]
    r.add("error", "onet_rating.normalized_value outside [0,1]",
          one("SELECT count(*) FROM onet_rating WHERE normalized_value IS NOT NULL "
              "AND (normalized_value < -0.0001 OR normalized_value > 1.0001)"))
    r.add("error", "onet_rating raw_value outside the scale's declared [min,max]",
          one("SELECT count(*) FROM onet_rating r JOIN onet_scale s USING(scale_id) "
              "WHERE r.raw_value < s.minimum - 0.0001 OR r.raw_value > s.maximum + 0.0001"))

    # never treat missing as zero — flag genuine 0.0 raw values only where the
    # scale minimum is > 0 (would indicate a mis-parse)
    r.add("warn", "onet_rating raw_value = 0 on a scale whose minimum is > 0 (possible mis-parse)",
          one("SELECT count(*) FROM onet_rating r JOIN onet_scale s USING(scale_id) "
              "WHERE r.raw_value = 0 AND s.minimum > 0"))

    # missing provenance / version
    r.add("error", "stg_source rows without attribution", one("SELECT count(*) FROM stg_source WHERE attribution IS NULL OR attribution = ''"))
    r.add("error", "stg_source rows without a sha256", one("SELECT count(*) FROM stg_source WHERE sha256 IS NULL OR sha256 = ''"))
    r.add("warn", "onet_rating rows without a release_label", one("SELECT count(*) FROM onet_rating WHERE release_label IS NULL OR release_label = ''"))

    # crosswalk
    r.add("info", "crosswalk pairs whose ESCO code did NOT resolve to an ESCO occupation URI (ISCO-group level or absent)",
          one("SELECT count(*) FROM xwalk_esco_onet WHERE esco_occupation_uri IS NULL"))
    r.add("error", "crosswalk O*NET-SOC codes not present in onet_occupation",
          one("SELECT count(*) FROM xwalk_esco_onet x LEFT JOIN onet_occupation o ON o.soc = x.onet_soc WHERE o.soc IS NULL"))
    r.add("warn", "crosswalk mapping_relation silently promoted to 'exact' (must be 0)",
          one("SELECT count(*) FROM xwalk_esco_onet WHERE mapping_relation = 'exact'"))

    # esco
    r.add("warn", "ESCO occupations with no essential skill relation",
          one("SELECT count(*) FROM esco_occupation o WHERE NOT EXISTS "
              "(SELECT 1 FROM esco_occupation_skill s WHERE s.occupation_uri = o.uri AND s.relation_type = 'essential')"))
    r.add("info", "ESCO occupations with no Ukrainian preferred label",
          one("SELECT count(*) FROM esco_occupation WHERE preferred_label_uk IS NULL OR preferred_label_uk = ''"))
    r.add("info", "ESCO skills with no Ukrainian preferred label",
          one("SELECT count(*) FROM esco_skill WHERE preferred_label_uk IS NULL OR preferred_label_uk = ''"))

    # onet
    r.add("info", "O*NET occupations with no Job Zone", one("SELECT count(*) FROM onet_occupation WHERE job_zone IS NULL"))
    r.add("info", "O*NET occupations with no work-values row (13-20xx SOC splits post-date the 30.2 data)",
          one("SELECT count(*) FROM onet_occupation o WHERE NOT EXISTS (SELECT 1 FROM onet_work_value w WHERE w.soc = o.soc)"))

    return r
