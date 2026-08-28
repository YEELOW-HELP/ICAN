"""Lookup helpers for the BASIC_STRUCTURED question bank (Matching V1
M1). The "current bank" is always a DB fact (the definition with
`is_active=True` for a given mode), never a hardcoded assessment_version
string in business logic -- see `seed.py` for how it is populated."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_basic_assessment import AssessmentDefinition, AssessmentItem, AssessmentMode
from app.services.exceptions import BasicAssessmentDefinitionNotFoundError


async def get_active_definition(session: AsyncSession, mode: AssessmentMode) -> AssessmentDefinition:
    result = await session.execute(
        select(AssessmentDefinition).where(
            AssessmentDefinition.mode == mode,
            AssessmentDefinition.is_active.is_(True),
        )
    )
    definition = result.scalar_one_or_none()
    if definition is None:
        raise BasicAssessmentDefinitionNotFoundError(f"no active AssessmentDefinition for mode={mode.value}")
    return definition


async def get_active_items(session: AsyncSession, definition: AssessmentDefinition) -> list[AssessmentItem]:
    """Active items in deterministic `display_order` -- the exact item
    count is always `len()` of this list, never a constant in code."""

    result = await session.execute(
        select(AssessmentItem)
        .where(AssessmentItem.definition_id == definition.id, AssessmentItem.active.is_(True))
        .order_by(AssessmentItem.display_order)
    )
    return list(result.scalars().all())
