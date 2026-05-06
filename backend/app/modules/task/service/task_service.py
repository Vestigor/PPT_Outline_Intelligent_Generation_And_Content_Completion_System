from __future__ import annotations

import json

from app.common.exception.code import StatusCode
from app.common.exception.exception import BusinessException
from app.common.model.entity.task import Task, TaskStatus, TaskType
from app.infrastructure.log.logging_config import get_logger
from app.modules.task.dto.response import TaskResponse, TaskStatusResponse
from app.modules.task.repository.task_repository import TaskRepository

logger = get_logger(__name__)

TASK_STREAM_KEY = "tasks:pending"


class TaskService:
    def __init__(self, task_repo: TaskRepository) -> None:
        self._task_repo = task_repo

    async def get_task(self, task_id: int, user_id: int) -> Task:
        """查询任务并验证其归属。通过 session.user_id 鉴权。"""
        task = await self._task_repo.find_by_id(task_id)
        if task is None:
            raise BusinessException.exc(StatusCode.TASK_NOT_FOUND.value)

        # 通过 session 验证归属
        from app.modules.session.repository.session_repository import SessionRepository
        db = self._task_repo._db
        session_repo = SessionRepository(db)
        session = await session_repo.find_by_id(task.session_id)
        if session is None or session.user_id != user_id:
            raise BusinessException.exc(StatusCode.TASK_ACCESS_DENIED.value)
        return task

    async def get_task_status(self, task_id: int, user_id: int) -> TaskStatusResponse:
        """返回轻量任务状态，供前端轮询。"""
        task = await self.get_task(task_id, user_id)
        progress: float | None = None
        if task.result and task.type == TaskType.SLIDE_BATCH:
            progress = task.result.get("progress")
        return TaskStatusResponse(
            id=task.id,
            status=task.status,
            progress=progress,
            error=task.error,
        )

    async def get_active_task_for_session(self, session_id: int, user_id: int) -> Task | None:
        """返回会话当前活跃（PENDING/RUNNING/STREAMING）任务，不存在则返回 None。"""
        from app.modules.session.repository.session_repository import SessionRepository
        db = self._task_repo._db
        session = await SessionRepository(db).find_by_id(session_id)
        if session is None or session.user_id != user_id:
            raise BusinessException.exc(StatusCode.SESSION_NOT_FOUND.value)
        tasks = await self._task_repo.find_running_by_session(session_id)
        return tasks[0] if tasks else None

    async def list_session_tasks(self, session_id: int) -> list[TaskResponse]:
        tasks = await self._task_repo.find_by_session(session_id)
        return [TaskResponse.model_validate(t) for t in tasks]

    async def cancel_task(self, task_id: int, user_id: int) -> bool:
        """取消未完成的任务，同时向 Redis 发布取消信号。"""
        await self.get_task(task_id, user_id)  # 鉴权
        cancelled = await self._task_repo.cancel(task_id)
        if not cancelled:
            raise BusinessException.exc(StatusCode.TASK_NOT_CANCELLABLE.value)

        # 发布取消信号（Worker 订阅并中止处理）
        try:
            from app.infrastructure.redis.redis import redis_client
            await redis_client.publish(
                f"task:{task_id}:cancel",
                json.dumps({"task_id": task_id}),
            )
        except Exception as e:
            logger.warning("Failed to publish cancel signal for task %d: %s", task_id, e)

        logger.info("Cancelled task %d by user %d", task_id, user_id)
        return True

    async def retry_task(self, task_id: int, user_id: int) -> Task:
        """重试 FAILED 状态的任务：重置状态并重新推入 Redis Stream。"""
        task = await self.get_task(task_id, user_id)
        if task.status != TaskStatus.FAILED:
            raise BusinessException.exc(StatusCode.TASK_NOT_RETRYABLE.value)

        await self._task_repo.update_status(task_id, TaskStatus.PENDING)
        await self._task_repo.increment_retry(task_id)

        # 重新推入 Redis Stream
        try:
            from app.infrastructure.redis.redis import redis_client
            payload = {
                "task_id": str(task.id),
                "session_id": str(task.session_id),
                "task_type": task.type.value,
                "retry": "true",
            }
            if task.trigger_message_id:
                payload["trigger_message_id"] = str(task.trigger_message_id)
            await redis_client.xadd(TASK_STREAM_KEY, payload, maxlen=500)
            logger.info("Re-enqueued task %d for retry", task_id)
        except Exception as e:
            logger.error("Failed to re-enqueue task %d: %s", task_id, e)
            raise

        await self._task_repo._db.refresh(task)
        return task

    async def mark_running(self, task_id: int) -> None:
        await self._task_repo.update_status(task_id, TaskStatus.RUNNING)

    async def mark_streaming(self, task_id: int) -> None:
        await self._task_repo.update_status(task_id, TaskStatus.STREAMING)

    async def mark_completed(self, task_id: int, result: dict) -> None:
        await self._task_repo.update_status(task_id, TaskStatus.COMPLETED, result=result)

    async def mark_failed(self, task_id: int, error: str) -> None:
        await self._task_repo.update_status(task_id, TaskStatus.FAILED, error=error)
        await self._task_repo.increment_retry(task_id)
