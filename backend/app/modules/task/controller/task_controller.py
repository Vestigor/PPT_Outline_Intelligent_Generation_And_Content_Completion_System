from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.dependencies import CurrentUser, TaskServiceDepend
from app.common.result.result import Result
from app.modules.task.dto.response import TaskResponse, TaskStatusResponse
from app.infrastructure.log.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/tasks", tags=["任务管理"])


@router.get(
    "/sessions/{session_id}/active",
    response_model=Result[TaskResponse | None],
    summary="获取会话当前活跃任务",
)
async def get_active_task(
    session_id: int,
    current_user: CurrentUser,
    task_svc: TaskServiceDepend,
) -> Result[TaskResponse | None]:
    task = await task_svc.get_active_task_for_session(session_id, current_user.id)
    return Result.success(TaskResponse.model_validate(task) if task else None)


@router.get(
    "/{task_id}",
    response_model=Result[TaskResponse],
    summary="查询任务详情",
)
async def get_task(
    task_id: int,
    current_user: CurrentUser,
    task_svc: TaskServiceDepend,
) -> Result[TaskResponse]:
    task = await task_svc.get_task(task_id, current_user.id)
    return Result.success(TaskResponse.model_validate(task))


@router.get(
    "/{task_id}/status",
    response_model=Result[TaskStatusResponse],
    summary="轮询任务状态",
    description="前端可每秒轮询此接口。SLIDE_BATCH 任务含 progress (0.0~1.0)。",
)
async def get_task_status(
    task_id: int,
    current_user: CurrentUser,
    task_svc: TaskServiceDepend,
) -> Result[TaskStatusResponse]:
    status = await task_svc.get_task_status(task_id, current_user.id)
    return Result.success(status)


@router.post(
    "/{task_id}/cancel",
    response_model=Result[None],
    summary="取消进行中的任务",
)
async def cancel_task(
    task_id: int,
    current_user: CurrentUser,
    task_svc: TaskServiceDepend,
) -> Result[None]:
    await task_svc.cancel_task(task_id, current_user.id)
    return Result.success(None)


@router.post(
    "/{task_id}/retry",
    response_model=Result[TaskResponse],
    summary="重试失败的任务",
)
async def retry_task(
    task_id: int,
    current_user: CurrentUser,
    task_svc: TaskServiceDepend,
) -> Result[TaskResponse]:
    task = await task_svc.retry_task(task_id, current_user.id)
    return Result.success(TaskResponse.model_validate(task))


@router.get(
    "/{task_id}/stream",
    summary="SSE：订阅任务 token 流与进度事件",
    description=(
        "通过 EventSource 连接，实时接收：\n"
        "- `token`：LLM 输出的文本片段（大纲/幻灯片生成中）\n"
        "- `progress`：SLIDE_BATCH 任务的完成进度 {current, total, percentage}\n"
        "- `done`：任务完成，含最终数据 {message_id, text, outline, slides}\n"
        "- `error`：任务失败，含错误信息\n\n"
        "SSE 鉴权：通过 URL 参数 `?token=<access_token>` 传递。"
    ),
)
async def stream_task(
    task_id: int,
    task_svc: TaskServiceDepend,
    token: str = Query(..., description="Bearer access token"),
) -> StreamingResponse:
    """
    SSE 流式推送实现：
    1. 验证 token 并鉴权任务归属
    2. 订阅 Redis Pub/Sub 频道 `task:{task_id}:events`
    3. 将收到的事件格式化为 SSE 并推送给客户端
    4. 收到 done / error 事件或客户端断开后关闭订阅

    SSE 事件格式：
      event: <type>\n
      data: <json>\n
      \n
    """
    from app.infrastructure.security.security import decode_access_token

    # 验证 token
    try:
        payload = await decode_access_token(token)
        user_id = payload.get("sub")
        if user_id is None:
            raise ValueError("Missing sub in token")
        user_id = int(user_id)
    except Exception:
        async def _auth_error():
            data = json.dumps({"error": "Unauthorized"})
            yield f"event: error\ndata: {data}\n\n"
        return StreamingResponse(_auth_error(), media_type="text/event-stream")

    # 验证任务归属
    try:
        await task_svc.get_task(task_id, user_id)
    except Exception:
        async def _access_error():
            data = json.dumps({"error": "Task not found or access denied"})
            yield f"event: error\ndata: {data}\n\n"
        return StreamingResponse(_access_error(), media_type="text/event-stream")

    return StreamingResponse(
        _sse_generator(task_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


async def _sse_generator(task_id: int):
    """
    从 Redis Pub/Sub 频道读取事件并以 SSE 格式推送。
    频道名：task:{task_id}:events

    每个 SSE 订阅者使用独立的 Redis 连接，不占用共享连接池，
    避免大量并发 SSE 连接耗尽连接池导致普通 API 请求失败。
    """
    import redis.asyncio as aioredis
    from app.config import settings

    channel = f"task:{task_id}:events"
    logger.info("SSE client connected for task %d", task_id)

    # 每个订阅者创建独立连接，与共享池完全隔离
    sub_client = aioredis.from_url(
        settings.REDIS_URL,
        encoding=settings.REDIS_ENCODING,
        decode_responses=settings.REDIS_DECODE_RESPONSES,
        max_connections=2,
    )
    pubsub = sub_client.pubsub()

    # 最长订阅时间 30 分钟，防止僵尸连接长期占用资源
    SSE_TIMEOUT = 1800
    deadline = asyncio.get_event_loop().time() + SSE_TIMEOUT

    try:
        await pubsub.subscribe(channel)

        heartbeat_interval = 15
        last_heartbeat = asyncio.get_event_loop().time()

        async for message in pubsub.listen():
            now = asyncio.get_event_loop().time()

            # 超时保护
            if now >= deadline:
                logger.info("SSE task %d exceeded max lifetime (%ds), closing", task_id, SSE_TIMEOUT)
                yield f"event: error\ndata: {json.dumps({'error': 'SSE timeout'})}\n\n"
                break

            if message["type"] == "subscribe":
                yield ": heartbeat\n\n"
                continue

            if message["type"] != "message":
                continue

            raw = message["data"]
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")

            try:
                event = json.loads(raw)
                event_type = event.get("type", "message")
                event_data = json.dumps(event.get("data", {}), ensure_ascii=False)
                yield f"event: {event_type}\ndata: {event_data}\n\n"

                if event_type in ("done", "error"):
                    logger.info("SSE task %d finished with event=%s", task_id, event_type)
                    break
            except json.JSONDecodeError:
                logger.warning("SSE received invalid JSON for task %d", task_id)
                continue

            if now - last_heartbeat > heartbeat_interval:
                yield ": heartbeat\n\n"
                last_heartbeat = now

    except asyncio.CancelledError:
        logger.info("SSE client disconnected for task %d", task_id)
    except Exception as e:
        logger.error("SSE error for task %d: %s", task_id, e)
        error_data = json.dumps({"error": str(e)})
        yield f"event: error\ndata: {error_data}\n\n"
    finally:
        try:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()
        except Exception:
            pass
        try:
            await sub_client.aclose()
        except Exception:
            pass
        logger.info("SSE closed for task %d", task_id)
