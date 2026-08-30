"""Generate MNP <-> external mapping CANDIDATES into a `mapping_review`
table in the reference DB (brief §11). Candidates only — never written to
`MnpExternalMapping`, never auto-confirmed.

Signals (no AI):
  * official ESCO<->O*NET crosswalk (xwalk_esco_onet)
  * ISCO bridge (MNP editorial isco -> ESCO / O*NET in that group)  [when MNP has an isco mapping]
  * normalised English-title match (reused approach, commit 6d27bf3)
"""

from __future__ import annotations

import re
import sqlite3
from difflib import SequenceMatcher

from data_explorer import config
from data_explorer.io import log
from data_explorer.mnp_snapshot import load_mnp_careers

_DDL = """
DROP TABLE IF EXISTS mapping_review;
CREATE TABLE mapping_review (
    entity_type     TEXT NOT NULL,       -- 'career'
    mnp_code        TEXT NOT NULL,
    mnp_name_en     TEXT,
    mnp_name_uk     TEXT,
    source_system   TEXT NOT NULL,       -- 'esco' | 'onet'
    external_id     TEXT NOT NULL,       -- ESCO URI | O*NET-SOC
    external_label  TEXT,
    signal          TEXT NOT NULL,       -- 'official_crosswalk' | 'isco_bridge' | 'title_match'
    score           REAL,
    proposed_mapping_type TEXT,          -- never 'exact' from a machine signal
    review_state    TEXT NOT NULL DEFAULT 'candidate',
    confidence      REAL,
    reviewer        TEXT,
    note            TEXT,
    source_version  TEXT NOT NULL,
    PRIMARY KEY (mnp_code, source_system, external_id, signal)
);
"""

_STOP = {"and", "or", "the", "of", "a", "an", "in", "for", "with", "to"}


def _fold(t: str) -> str:
    for suf in ("ies", "es", "s"):
        if t.endswith(suf) and len(t) - len(suf) >= 3:
            return t[: -len(suf)] + ("y" if suf == "ies" else "")
    return t


def _toks(text: str) -> set[str]:
    return {_fold(t) for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if t not in _STOP and len(t) > 1}


def _score(a: str, b: str) -> float:
    ta, tb = _toks(a), _toks(b)
    if not ta or not tb:
        return 0.0
    j = len(ta & tb) / len(ta | tb)
    s = SequenceMatcher(None, " ".join(sorted(ta)), " ".join(sorted(tb))).ratio()
    return round(0.6 * j + 0.4 * s, 4)


