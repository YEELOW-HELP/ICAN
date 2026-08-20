from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AdminUser
from app.db.models_crm import Client, ClientFile, FileType, TimelineEventType
from app.services.crm import clients as client_service
from app.services.crm import timeline
from app.services.crm.storage import get_storage


async def upload_file(
    session: AsyncSession,
    client: Client,
    *,
    file_type: str,
    other_description: str | None,
    filename: str,
    content_type: str | None,
    data: bytes,
    actor: AdminUser,
) -> ClientFile:
    storage_key = get_storage().save(client.id, filename, data)

    row = ClientFile(
        client_id=client.id,
        file_type=FileType(file_type),
        other_description=other_description,
        filename=filename,
        storage_key=storage_key,
        content_type=content_type,
        size_bytes=len(data),
        uploaded_by_id=actor.id,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)

    await client_service.touch_activity(session, client)
    await timeline.record_event(
        session, client_id=client.id, event_type=TimelineEventType.FILE_UPLOADED,
        description=f"Завантажено файл: {filename} ({row.file_type.value})", actor_id=actor.id,
    )
    return row


async def list_files(session: AsyncSession, client_id: int) -> list[ClientFile]:
    result = await session.execute(
        select(ClientFile)
        .where(ClientFile.client_id == client_id, ClientFile.deleted_at.is_(None))
        .order_by(ClientFile.uploaded_at.desc())
    )
    return list(result.scalars().all())


async def get_file(session: AsyncSession, file_id: int) -> ClientFile | None:
    result = await session.execute(
        select(ClientFile).where(ClientFile.id == file_id, ClientFile.deleted_at.is_(None))
    )
    return result.scalar_one_or_none()


async def mark_current_cv(session: AsyncSession, file: ClientFile, actor: AdminUser) -> ClientFile:
    others = await session.execute(
        select(ClientFile).where(ClientFile.client_id == file.client_id, ClientFile.is_current_cv.is_(True))
    )
    for other in others.scalars().all():
        other.is_current_cv = False
    file.is_current_cv = True
    await session.commit()
    await session.refresh(file)
    return file


async def delete_file(session: AsyncSession, file: ClientFile, actor: AdminUser) -> None:
    file.deleted_at = datetime.now(timezone.utc)
    await session.commit()
    await timeline.record_event(
        session, client_id=file.client_id, event_type=TimelineEventType.FILE_DELETED,
        description=f"Видалено файл: {file.filename}", actor_id=actor.id,
    )
