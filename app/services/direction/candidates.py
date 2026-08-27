"""Deterministic V0.1 candidate generation (Career Fit / Direction
Evaluation Model plan section 7).

Broad-before-ranking, by design: every ACTIVE career in the pinned
`KnowledgeBaseVersion` enters the pool (up to a configurable shortlist
cap), unfiltered by profile content. Filtering happens later -- the hard
constraint gate, the four-output scoring, and `RankingPolicy` -- never
here. This is what "avoid treating missing profile data as negative
evidence" means concretely: candidate generation never looks at the
profile at all, so a profile's gaps can never silently shrink the pool.

Only real, persisted `Career` rows are ever returned -- retrieval goes
exclusively through `app.services.knowledge.retrieval` (the Stage 3A
write-path contract's read-side counterpart: Direction Intelligence never
queries `careers`/`career_*` tables directly). No career name/code is
ever invented; `career_id`/`career_code` are the actual KB primary
key/business key, preserved unchanged.

If semantic/LLM reranking is ever added, it stays OUT of this critical
path -- this module has zero AI Gateway dependency and must stay that way.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_knowledge import Career, CareerStatus
from app.services.knowledge.retrieval import find_careers

__all__ = ["CandidateEntry", "generate_candidates"]


@dataclass(frozen=True)
class CandidateEntry:
    career_id: uuid.UUID
    career_code: str
    domain: str
    entry_reason: str


async def generate_candidates(
    session: AsyncSession,
    *,
    knowledge_base_version_id: uuid.UUID,
    shortlist_cap: int | None = None,
) -> list[CandidateEntry]:
    careers: list[Career] = await find_careers(
        session, knowledge_base_version_id=knowledge_base_version_id, status=CareerStatus.ACTIVE
    )
    if shortlist_cap is not None and shortlist_cap > 0:
        careers = careers[:shortlist_cap]

    return [
        CandidateEntry(
            career_id=career.id,
            career_code=career.code,
            domain=career.domain.value,
            entry_reason=(
                f"broad candidate pool: ACTIVE career in KnowledgeBaseVersion {knowledge_base_version_id} "
                "(V0.1 candidate generation is unfiltered by profile content; eligibility is decided by the "
                "hard constraint gate and RankingPolicy downstream)"
            ),
        )
        for career in careers
    ]
