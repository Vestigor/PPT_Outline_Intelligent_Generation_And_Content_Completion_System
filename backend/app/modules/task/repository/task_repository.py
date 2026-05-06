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

    async def find_by_id_and_session(
        self, task_id: int, session_id: int
    ) -> Optional[Task]:
        result = await self._db.execute(
            select(Task).where(Task.id == task_id, Task.session_id == session_id)
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

    async def find_latest_by_session(self, session_id: int) -> Optional[Task]:
        result = await self._db.execute(
            select(Task)
            .where(Task.session_id == session_id)
            .order_by(Task.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        session_id: int,
        task_type: TaskType,
        trigger_message_id: int | None = None,
        snapshot_llm_config_id: int | None = None,
        snapshot_rag_enabled: bool = False,
        snapshot_deep_search_enabled: bool = False,
    ) -> Task:
        task = Task(
            session_id=session_id,
            type=task_type,
            status=TaskStatus.PENDING,
            trigger_message_id=trigger_message_id,
            retry_count=0,
            snapshot_llm_config_id=snapshot_llm_config_id,
            snapshot_rag_enabled=snapshot_rag_enabled,
            snapshot_deep_search_enabled=snapshot_deep_search_enabled,
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
