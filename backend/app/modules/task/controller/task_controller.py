from __future__ import annotations

import asyncio
import json
import secrets

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.dependencies import CurrentUser, TaskServiceDepend
from app.common.result.result import Result
from app.modules.task.dto.response import TaskResponse, TaskStatusResponse
from app.infrastructure.log.logging_config import get_logger
# redis_helper 封装了 JSON 序列化与带 TTL 的 set；裸 redis_client 不支持 ttl 关键字。
from app.infrastructure.redis.redis import redis_helper

logger = get_logger(__name__)

router = APIRouter(prefix="/tasks", tags=["任务管理"])

# SSE 一次性票据：EventSource 无法携带 Authorization 头，只能把凭据放 URL。
# 直接放 access token 会随 URL 进入 Nginx/代理/浏览器历史，泄露面大。
# 改为：先用正常 Bearer 鉴权换取一次性、短时效、仅绑定该任务的 ticket，
# 再用 ?ticket= 连 SSE；ticket 用后即删，泄露也仅 30s 内对单个任务有效。
_SSE_TICKET_PREFIX = "sse:ticket:"
_SSE_TICKET_TTL_SECONDS = 30


def _sse_frame(event: str, data: dict | str) -> str:
    """
    构造单条 SSE 帧。

    统一在此拼接 `event:` / `data:` 行与帧尾的空行，避免各处手写漏掉结尾的
    `\\n\\n`（漏掉会导致浏览器一直缓冲、整个流式失效）。data 为 dict 时序列化为
    JSON（不转义非 ASCII，保证中文 token 原样传输）。
    """
    payload = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


def _sse_comment(text: str) -> str:
    """SSE 注释行（以 ':' 开头），用于心跳与连接确认，不触发客户端事件。"""
    return f": {text}\n\n"


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


@router.post(
    "/{task_id}/stream-ticket",
    response_model=Result[dict],
    summary="换取 SSE 一次性票据",
    description=(
        "用正常的 Bearer 鉴权换取一个一次性、短时效（30s）、仅绑定该任务的票据，"
        "随后用 `GET /tasks/{id}/stream?ticket=<ticket>` 建立 SSE 连接。"
    ),
)
async def issue_stream_ticket(
    task_id: int,
    current_user: CurrentUser,
    task_svc: TaskServiceDepend,
) -> Result[dict]:
    # 归属校验：拿不到/无权访问会抛业务异常，由全局异常处理器统一返回
    await task_svc.get_task(task_id, current_user.id)

    ticket = secrets.token_urlsafe(32)
    await redis_helper.set(
        f"{_SSE_TICKET_PREFIX}{ticket}",
        {"user_id": current_user.id, "task_id": task_id},
        ttl=_SSE_TICKET_TTL_SECONDS,
    )
    return Result.success({"ticket": ticket, "expires_in": _SSE_TICKET_TTL_SECONDS})


@router.get(
    "/{task_id}/stream",
    summary="SSE：订阅任务 token 流与进度事件",
    description=(
        "通过 EventSource 连接，实时接收：\n"
        "- `token`：LLM 输出的文本片段（大纲/幻灯片生成中）\n"
        "- `progress`：SLIDE_BATCH 任务的完成进度 {current, total, percentage}\n"
        "- `done`：任务完成，含最终数据 {message_id, text, outline, slides}\n"
        "- `error`：任务失败，含错误信息\n\n"
        "SSE 鉴权：先调用 `POST /tasks/{id}/stream-ticket` 换取一次性票据，"
        "再通过 URL 参数 `?ticket=<ticket>` 传递。"
    ),
)
async def stream_task(
    task_id: int,
    task_svc: TaskServiceDepend,
    ticket: str = Query(..., description="一次性 SSE 票据（由 stream-ticket 接口换取）"),
) -> StreamingResponse:
    """
    SSE 流式推送实现：
    1. 校验一次性票据（用后即删），确认归属
    2. 订阅 Redis Pub/Sub 频道 `task:{task_id}:events`
    3. 将收到的事件格式化为 SSE 并推送给客户端
    4. 收到 done / error 事件或客户端断开后关闭订阅
    """
    # 校验票据：必须存在、绑定的 task_id 一致；校验后立即删除（一次性）
    ticket_key = f"{_SSE_TICKET_PREFIX}{ticket}"
    payload = await redis_helper.get(ticket_key)
    await redis_helper.delete(ticket_key)

    if not payload or payload.get("task_id") != task_id:
        async def _auth_error():
            yield _sse_frame("error", {"error": "Invalid or expired ticket"})
        return StreamingResponse(_auth_error(), media_type="text/event-stream")

    user_id = payload.get("user_id")

    # 双重保险：再校验一次任务归属（票据签发与连接之间状态可能变化）
    try:
        await task_svc.get_task(task_id, user_id)
    except Exception:
        async def _access_error():
            yield _sse_frame("error", {"error": "Task not found or access denied"})
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

    心跳策略：使用 get_message(timeout=...) 的轮询方式（而非 listen()）；
    这样当后端处于静默期（如 RAG/DB commit 段）时，仍可按固定节奏推送
    SSE 注释行，防止 Nginx/浏览器/上游代理因长时间无字节而切断连接。
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
    HEARTBEAT_INTERVAL = 15.0
    POLL_TIMEOUT = 1.0  # get_message 的单次超时
    deadline = asyncio.get_event_loop().time() + SSE_TIMEOUT

    try:
        await pubsub.subscribe(channel)
        # 立即推一行 SSE 注释，触发浏览器 onopen，避免 EventSource 因首字节迟到误判失败
        yield _sse_comment("connected")

        last_heartbeat = asyncio.get_event_loop().time()

        while True:
            now = asyncio.get_event_loop().time()
            if now >= deadline:
                logger.info(
                    "SSE task %d exceeded max lifetime (%ds), closing",
                    task_id, SSE_TIMEOUT,
                )
                yield _sse_frame("error", {"error": "SSE timeout"})
                break

            try:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=POLL_TIMEOUT
                )
            except Exception as e:
                logger.warning("SSE get_message error for task %d: %s", task_id, e)
                message = None

            if message is None:
                # 静默期：按固定节奏发心跳，保活 TCP/HTTP 链路
                if now - last_heartbeat >= HEARTBEAT_INTERVAL:
                    yield _sse_comment("heartbeat")
                    last_heartbeat = now
                continue

            if message.get("type") != "message":
                continue

            raw = message["data"]
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")

            try:
                event = json.loads(raw)
                event_type = event.get("type", "message")
                yield _sse_frame(event_type, event.get("data", {}))
                last_heartbeat = now

                if event_type in ("done", "error"):
                    logger.info("SSE task %d finished with event=%s", task_id, event_type)
                    break
            except json.JSONDecodeError:
                logger.warning("SSE received invalid JSON for task %d", task_id)
                continue

    except asyncio.CancelledError:
        logger.info("SSE client disconnected for task %d", task_id)
    except Exception as e:
        logger.error("SSE error for task %d: %s", task_id, e)
        yield _sse_frame("error", {"error": str(e)})
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
