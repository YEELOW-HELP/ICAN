"""Deterministic material-duplicate detection (Career Fit / Direction
Evaluation Model, material-differentiation invariant carried over from
Slice 1: no invented similarity threshold, no secret scoring adjustment
for diversity).

V0.1 deliberately does NOT do semantic/fuzzy similarity matching --
`RankingPolicy.dedup_similarity_threshold` is `None` because no such
threshold is methodology-approved yet (see
`app/services/direction/config.py`). Instead, this module finds only
EXACT, structural collisions already present in curated KB data: two
different `Career` rows in the same KB version sharing the identical
normalized title or the identical normalized alias text. That is a real
KB curation collision (the same career entered twice under different
codes), never a guess about two genuinely different careers being
"similar enough."

Grouping only -- this module does not decide which member of a group is
the "stronger recommendation" (that requires the four-output scores,
computed later in the pipeline).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from app.db.models_knowledge import Career, CareerAlias

__all__ = ["normalize_title", "find_duplicate_groups"]


def normalize_title(text: str) -> str:
    return " ".join(text.strip().lower().split())


def find_duplicate_groups(
    careers: Sequence[Career], aliases_by_career: dict[uuid.UUID, list[CareerAlias]]
) -> list[tuple[str, ...]]:
    """Returns groups of >=2 `career_code`s that collide on an exact
    normalized title or alias. Each career appears in at most one group
    (the first collision key it matches under is authoritative -- stable
    because iteration order follows `careers`' input order)."""
    by_key: dict[str, list[str]] = {}
    grouped_codes: set[str] = set()

    for career in careers:
        if career.code in grouped_codes:
            continue
        keys = {normalize_title(career.title_uk)}
        if career.title_en:
            keys.add(normalize_title(career.title_en))
        for alias in aliases_by_career.get(career.id, []):
            keys.add(alias.normalized_text)
        for key in keys:
            by_key.setdefault(key, []).append(career.code)

    groups: list[tuple[str, ...]] = []
    seen: set[frozenset[str]] = set()
    for codes in by_key.values():
        if len(codes) < 2:
            continue
        key = frozenset(codes)
        if key in seen:
            continue
        seen.add(key)
        groups.append(tuple(sorted(codes)))
    return groups
