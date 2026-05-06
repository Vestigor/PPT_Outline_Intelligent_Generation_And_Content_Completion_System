from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager

_existing = os.environ.get("NO_PROXY", os.environ.get("no_proxy", ""))
_local = "localhost,127.0.0.1,::1"
if not any(h in _existing for h in ("localhost", "127.0.0.1")):
    _merged = f"{_existing},{_local}".lstrip(",")
    os.environ["NO_PROXY"] = _merged
    os.environ["no_proxy"] = _merged
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
try:
    from fastapi.openapi.utils import get_openapi
except ImportError:
    from fastapi._compat import get_openapi

from app.api.router import api_router
from app.common.exception.handlers import register_exception_handlers
from app.common.model.base_entity.base_entity import BaseEntity
from app.infrastructure.database.postgre_sql import postgres_engine as engine
from app.infrastructure.log.logging_config import setup_logging
from app.infrastructure.middleware import (
    AccessLogMiddleware,
    RequestIDMiddleware,
    SecurityHeadersMiddleware,
)
from app.infrastructure.redis.redis import redis_client
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    setup_logging()

    # 开发环境自动建表；生产环境请改用 Alembic 管理迁移
    async with engine.begin() as conn:
        await conn.run_sync(BaseEntity.metadata.create_all)

    await redis_client.ping()

    # 恢复因进程崩溃或 Redis 连接失败而滞留在 DB 中的任务
    await _recover_pending_tasks(startup=True)

    knowledge_task = asyncio.create_task(_start_knowledge_worker())
    task_task = asyncio.create_task(_start_task_worker())
    recovery_task = asyncio.create_task(_periodic_task_recovery())

    yield

    for t in (knowledge_task, task_task, recovery_task):
        t.cancel()
        try:
            await t
        except asyncio.CancelledError:
            pass

    await engine.dispose()
    await redis_client.aclose()


async def _recover_pending_tasks(*, startup: bool = False) -> None:
    """
    DB → Redis Stream 任务恢复。

    两种触发模式：
      - 启动恢复（startup=True）：将 RUNNING/STREAMING（之前进程崩溃留下的）一律重置为 PENDING
        再重推；PENDING 任务也立即重推。
      - 周期恢复（startup=False）：仅重推「在 PENDING 状态停留过久」的任务，
        以及 RUNNING/STREAMING 超时（≥ Worker 单任务超时）的僵尸任务。

    幂等保证：Worker 端用 DB 原子 UPDATE WHERE status=PENDING 切换状态，
    重复消息只会被一个 Worker 处理。
    """
    from datetime import datetime, timezone, timedelta
    from sqlalchemy import select, update as sa_update
    from app.infrastructure.database.postgre_sql import AsyncSessionLocal
    from app.common.model.entity.task import Task, TaskStatus
    from app.infrastructure.log.logging_config import get_logger

    _logger = get_logger(__name__)
    TASK_STREAM_KEY = "tasks:pending"

    # 比 TaskWorker.PER_TASK_TIMEOUT_SECONDS（600s）略大，
    # 确保正常超时由 Worker 自身处理（标记 FAILED），只接管真正崩溃残留的 RUNNING/STREAMING 任务
    RUNNING_TIMEOUT_SECONDS = 900
    PENDING_RECOVERY_LAG_SECONDS = 0 if startup else 60

    try:
        async with AsyncSessionLocal() as db:
            now = datetime.now(timezone.utc)
            pending_cutoff = now - timedelta(seconds=PENDING_RECOVERY_LAG_SECONDS)
            running_cutoff = now - timedelta(seconds=RUNNING_TIMEOUT_SECONDS)

            # 1) 重置僵尸 RUNNING/STREAMING（启动模式无视时长，周期模式只挑超时的）
            if startup:
                stmt = sa_update(Task).where(
                    Task.status.in_([TaskStatus.RUNNING, TaskStatus.STREAMING])
                ).values(status=TaskStatus.PENDING)
            else:
                stmt = sa_update(Task).where(
                    Task.status.in_([TaskStatus.RUNNING, TaskStatus.STREAMING]),
                    Task.updated_at < running_cutoff,
                ).values(status=TaskStatus.PENDING)
            reset_result = await db.execute(stmt)
            reset_count = reset_result.rowcount or 0
            if reset_count:
                _logger.warning(
                    "Reset %d stuck RUNNING/STREAMING task(s) → PENDING (startup=%s)",
                    reset_count, startup,
                )

            # 2) 抽取需重推的 PENDING 任务
            result = await db.execute(
                select(Task).where(
                    Task.status == TaskStatus.PENDING,
                    Task.updated_at <= pending_cutoff,
                )
            )
            stuck_tasks = list(result.scalars().all())
            await db.commit()

            if not stuck_tasks:
                return

            _logger.info(
                "Re-enqueueing %d PENDING task(s) (startup=%s)", len(stuck_tasks), startup
            )

            for task in stuck_tasks:
                payload: dict = {
                    "task_id": str(task.id),
                    "session_id": str(task.session_id),
                    "task_type": task.type.value,
                }
                if task.trigger_message_id:
                    payload["trigger_message_id"] = str(task.trigger_message_id)

                try:
                    await redis_client.xadd(TASK_STREAM_KEY, payload, maxlen=1000)
                except Exception as e:
                    _logger.warning("Re-enqueue failed for task %d: %s", task.id, e)

    except Exception as e:
        from app.infrastructure.log.logging_config import get_logger as _gl
        _gl(__name__).error("Task recovery failed: %s", e, exc_info=True)


