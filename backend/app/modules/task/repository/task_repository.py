from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.model.entity.task import Task, TaskStatus, TaskType


class TaskRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def find_by_id(self, task_id: int) -> Optional[Task]:
        result = await self._db.execute(
            select(Task).where(Task.id == task_id)
        )
        return result.scalar_one_or_none()

    async def find_by_session(self, session_id: int) -> list[Task]:
        result = await self._db.execute(
            select(Task)
            .where(Task.session_id == session_id)
            .order_by(Task.id.desc())
        )
        return list(result.scalars().all())

    async def find_running_by_session(self, session_id: int) -> list[Task]:
        result = await self._db.execute(
            select(Task).where(
                Task.session_id == session_id,
                Task.status.in_([TaskStatus.PENDING, TaskStatus.RUNNING, TaskStatus.STREAMING]),
            )
        )
        return list(result.scalars().all())

    async def create(
        self,
        session_id: int,
        task_type: TaskType,
    ) -> Task:
        task = Task(
            session_id=session_id,
            type=task_type,
            status=TaskStatus.PENDING,
            retry_count=0,
        )
        self._db.add(task)
        await self._db.flush()
        await self._db.refresh(task)
        return task

    async def update_status(
        self,
        task_id: int,
        status: TaskStatus,
        result: dict | None = None,
        error: str | None = None,
    ) -> None:
        task = await self.find_by_id(task_id)
        if task is not None:
            task.status = status
            if result is not None:
                task.result = result
            if error is not None:
                task.error = error
            await self._db.flush()

    async def increment_retry(self, task_id: int) -> None:
        task = await self.find_by_id(task_id)
        if task is not None:
            task.retry_count += 1
            await self._db.flush()

    async def cancel(self, task_id: int) -> bool:
        task = await self.find_by_id(task_id)
        if task is None:
            return False
        if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            return False
        task.status = TaskStatus.CANCELLED
        await self._db.flush()
        return True
