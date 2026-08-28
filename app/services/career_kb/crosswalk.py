"""External taxonomy crosswalk (`CareerExternalMapping`), Matching V1 M3.

Many-to-many by design (Founder Review §5/§F of
`MNP_CAREER_KB_V1.md`) -- one `Career` may carry multiple mappings to the
same `source_system` (e.g. two O*NET-SOC codes), and the same external
code may be attached to more than one `Career` (e.g. two MNP careers both
crosswalking to the same, broader O*NET occupation). `Career.code` is
never touched here.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_career_kb import CareerExternalMapping, ExternalMappingStatus, ExternalSourceSystem
from app.services.exceptions import CareerAlreadyMappedError


async def create_external_mapping(
    session: AsyncSession,
    *,
    career_id: uuid.UUID,
    source_system: ExternalSourceSystem,
    external_code: str,
    external_label: str | None,
    mapping_status: ExternalMappingStatus,
    mapping_version: str,
    confidence: float | None = None,
    external_url: str | None = None,
    reviewed_by: str | None = None,
    notes: str | None = None,
) -> CareerExternalMapping:
    if mapping_status in (ExternalMappingStatus.UNMAPPED,):
        raise ValueError("use mark_unmapped() for an UNMAPPED record -- external_code must be present here")

    existing = await session.execute(
        select(CareerExternalMapping).where(
            CareerExternalMapping.career_id == career_id,
            CareerExternalMapping.source_system == source_system,
            CareerExternalMapping.external_code == external_code,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise CareerAlreadyMappedError(
            f"career {career_id} already has a {source_system.value} mapping to {external_code!r}"
        )

    mapping = CareerExternalMapping(
        career_id=career_id,
        source_system=source_system,
        external_code=external_code,
        external_label=external_label,
        external_url=external_url,
        mapping_status=mapping_status,
        mapping_version=mapping_version,
        confidence=confidence,
        reviewed_by=reviewed_by,
        notes=notes,
    )
    session.add(mapping)
    await session.flush()
    return mapping


async def mark_unmapped(
    session: AsyncSession,
    *,
    career_id: uuid.UUID,
    source_system: ExternalSourceSystem,
    mapping_version: str,
    notes: str | None = None,
) -> CareerExternalMapping:
    """Idempotent: returns the existing UNMAPPED marker row if one already
    exists for this (career, source_system), never creates a second one."""

    existing = await session.execute(
        select(CareerExternalMapping).where(
            CareerExternalMapping.career_id == career_id,
            CareerExternalMapping.source_system == source_system,
            CareerExternalMapping.mapping_status == ExternalMappingStatus.UNMAPPED,
        )
    )
    row = existing.scalar_one_or_none()
    if row is not None:
        return row

    marker = CareerExternalMapping(
        career_id=career_id,
        source_system=source_system,
        external_code=None,
        external_label=None,
        mapping_status=ExternalMappingStatus.UNMAPPED,
        mapping_version=mapping_version,
        notes=notes,
    )
    session.add(marker)
    await session.flush()
    return marker


async def get_external_mappings(
    session: AsyncSession, career_id: uuid.UUID, *, source_system: ExternalSourceSystem | None = None
) -> list[CareerExternalMapping]:
    query = select(CareerExternalMapping).where(CareerExternalMapping.career_id == career_id)
    if source_system is not None:
        query = query.where(CareerExternalMapping.source_system == source_system)
    result = await session.execute(query.order_by(CareerExternalMapping.created_at))
    return list(result.scalars().all())