async def _periodic_task_recovery() -> None:
    """每 60 秒扫描一次 DB，恢复积压或僵尸任务。"""
    while True:
        await asyncio.sleep(60)
        await _recover_pending_tasks(startup=False)


async def _start_knowledge_worker() -> None:
    from app.workers.knowledge_worker import KnowledgeWorker
    await KnowledgeWorker().start()


async def _start_task_worker() -> None:
    from app.workers.task_worker import TaskWorker
    await TaskWorker().start()


_DESCRIPTION = """
## PPT 大纲智能生成与内容补全系统

> 同济大学 × 合合信息 · 课程项目

本系统通过多轮对话帮助用户从一个模糊的想法出发，最终生成一份**有数据支撑、结构清晰、内容可靠**的 PPT 初稿。

---

### 核心流程

```
用户输入 → 需求收集（多轮） → 大纲生成（流式） → 大纲确认/修改 → 内容生成（并行 RAG）→ 导出
```

### 两种会话模式

| 模式 | 触发条件 | 特点 |
|------|----------|------|
| **引导式 (GUIDED)** | 纯文字描述主题 | 多轮对话收集需求，适合从零开始 |
| **报告驱动 (REPORT_DRIVEN)** | 首条消息携带文件 | 直接从文档提炼大纲，适合文档转 PPT |

### 认证

所有接口（除注册/登录外）需在 `Authorization` 头携带 Bearer Token：

```
Authorization: Bearer <access_token>
```

SSE 流式接口通过 `?token=<access_token>` URL 参数传递令牌。

### 流式输出（SSE）

触发大纲生成或内容生成后，通过 `GET /tasks/{task_id}/stream` 订阅实时进度：

| 事件类型 | 含义 |
|----------|------|
| `token` | LLM 输出的文本片段 |
| `progress` | 进度更新（0.0 ~ 1.0）|
| `done` | 任务完成，`result` 字段含最终结果 |
| `error` | 任务失败，`error` 字段含错误信息 |
"""

_TAGS_METADATA = [
    {
        "name": "用户管理",
        "description": "用户注册、登录、退出及账号信息管理。",
    },
    {
        "name": "会话管理",
        "description": (
            "PPT 创作会话的完整生命周期管理。\n\n"
            "**阶段流转（单向）**：\n"
            "`requirement_collection` → `outline_generation` → `outline_confirming`"
            " → `content_generation` → `content_confirming` → `completed`"
        ),
    },
    {
        "name": "任务管理",
        "description": "查询异步任务状态并通过 SSE 订阅流式输出。",
    },
    {
        "name": "知识库管理",
        "description": (
            "用户知识库文件的上传、管理和会话引用。\n\n"
            "文件上传后异步完成文本提取和向量化，状态流转：`pending → processing → ready`。"
        ),
    },
    {
        "name": "模型管理",
        "description": "LLM 提供商、模型及用户配置管理（含管理员操作）。",
    },
]


def create_app() -> FastAPI:
    app = FastAPI(
        title="PPT 智能生成系统 API",
        version=settings.APP_VERSION,
        description=_DESCRIPTION,
        openapi_tags=_TAGS_METADATA,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
        contact={"name": "同济大学 × 合合信息"},
        license_info={"name": "仅供课程展示使用"},
    )

    # ── 自定义 OpenAPI schema（注入 Bearer 安全方案）────────────────────────
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            tags=_TAGS_METADATA,
            routes=app.routes,
        )
        schema.setdefault("components", {})
        schema["components"]["securitySchemes"] = {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "登录后获取的 access_token，格式：`Bearer <token>`",
            }
        }
        for path, path_item in schema.get("paths", {}).items():
            if path in ("/api/users/login", "/api/users/register"):
                continue
            for operation in path_item.values():
                if isinstance(operation, dict):
                    operation.setdefault("security", [{"BearerAuth": []}])
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi  # type: ignore[method-assign]

    # ── 中间件（注册顺序 = 洋葱模型外→内，即最后注册的最先执行）──────────
    # 1. SecurityHeaders  — 最外层，为所有响应添加安全头
    app.add_middleware(SecurityHeadersMiddleware)
    # 2. GZip 压缩
    app.add_middleware(GZipMiddleware, minimum_size=settings.GZIP_MINIMUM_SIZE)
    # 3. AccessLog  — 在 RequestID 之后执行，可以读取 request_id
    app.add_middleware(AccessLogMiddleware)
    # 4. RequestID  — 最先执行，为后续中间件提供 request_id
    app.add_middleware(RequestIDMiddleware)
    # 5. CORS  — 标准跨域处理
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    # ── 全局异常处理器 ────────────────────────────────────────────────────────
    register_exception_handlers(app)

    # ── 路由 ──────────────────────────────────────────────────────────────────
    app.include_router(api_router, prefix="/api")

    @app.get("/health", tags=["系统"], summary="健康检查", include_in_schema=True)
    async def health_check():
        return {"status": "ok", "version": settings.APP_VERSION}

    return app


app: FastAPI = create_app()
