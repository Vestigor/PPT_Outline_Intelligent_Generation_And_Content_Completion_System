from __future__ import annotations

from app.common.model.entity.task import Task, TaskStatus, TaskType
from app.modules.task.dto.response import TaskResponse, TaskStatusResponse
from app.modules.task.repository.task_repository import TaskRepository


class TaskService:
    def __init__(self, task_repo: TaskRepository) -> None:
        self._task_repo = task_repo

    async def get_task(self, task_id: int, user_session_ids: list[int]) -> Task:
        """
        按 task_id 查询任务，并验证该任务所属 session 归属当前用户。
        user_session_ids：当前用户所有 session id 列表，用于鉴权。
        """
        # TODO: 查询任务，验证 task.session_id in user_session_ids
        pass

    async def get_task_status(self, task_id: int) -> TaskStatusResponse:
        """
        返回轻量任务状态，供前端轮询。
        SLIDE_BATCH 任务额外计算已完成幻灯片比例作为 progress。
        """
        # TODO: 查询任务，计算 progress（已完成幻灯片 / 总幻灯片数）
        pass

    async def list_session_tasks(self, session_id: int) -> list[TaskResponse]:
        """返回一个会话下的所有任务列表。"""
        tasks = await self._task_repo.find_by_session(session_id)
        return [TaskResponse.model_validate(t) for t in tasks]

    async def cancel_task(self, task_id: int) -> bool:
        """
        取消一个未完成的任务。
        已完成 / 已失败 / 已取消的任务不可取消，返回 False。
        """
        # TODO: 调用 TaskRepository.cancel，同时向 Redis 发送取消信号
        pass

    async def retry_task(self, task_id: int) -> Task:
        """
        重试一个 FAILED 状态的任务：
        重置状态为 PENDING，递增 retry_count，重新推入 Redis Stream。
        """
        # TODO: 验证任务状态为 FAILED，更新状态，XADD 到 Redis Stream
        pass

    async def enqueue(self, session_id: int, task_type: TaskType) -> Task:
        """
        创建任务记录并推入对应 Redis Stream。
        由 SessionService 调用，不直接暴露给 API。
        """
        # TODO: TaskRepository.create，然后 XADD 到 Redis Stream
        pass

    async def mark_running(self, task_id: int) -> None:
        """Worker 拉取任务后调用，将状态更新为 RUNNING。"""
        await self._task_repo.update_status(task_id, TaskStatus.RUNNING)

    async def mark_streaming(self, task_id: int) -> None:
        """LLM 开始流式输出后调用。"""
        await self._task_repo.update_status(task_id, TaskStatus.STREAMING)

    async def mark_completed(self, task_id: int, result: dict) -> None:
        """任务成功完成后由 Worker 调用。"""
        await self._task_repo.update_status(
            task_id, TaskStatus.COMPLETED, result=result
        )

    async def mark_failed(self, task_id: int, error: str) -> None:
        """任务失败后由 Worker 调用。"""
        await self._task_repo.update_status(
            task_id, TaskStatus.FAILED, error=error
        )
        await self._task_repo.increment_retry(task_id)
