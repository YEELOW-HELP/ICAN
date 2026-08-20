from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AdminUser
from app.db.models_crm import Client, Task, TaskStatus


async def create_task(session: AsyncSession, client: Client, data: dict) -> Task:
    task = Task(
        client_id=client.id,
        task_type=data["task_type"],
        other_description=data.get("other_description"),
        assignee_id=data.get("assignee_id"),
        due_at=data.get("due_at"),
        note=data.get("note"),
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task


async def complete_task(session: AsyncSession, task: Task) -> Task:
    task.status = TaskStatus.DONE
    task.completed_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(task)
    return task


async def cancel_task(session: AsyncSession, task: Task) -> Task:
    task.status = TaskStatus.CANCELLED
    await session.commit()
    await session.refresh(task)
    return task


async def list_tasks_for_client(session: AsyncSession, client_id: int) -> list[Task]:
    result = await session.execute(select(Task).where(Task.client_id == client_id).order_by(Task.due_at))
    return list(result.scalars().all())


async def list_overdue(session: AsyncSession, assignee_id: int | None = None) -> list[Task]:
    now = datetime.now(timezone.utc)
    query = select(Task).where(Task.status == TaskStatus.PENDING, Task.due_at < now)
    if assignee_id is not None:
        query = query.where(Task.assignee_id == assignee_id)
    result = await session.execute(query.order_by(Task.due_at))
    return list(result.scalars().all())
