"""Load ESCO v1.2.1 (occupations, skills, ISCO groups, relations,
hierarchies) into the reference DB, English + Ukrainian labels side by
side.

Raw ESCO concept URIs are preserved verbatim — they are references, never
MNP identity (Founder Decision #16).
"""

from __future__ import annotations

import sqlite3

from data_explorer import config
from data_explorer.io import log, read_csv, split_esco_labels

_DDL = """
CREATE TABLE esco_occupation (
    uri                 TEXT PRIMARY KEY,
    code                TEXT,
    isco_group          TEXT,
    preferred_label_en  TEXT,
    preferred_label_uk  TEXT,
    description_en       TEXT,
    description_uk       TEXT,
    definition_en        TEXT,
    scope_note_en        TEXT,
    regulated_note_en    TEXT,
    status              TEXT,
    nace_code           TEXT
);
CREATE INDEX ix_esco_occ_isco ON esco_occupation (isco_group);
CREATE INDEX ix_esco_occ_label_en ON esco_occupation (preferred_label_en);

CREATE TABLE esco_occupation_label (
    occupation_uri  TEXT NOT NULL,
    lang            TEXT NOT NULL,
    label           TEXT NOT NULL,
    label_type      TEXT NOT NULL     -- 'alt' | 'hidden'
);
CREATE INDEX ix_esco_occ_label_lbl ON esco_occupation_label (label);

CREATE TABLE esco_skill (
    uri                 TEXT PRIMARY KEY,
    concept_type        TEXT,
    skill_type          TEXT,          -- 'skill/competence' | 'knowledge' | ...
    reuse_level         TEXT,          -- transversal | cross-sector | sector-specific | occupation-specific
    preferred_label_en  TEXT,
    preferred_label_uk  TEXT,
    description_en       TEXT,
    description_uk       TEXT,
    status              TEXT
);
CREATE INDEX ix_esco_skill_type ON esco_skill (skill_type);
CREATE INDEX ix_esco_skill_reuse ON esco_skill (reuse_level);

CREATE TABLE esco_skill_label (
    skill_uri   TEXT NOT NULL,
    lang        TEXT NOT NULL,
    label       TEXT NOT NULL,
    label_type  TEXT NOT NULL
);
CREATE INDEX ix_esco_skill_label_lbl ON esco_skill_label (label);

CREATE TABLE esco_isco_group (
    uri                 TEXT PRIMARY KEY,
    code                TEXT NOT NULL,
    preferred_label_en  TEXT,
    preferred_label_uk  TEXT,
    description_en       TEXT
);
CREATE INDEX ix_esco_isco_code ON esco_isco_group (code);

CREATE TABLE esco_occupation_skill (
    occupation_uri  TEXT NOT NULL,
    skill_uri       TEXT NOT NULL,
    relation_type   TEXT NOT NULL,    -- 'essential' | 'optional'
    skill_type      TEXT,
    PRIMARY KEY (occupation_uri, skill_uri, relation_type)
);
CREATE INDEX ix_esco_os_occ ON esco_occupation_skill (occupation_uri);
CREATE INDEX ix_esco_os_skill ON esco_occupation_skill (skill_uri);

CREATE TABLE esco_skill_skill (
    from_uri       TEXT NOT NULL,
    to_uri         TEXT NOT NULL,
    relation_type  TEXT,
    from_type      TEXT,
    to_type        TEXT,
    PRIMARY KEY (from_uri, to_uri, relation_type)
);

CREATE TABLE esco_broader (
    pillar        TEXT NOT NULL,      -- 'occupation' | 'skill'
    concept_uri   TEXT NOT NULL,
    concept_label TEXT,
    broader_uri   TEXT NOT NULL,
    broader_label TEXT,
    broader_type  TEXT,
    PRIMARY KEY (pillar, concept_uri, broader_uri)
);

CREATE TABLE esco_skill_hierarchy (
    level0_uri TEXT, level0_term TEXT, level0_code TEXT,
    level1_uri TEXT, level1_term TEXT, level1_code TEXT,
    level2_uri TEXT, level2_term TEXT, level2_code TEXT,
    level3_uri TEXT, level3_term TEXT, level3_code TEXT,
    description TEXT
);
"""


def _uk_index(name: str) -> dict[str, dict[str, str]]:
    """uri -> {preferredLabel, description, altLabels(raw), hiddenLabels(raw)} from the uk CSV."""
    out: dict[str, dict[str, str]] = {}
    try:
        d = config.esco_dir("uk")
    except FileNotFoundError:
        return out
    p = d / f"{name}_uk.csv"
    if not p.exists():
        return out
    for row in read_csv(p):
        out[row["conceptUri"]] = row
    return out


