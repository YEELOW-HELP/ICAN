"""Read-only assembled views over data/data_explorer/reference.sqlite."""

from __future__ import annotations

import sqlite3

from data_explorer import config


def _conn() -> sqlite3.Connection:
    if not config.REFERENCE_DB.exists():
        raise SystemExit("reference.sqlite not built — run: python -m data_explorer.cli build")
    c = sqlite3.connect(config.REFERENCE_DB)
    c.row_factory = sqlite3.Row
    return c


# --------------------------------------------------------------------------
# O*NET
# --------------------------------------------------------------------------
def onet_occupation_view(conn: sqlite3.Connection, soc: str) -> dict:
    occ = conn.execute("SELECT * FROM onet_occupation WHERE soc = ?", (soc,)).fetchone()
    if occ is None:
        return {}
    titles = {
        kind: [r["title"] for r in conn.execute(
            "SELECT title FROM onet_occupation_title WHERE soc=? AND kind=? ORDER BY title", (soc, kind))]
        for kind in ("primary", "alternate", "reported")
    }

    ratings: dict[str, list[dict]] = {}
    for r in conn.execute(
        "SELECT table_key, family, element_id, element_name, scale_id, category, raw_value, normalized_value "
        "FROM onet_rating WHERE soc=? ORDER BY table_key, scale_id, element_id", (soc,)
    ):
        ratings.setdefault(r["table_key"], []).append(dict(r))

    work_values = [dict(r) for r in conn.execute(
        "SELECT element_name, short_key, raw_value, normalized_value, release_label "
        "FROM onet_work_value WHERE soc=? ORDER BY element_id", (soc,))]

    tasks = [dict(r) for r in conn.execute(
        "SELECT t.task_id, t.task, t.task_type, "
        "(SELECT raw_value FROM onet_task_rating WHERE task_id=t.task_id AND scale_id='IM') AS importance "
        "FROM onet_task t WHERE t.soc=? ORDER BY importance DESC NULLS LAST", (soc,))]

    software = [dict(r) for r in conn.execute(
        "SELECT element_name, workplace_example, hot_technology, in_demand "
        "FROM onet_software_skill WHERE soc=? ORDER BY hot_technology DESC, element_name", (soc,))]

    related = [dict(r) for r in conn.execute(
        "SELECT r.related_soc, o.title AS related_title, r.relatedness_tier, r.idx "
        "FROM onet_related_occupation r LEFT JOIN onet_occupation o ON o.soc=r.related_soc "
        "WHERE r.soc=? ORDER BY r.idx", (soc,))]

    return {
        "soc": occ["soc"], "title": occ["title"], "description": occ["description"],
        "job_zone": occ["job_zone"], "titles": titles, "ratings": ratings,
        "work_values": work_values, "tasks": tasks, "software": software, "related": related,
    }


# --------------------------------------------------------------------------
# ESCO
# --------------------------------------------------------------------------
def esco_occupation_view(conn: sqlite3.Connection, uri: str) -> dict:
    occ = conn.execute("SELECT * FROM esco_occupation WHERE uri = ?", (uri,)).fetchone()
    if occ is None:
        return {}
    labels: dict[str, list[str]] = {}
    for r in conn.execute("SELECT lang, label_type, label FROM esco_occupation_label WHERE occupation_uri=? ORDER BY lang, label_type", (uri,)):
        labels.setdefault(f"{r['lang']}_{r['label_type']}", []).append(r["label"])
    isco = conn.execute("SELECT code, preferred_label_en, preferred_label_uk FROM esco_isco_group WHERE code=?", (occ["isco_group"],)).fetchone()

    skills = [dict(r) for r in conn.execute(
        "SELECT s.preferred_label_en, s.preferred_label_uk, s.skill_type, s.reuse_level, os.relation_type "
        "FROM esco_occupation_skill os JOIN esco_skill s ON s.uri = os.skill_uri "
        "WHERE os.occupation_uri=? ORDER BY os.relation_type, s.preferred_label_en", (uri,))]

    broader = [dict(r) for r in conn.execute(
        "SELECT broader_label, broader_type FROM esco_broader WHERE pillar='occupation' AND concept_uri=?", (uri,))]

    return {
        "uri": uri, "code": occ["code"], "isco_group": occ["isco_group"],
        "isco_label_en": isco["preferred_label_en"] if isco else None,
        "isco_label_uk": isco["preferred_label_uk"] if isco else None,
        "preferred_label_en": occ["preferred_label_en"], "preferred_label_uk": occ["preferred_label_uk"],
        "description_en": occ["description_en"], "description_uk": occ["description_uk"],
        "definition_en": occ["definition_en"], "regulated_note_en": occ["regulated_note_en"],
        "labels": labels, "skills": skills, "broader": broader,
        "essential_skill_count": sum(1 for s in skills if s["relation_type"] == "essential"),
        "optional_skill_count": sum(1 for s in skills if s["relation_type"] == "optional"),
    }


# --------------------------------------------------------------------------
# crosswalk
# --------------------------------------------------------------------------
def crosswalk_for(conn: sqlite3.Connection, *, soc: str | None = None, esco_uri: str | None = None,
                  esco_code: str | None = None) -> list[dict]:
    if soc:
        q, a = "SELECT * FROM xwalk_esco_onet WHERE onet_soc = ?", (soc,)
    elif esco_uri:
        q, a = "SELECT * FROM xwalk_esco_onet WHERE esco_occupation_uri = ?", (esco_uri,)
    elif esco_code:
        q, a = "SELECT * FROM xwalk_esco_onet WHERE esco_isco_code = ?", (esco_code,)
    else:
        return []
    return [dict(r) for r in conn.execute(q, a)]


# --------------------------------------------------------------------------
# MNP interpretation vs source fact (brief §12)
# --------------------------------------------------------------------------
def mnp_used_vs_ignored(conn: sqlite3.Connection, soc: str) -> dict:
    """For a mapped O*NET-SOC: which O*NET dimensions the current MNP
    matching engine selects vs which it ignores vs which are missing."""
    out = {"used": {}, "ignored": {}, "missing": {}}
    for table_key, selected_ids in config.MNP_SELECTED_ONET.items():
        present = {r[0]: r[1] for r in conn.execute(
            "SELECT element_id, element_name FROM onet_rating WHERE soc=? AND table_key=?", (soc, table_key))}
        wv_present = {}
        if table_key == "work_values":
            wv_present = {r[0]: r[1] for r in conn.execute(
                "SELECT element_id, element_name FROM onet_work_value WHERE soc=?", (soc,))}
            present = wv_present
        out["used"][table_key] = [{"element_id": e, "element_name": present.get(e)} for e in selected_ids if e in present]
        out["missing"][table_key] = [e for e in selected_ids if e not in present]
        out["ignored"][table_key] = [
            {"element_id": e, "element_name": n} for e, n in sorted(present.items()) if e not in selected_ids
        ]
    return out
