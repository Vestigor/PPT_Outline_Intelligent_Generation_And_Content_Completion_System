from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
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
from app.infrastructure.redis.redis import redis_client
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """应用程序启动和关闭生命周期管理。"""
    setup_logging()

    # 创建所有数据库表（开发环境；生产环境请使用 Alembic 管理迁移）
    async with engine.begin() as conn:
        await conn.run_sync(BaseEntity.metadata.create_all)

    # 验证 Redis 连接
    await redis_client.ping()

    # 启动后台 Worker
    knowledge_task = asyncio.create_task(_start_knowledge_worker())
    task_task = asyncio.create_task(_start_task_worker())

    yield

    # 清理资源
    for t in (knowledge_task, task_task):
        t.cancel()
        try:
            await t
        except asyncio.CancelledError:
            pass

    await engine.dispose()
    await redis_client.aclose()


async def _start_knowledge_worker() -> None:
    """启动知识库文档处理 Worker（解析 / 分块 / Embedding）。"""
    from app.workers.knowledge_worker import KnowledgeWorker
    await KnowledgeWorker().start()


async def _start_task_worker() -> None:
    """启动异步任务执行 Worker（大纲生成 / 幻灯片批量生成）。"""
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
        "description": "用户注册、登录、退出及账号信息管理。注册时选择的 LLM 服务商不可更改。",
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
        "description": "查询异步任务状态并通过 SSE 订阅流式输出。大纲生成、内容生成等耗时操作均为异步任务。",
    },
    {
        "name": "知识库管理",
        "description": (
            "用户知识库文件的上传、管理和会话引用。\n\n"
            "文件上传后异步完成文本提取和向量化，状态流转：`pending → processing → ready`。\n"
            "只有 `ready` 状态的文件才会被 RAG 检索使用。"
        ),
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
        contact={
            "name": "同济大学 × 合合信息",
        },
        license_info={
            "name": "仅供课程展示使用",
        },
    )

    # 自定义 OpenAPI schema（注入 Bearer 安全方案）
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
        # 注入 Bearer Token 安全方案
        schema["components"] = schema.get("components", {})
        schema["components"]["securitySchemes"] = {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "登录后获取的 access_token，格式：`Bearer <token>`",
            }
        }
        # 为所有路径添加安全要求
        for path, path_item in schema.get("paths", {}).items():
            if path in ("/api/users/login", "/api/users/register"):
                continue
            for operation in path_item.values():
                if isinstance(operation, dict):
                    operation.setdefault("security", [{"BearerAuth": []}])
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi  # type: ignore[method-assign]

    # 跨域中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Gzip 压缩
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    # 注册全局异常处理器
    register_exception_handlers(app)

    # 注册路由
    app.include_router(api_router, prefix="/api")

    # 健康检查
    @app.get("/health", tags=["系统"], summary="健康检查", include_in_schema=True)
    async def health_check():
        return {"status": "ok", "version": settings.APP_VERSION}

    return app


app: FastAPI = create_app()