def load(conn: sqlite3.Connection) -> None:
    en = config.esco_dir("en")
    conn.executescript(_DDL)
    cur = conn.cursor()

    # ---- occupations -----------------------------------------------------
    uk_occ = _uk_index("occupations")
    n = 0
    for row in read_csv(en / "occupations_en.csv"):
        uri = row["conceptUri"]
        u = uk_occ.get(uri, {})
        cur.execute(
            "INSERT OR IGNORE INTO esco_occupation VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (uri, row.get("code"), row.get("iscoGroup"),
             row.get("preferredLabel"), u.get("preferredLabel"),
             row.get("description"), u.get("description"),
             row.get("definition"), row.get("scopeNote"), row.get("regulatedProfessionNote"),
             row.get("status"), row.get("naceCode")),
        )
        for lang, src in (("en", row), ("uk", u)):
            for lt, field in (("alt", "altLabels"), ("hidden", "hiddenLabels")):
                for lbl in split_esco_labels(src.get(field, "")):
                    cur.execute("INSERT INTO esco_occupation_label VALUES (?,?,?,?)", (uri, lang, lbl, lt))
        n += 1
    log(f"  esco_occupation: {n}")

    # ---- skills ---------------------------------------------------------
    uk_skill = _uk_index("skills")
    n = 0
    for row in read_csv(en / "skills_en.csv"):
        uri = row["conceptUri"]
        u = uk_skill.get(uri, {})
        cur.execute(
            "INSERT OR IGNORE INTO esco_skill VALUES (?,?,?,?,?,?,?,?,?)",
            (uri, row.get("conceptType"), row.get("skillType"), row.get("reuseLevel"),
             row.get("preferredLabel"), u.get("preferredLabel"),
             row.get("description"), u.get("description"), row.get("status")),
        )
        for lang, src in (("en", row), ("uk", u)):
            for lt, field in (("alt", "altLabels"), ("hidden", "hiddenLabels")):
                for lbl in split_esco_labels(src.get(field, "")):
                    cur.execute("INSERT INTO esco_skill_label VALUES (?,?,?,?)", (uri, lang, lbl, lt))
        n += 1
    log(f"  esco_skill: {n}")

    # ---- ISCO groups --------------------------------------------------
    uk_isco = _uk_index("ISCOGroups")
    n = 0
    for row in read_csv(en / "ISCOGroups_en.csv"):
        uri = row["conceptUri"]
        u = uk_isco.get(uri, {})
        cur.execute("INSERT OR IGNORE INTO esco_isco_group VALUES (?,?,?,?,?)",
                    (uri, row.get("code"), row.get("preferredLabel"), u.get("preferredLabel"),
                     row.get("description")))
        n += 1
    log(f"  esco_isco_group: {n}")

    # ---- occupation <-> skill relations ------------------------------
    n = 0
    for row in read_csv(en / "occupationSkillRelations_en.csv"):
        cur.execute("INSERT OR IGNORE INTO esco_occupation_skill VALUES (?,?,?,?)",
                    (row["occupationUri"], row["skillUri"], row["relationType"], row.get("skillType")))
        n += 1
    log(f"  esco_occupation_skill: {n}")

    n = 0
    for row in read_csv(en / "skillSkillRelations_en.csv"):
        cur.execute("INSERT OR IGNORE INTO esco_skill_skill VALUES (?,?,?,?,?)",
                    (row["originalSkillUri"], row["relatedSkillUri"], row.get("relationType"),
                     row.get("originalSkillType"), row.get("relatedSkillType")))
        n += 1
    log(f"  esco_skill_skill: {n}")

    for pillar, fname in (("occupation", "broaderRelationsOccPillar_en.csv"),
                          ("skill", "broaderRelationsSkillPillar_en.csv")):
        p = en / fname
        if not p.exists():
            continue
        n = 0
        for row in read_csv(p):
            cur.execute("INSERT OR IGNORE INTO esco_broader VALUES (?,?,?,?,?,?)",
                        (pillar, row["conceptUri"], row.get("conceptLabel"),
                         row["broaderUri"], row.get("broaderLabel"), row.get("broaderType")))
            n += 1
        log(f"  esco_broader[{pillar}]: {n}")

    p = en / "skillsHierarchy_en.csv"
    if p.exists():
        n = 0
        for row in read_csv(p):
            cur.execute(
                "INSERT INTO esco_skill_hierarchy VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (row.get("Level 0 URI"), row.get("Level 0 preferred term"), row.get("Level 0 code"),
                 row.get("Level 1 URI"), row.get("Level 1 preferred term"), row.get("Level 1 code"),
                 row.get("Level 2 URI"), row.get("Level 2 preferred term"), row.get("Level 2 code"),
                 row.get("Level 3 URI"), row.get("Level 3 preferred term"), row.get("Level 3 code"),
                 row.get("Description")),
            )
            n += 1
        log(f"  esco_skill_hierarchy: {n}")
