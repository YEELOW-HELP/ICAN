"""Resolves a raw CV/questionnaire job title to a `MnpCareer` via
`MnpCareerAlias` (MNP_RESUME_PARSER_V1 "Deterministic normalization":
"MNP Career aliases"). Exact/normalized match only -- no fuzzy/semantic
matching (no LLM tokens); an unresolved title simply leaves
`normalized_career_id` unset, never guesses."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_career_kb_mnp import CareerLifecycleStatus, MnpCareer, MnpCareerAlias


def _normalize(text: str) -> str:
    return " ".join(text.strip().lower().split())


async def resolve_job_title_to_career(session: AsyncSession, raw_title: str) -> MnpCareer | None:
    normalized = _normalize(raw_title)
    if not normalized:
        return None

    result = await session.execute(select(MnpCareerAlias))
    for alias_row in result.scalars().all():
        if _normalize(alias_row.alias) == normalized:
            career = await session.get(MnpCareer, alias_row.career_id)
            if career is not None and career.status != CareerLifecycleStatus.ARCHIVED:
                return career

    # Also match the canonical name directly (an alias row always exists
    # for it too via seed_alpha, but this keeps the function correct even
    # if a career has zero aliases).
    result = await session.execute(select(MnpCareer).where(MnpCareer.status != CareerLifecycleStatus.ARCHIVED))
    for career in result.scalars().all():
        if _normalize(career.canonical_name_uk) == normalized or _normalize(career.canonical_name_en) == normalized:
            return career
    return None
