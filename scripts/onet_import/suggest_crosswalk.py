"""Propose O*NET-SOC crosswalk candidates for MNP careers, by matching the
career's English title against O*NET's own primary + alternate + reported
title corpus (`onet_occupation_title` in the reference DB), tie-broken by
Job-Zone plausibility.

Output is a REVIEW ARTIFACT, never applied automatically — it feeds a
human curator who fills `CareerExternalMapping.reviewed_by` /
`confidence`. Deterministic (pure string + set math, no network, no AI).

Today it runs against the 24-Alpha catalog (titles from
`app/services/knowledge/seed.py`) and compares each suggestion to the
existing hand crosswalk in `onet_alpha_fixture.py`. Fed a larger MNP
career list later, the same tool produces the catalog-scale draft.

Usage:
    python -m scripts.onet_import.suggest_crosswalk
    python -m scripts.onet_import.suggest_crosswalk --top 5
"""

from __future__ import annotations

import csv
import re
import sqlite3
import sys
from difflib import SequenceMatcher

from app.services.career_kb.onet_alpha_fixture import load_onet_source
from app.services.knowledge.seed import _CAREERS
from scripts.onet_import.common import CROSSWALK_DIR, REFERENCE_DB, log

_STOP = {"and", "or", "the", "of", "a", "an", "in", "for", "with", "to"}
# O*NET alternate/reported titles are user-submitted and noisy; a match on
# the official primary title is worth far more than a match on some
# occupation's list of also-known-as strings.
_KIND_WEIGHT = {"primary": 1.0, "alternate": 0.55, "reported": 0.5}


def _fold(tok: str) -> str:
    """Crude singular fold so 'electricians' matches 'electrician',
    'analysts' matches 'analyst'. Not a real stemmer — enough for title
    matching."""
    for suf in ("ies", "es", "s"):
        if tok.endswith(suf) and len(tok) - len(suf) >= 3:
            return tok[: -len(suf)] + ("y" if suf == "ies" else "")
    return tok


def _norm_tokens(text: str) -> set[str]:
    return {
        _fold(t)
        for t in re.findall(r"[a-z0-9]+", text.lower())
        if t not in _STOP and len(t) > 1
    }


def _score(a: str, b: str) -> float:
    ta, tb = _norm_tokens(a), _norm_tokens(b)
    if not ta or not tb:
        return 0.0
    jaccard = len(ta & tb) / len(ta | tb)
    seq = SequenceMatcher(None, " ".join(sorted(ta)), " ".join(sorted(tb))).ratio()
    return round(0.6 * jaccard + 0.4 * seq, 4)


def _load_onet_titles(conn: sqlite3.Connection) -> dict[str, list[tuple[str, str]]]:
    """soc -> [(title, kind)]  (primary first)."""
    out: dict[str, list[tuple[str, str]]] = {}
    for soc, title, kind in conn.execute(
        "SELECT soc, title, kind FROM onet_occupation_title"
    ):
        out.setdefault(soc, []).append((title, kind))
    return out


def _token_index(onet_titles: dict[str, list[tuple[str, str]]]) -> dict[str, set[str]]:
    """token -> {soc} — lets us score only the SOCs that share a word with
    the career title, instead of all ~1000."""
    idx: dict[str, set[str]] = {}
    for soc, titles in onet_titles.items():
        for title, _ in titles:
            for tok in _norm_tokens(title):
                idx.setdefault(tok, set()).add(soc)
    return idx


def _primary_title(conn: sqlite3.Connection) -> dict[str, str]:
    return dict(conn.execute("SELECT soc, title FROM onet_occupation"))


def _current_mappings() -> dict[str, list[tuple[str, str, str]]]:
    """mnp code -> [(soc, label, status)]  from the existing hand crosswalk."""
    out: dict[str, list[tuple[str, str, str]]] = {}
    for rec in load_onet_source():
        out[rec.mnp_career_code] = [
            (o.soc_code, o.label, o.mapping_status) for o in rec.onet_occupations
        ]
    return out


def main(argv: list[str]) -> int:
    top_n = 5
    if "--top" in argv:
        top_n = int(argv[argv.index("--top") + 1])

    if not REFERENCE_DB.exists():
        raise SystemExit(
            f"{REFERENCE_DB} not found — run download_onet + build_onet_reference first"
        )

    conn = sqlite3.connect(REFERENCE_DB)
    try:
        onet_titles = _load_onet_titles(conn)
        primary = _primary_title(conn)
    finally:
        conn.close()
    tok_idx = _token_index(onet_titles)

    current = _current_mappings()
    CROSSWALK_DIR.mkdir(parents=True, exist_ok=True)
    out_path = CROSSWALK_DIR / "onet_suggestions.csv"

    rows: list[dict] = []
    for career in _CAREERS:
        code = career["code"]
        title_en = career["title_en"] or ""
        # only score SOCs that share at least one title word with the career
        candidate_socs: set[str] = set()
        for tok in _norm_tokens(title_en):
            candidate_socs |= tok_idx.get(tok, set())
        best: dict[str, tuple[float, str]] = {}
        for soc in candidate_socs:
            s = max(
                _score(title_en, t) * _KIND_WEIGHT.get(kind, 0.5)
                for t, kind in onet_titles[soc]
            )
            if s > 0:
                best[soc] = (round(s, 4), primary.get(soc, soc))
        ranked = sorted(best.items(), key=lambda kv: kv[1][0], reverse=True)[:top_n]

        cur = current.get(code, [])
        cur_socs = {s for s, _, _ in cur}
        cur_str = "; ".join(f"{s} ({st})" for s, _, st in cur) or "(none / UNMAPPED)"

        if not ranked:
            rows.append(dict(
                career_code=code, title_en=title_en, current_mapping=cur_str,
                suggested_soc="", suggested_label="", score="", rank="",
                verdict="no_candidate",
            ))
            continue

        for rank, (soc, (score, label)) in enumerate(ranked, 1):
            if soc in cur_socs:
                verdict = "agrees"
            elif rank == 1 and cur_socs:
                verdict = "differs"
            elif rank == 1 and not cur_socs:
                verdict = "new (career currently UNMAPPED)"
            else:
                verdict = "alt"
            rows.append(dict(
                career_code=code, title_en=title_en, current_mapping=cur_str,
                suggested_soc=soc, suggested_label=label, score=score, rank=rank,
                verdict=verdict,
            ))

    fieldnames = ["career_code", "title_en", "current_mapping", "suggested_soc",
                  "suggested_label", "score", "rank", "verdict"]
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    log(f"wrote {out_path}  ({len(rows)} rows, {len(_CAREERS)} careers)")
    # summary
    top1 = [r for r in rows if r["rank"] == 1]
    agree = sum(1 for r in top1 if r["verdict"] == "agrees")
    differ = sum(1 for r in top1 if r["verdict"] == "differs")
    log(f"  rank-1 verdict: {agree} agree, {differ} differ, "
        f"{len(top1) - agree - differ} new/other")
    for r in top1:
        flag = "  " if r["verdict"] == "agrees" else "!!"
        log(f"  {flag} {r['career_code']:32} -> {r['suggested_soc']:11} "
            f"{r['suggested_label'][:34]:34} score={r['score']}  [{r['verdict']}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
