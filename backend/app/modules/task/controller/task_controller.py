from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.dependencies import CurrentUser, TaskRepoDepend, TaskServiceDepend
from app.common.result.result import Result
from app.modules.task.dto.response import TaskResponse, TaskStatusResponse

router = APIRouter(prefix="/tasks", tags=["任务管理"])


@router.get(
    "/{task_id}",
    response_model=Result[TaskResponse],
    summary="查询任务完整信息",
)
async def get_task(
    task_id: int,
    current_user: CurrentUser,
    task_svc: TaskServiceDepend,
) -> Result[TaskResponse]:
    # TODO: 验证任务归属当前用户，返回任务详情
    pass


@router.get(
    "/{task_id}/status",
    response_model=Result[TaskStatusResponse],
    summary="轮询任务状态（轻量）",
    description="前端可每秒轮询此接口获取任务状态与进度，不建议频率超过 1 次/秒",
)
async def get_task_status(
    task_id: int,
    current_user: CurrentUser,
    task_svc: TaskServiceDepend,
) -> Result[TaskStatusResponse]:
    # TODO: 验证归属，调用 task_svc.get_task_status
    pass


@router.post(
    "/{task_id}/cancel",
    response_model=Result[None],
    summary="取消一个进行中的任务",
)
async def cancel_task(
    task_id: int,
    current_user: CurrentUser,
    task_svc: TaskServiceDepend,
) -> Result[None]:
    # TODO: 验证归属，调用 task_svc.cancel_task
    pass


@router.post(
    "/{task_id}/retry",
    response_model=Result[TaskResponse],
    summary="重试一个失败的任务",
)
async def retry_task(
    task_id: int,
    current_user: CurrentUser,
    task_svc: TaskServiceDepend,
) -> Result[TaskResponse]:
    # TODO: 验证归属，调用 task_svc.retry_task
    pass


@router.get(
    "/{task_id}/stream",
    summary="SSE：订阅任务 token 流与进度事件",
    description=(
        "前端通过 EventSource 连接此接口，实时接收以下事件：\n"
        "- token：LLM 输出的文本片段\n"
        "- progress：SLIDE_BATCH 任务的完成进度（0.0~1.0）\n"
        "- done：任务完成，携带最终结果\n"
        "- error：任务失败，携带错误信息"
    ),
)
async def stream_task(
    task_id: int,
    current_user: CurrentUser,
    task_repo: TaskRepoDepend,
) -> StreamingResponse:
    # TODO: 验证归属；从 Redis 发布/订阅或内存队列读取事件并推送 SSE
    pass