def build(conn: sqlite3.Connection) -> None:
    conn.executescript(_DDL)
    cur = conn.cursor()
    careers = load_mnp_careers()

    # title indexes
    onet_titles: dict[str, list[tuple[str, str]]] = {}
    for soc, title, kind in cur.execute("SELECT soc, title, kind FROM onet_occupation_title"):
        onet_titles.setdefault(soc, []).append((title, kind))
    onet_primary = dict(cur.execute("SELECT soc, title FROM onet_occupation"))
    esco_occ = list(cur.execute("SELECT uri, code, preferred_label_en, preferred_label_uk FROM esco_occupation"))

    tok_onet: dict[str, set[str]] = {}
    for soc, titles in onet_titles.items():
        for t, _ in titles:
            for tk in _toks(t):
                tok_onet.setdefault(tk, set()).add(soc)
    tok_esco: dict[str, set[str]] = {}
    for uri, _code, en, _uk in esco_occ:
        for tk in _toks(en):
            tok_esco.setdefault(tk, set()).add(uri)
    esco_by_uri = {r[0]: r for r in esco_occ}

    n_cand = 0
    for c in careers:
        mapped_soc = {m["external_id"] for m in c.external_mappings if m["source_system"] == "onet"}
        mapped_esco = {m["external_id"] for m in c.external_mappings if m["source_system"] == "esco"}

        # ---- signal 1: official crosswalk (needs an existing mapping on one side) ----
        for soc in mapped_soc:
            for row in cur.execute("SELECT esco_occupation_uri, esco_isco_title FROM xwalk_esco_onet WHERE onet_soc=? AND esco_occupation_uri IS NOT NULL", (soc,)):
                cur.execute(
                    "INSERT OR IGNORE INTO mapping_review "
                    "(entity_type,mnp_code,mnp_name_en,mnp_name_uk,source_system,external_id,external_label,signal,score,proposed_mapping_type,source_version) "
                    "VALUES ('career',?,?,?,'esco',?,?,'official_crosswalk',1.0,'close',?)",
                    (c.code, c.canonical_name_en, c.canonical_name_uk, row[0], row[1], config.CROSSWALK_LABEL))
                n_cand += 1
        for uri in mapped_esco:
            for row in cur.execute("SELECT onet_soc, onet_title FROM xwalk_esco_onet WHERE esco_occupation_uri=?", (uri,)):
                cur.execute(
                    "INSERT OR IGNORE INTO mapping_review "
                    "(entity_type,mnp_code,mnp_name_en,mnp_name_uk,source_system,external_id,external_label,signal,score,proposed_mapping_type,source_version) "
                    "VALUES ('career',?,?,?,'onet',?,?,'official_crosswalk',1.0,'close',?)",
                    (c.code, c.canonical_name_en, c.canonical_name_uk, row[0], row[1], config.CROSSWALK_LABEL))
                n_cand += 1

        # ---- signal 3: title match (always available) ----
        cand_socs: set[str] = set()
        for tk in _toks(c.canonical_name_en):
            cand_socs |= tok_onet.get(tk, set())
        best_onet = sorted(
            ((soc, max(_score(c.canonical_name_en, t) * (1.0 if k == "primary" else 0.55) for t, k in onet_titles[soc]))
             for soc in cand_socs),
            key=lambda x: x[1], reverse=True)[:5]
        for soc, sc in best_onet:
            if sc <= 0:
                continue
            cur.execute(
                "INSERT OR IGNORE INTO mapping_review "
                "(entity_type,mnp_code,mnp_name_en,mnp_name_uk,source_system,external_id,external_label,signal,score,proposed_mapping_type,source_version) "
                "VALUES ('career',?,?,?,'onet',?,?,'title_match',?,?,?)",
                (c.code, c.canonical_name_en, c.canonical_name_uk, soc, onet_primary.get(soc),
                 sc, "close" if sc > 0.75 else "broad", config.ONET_RELEASE_LABEL))
            n_cand += 1

        cand_uris: set[str] = set()
        for tk in _toks(c.canonical_name_en):
            cand_uris |= tok_esco.get(tk, set())
        best_esco = sorted(
            ((uri, _score(c.canonical_name_en, esco_by_uri[uri][2])) for uri in cand_uris),
            key=lambda x: x[1], reverse=True)[:5]
        for uri, sc in best_esco:
            if sc <= 0:
                continue
            cur.execute(
                "INSERT OR IGNORE INTO mapping_review "
                "(entity_type,mnp_code,mnp_name_en,mnp_name_uk,source_system,external_id,external_label,signal,score,proposed_mapping_type,source_version) "
                "VALUES ('career',?,?,?,'esco',?,?,'title_match',?,?,?)",
                (c.code, c.canonical_name_en, c.canonical_name_uk, uri, esco_by_uri[uri][2],
                 sc, "close" if sc > 0.75 else "broad", config.ESCO_LABEL))
            n_cand += 1

    # careers with zero candidates -> explicit review_required marker
    for c in careers:
        got = cur.execute("SELECT count(*) FROM mapping_review WHERE mnp_code=?", (c.code,)).fetchone()[0]
        if got == 0:
            cur.execute(
                "INSERT INTO mapping_review "
                "(entity_type,mnp_code,mnp_name_en,mnp_name_uk,source_system,external_id,signal,review_state,source_version) "
                "VALUES ('career',?,?,?,'esco','','none','review_required','')",
                (c.code, c.canonical_name_en, c.canonical_name_uk))

    conn.commit()
    log(f"  mapping_review: {n_cand} candidates for {len(careers)} MNP careers")
