from __future__ import annotations

import json

from fastapi import UploadFile

from app.common.exception.code import StatusCode
from app.common.exception.exception import BusinessException, AuthException
from app.common.model.entity.message import Message, MessageRole
from app.common.model.entity.session import Session, SessionStage, SessionType
from app.common.model.entity.task import Task, TaskType
from app.infrastructure.file.file_parser_service import DocumentParserService
from app.infrastructure.log.logging_config import get_logger
from app.modules.session.dto.response import SendMessageResponse, StartSessionResponse
from app.modules.session.repository.session_repository import (
    MessageRepository,
    OutlineRepository,
    ReportRepository,
    SessionRepository,
    SlideRepository,
)
from app.modules.task.repository.task_repository import TaskRepository

logger = get_logger(__name__)

# 任务推送到 Redis Stream 的键名
TASK_STREAM_KEY = "tasks:pending"


class SessionService:
    """
    会话业务逻辑服务，遵循 Controller → Service → Repository 分层原则。

    流程说明：
      GUIDED 会话：
        需求收集（多轮）→ 大纲生成（异步）→ 大纲确认/修改 → 内容生成（异步）→ 内容确认/修改 → 完成

      REPORT_DRIVEN 会话：
        大纲生成（异步，基于报告）→ 大纲确认/修改 → 内容生成（异步）→ 内容确认/修改 → 完成

    消息处理原则：
      1. 语义判断在 Service 层同步完成（快速 LLM 调用）
      2. 耗时生成任务推入 Redis Stream 由 TaskWorker 异步处理
      3. 流式输出通过 Redis Pub/Sub → SSE 传递给前端
    """

    def __init__(
        self,
        session_repo: SessionRepository,
        message_repo: MessageRepository,
        outline_repo: OutlineRepository,
        slide_repo: SlideRepository,
        report_repo: ReportRepository,
        task_repo: TaskRepository,
    ) -> None:
        self._session_repo = session_repo
        self._message_repo = message_repo
        self._outline_repo = outline_repo
        self._slide_repo = slide_repo
        self._report_repo = report_repo
        self._task_repo = task_repo

    # ──────────────────────────────────────────────
    # 公开接口
    # ──────────────────────────────────────────────

    async def start_session(
        self,
        user_id: int,
        llm_config_id: int | None,
        title: str,
        content: str,
        file: UploadFile | None = None,
        rag_enabled: bool = False,
        deep_search_enabled: bool = False,
    ) -> StartSessionResponse:
        """
        原子创建会话并处理第一条消息。
        若携带文件则判定为 REPORT_DRIVEN（跳过需求收集），否则为 GUIDED。
        """
        # 校验前置条件并解析"实际生效"的 LLM 配置：
        # 用户未显式指定时，回退到默认/最近一个 active 配置，
        # 把它的 id 写入 session.current_user_llm_config_id；
        # 否则该字段为 NULL，前端无法回显，task snapshot 也拿不到 id。
        resolved_llm_config_id = await self._validate_prereqs(
            user_id, llm_config_id, rag_enabled, deep_search_enabled
        )

        is_report_driven = file is not None
        session_type = SessionType.REPORT_DRIVEN if is_report_driven else SessionType.GUIDED
        initial_stage = (
            SessionStage.OUTLINE_GENERATION if is_report_driven
            else SessionStage.REQUIREMENT_COLLECTION
        )

        # 生成会话标题
        if not title:
            title = content[:50] if len(content) > 50 else content

        # 创建会话
        session = await self._session_repo.create(
            user_id=user_id,
            title=title,
            session_type=session_type,
            stage=initial_stage,
            llm_config_id=resolved_llm_config_id,
            rag_enabled=rag_enabled,
            deep_search_enabled=deep_search_enabled,
        )
        logger.info("Created session id=%d type=%s", session.id, session_type.value)

        # 处理报告文件
        if is_report_driven and file is not None:
            await self._save_report(session, file)

        # 创建第一条用户消息
        user_msg = await self._create_user_message(session, content)

        # 根据会话类型路由
        if is_report_driven:
            task = await self._enqueue_task(session, TaskType.OUTLINE_GENERATION, user_msg.id)
            return StartSessionResponse(
                session_id=session.id,
                message_id=user_msg.id,
                seq_no=user_msg.seq_no,
                task_id=task.id,
                streaming=True,
                reply="正在基于您的报告生成 PPT 大纲，请稍候…",
            )
        else:
            task = await self._enqueue_task(session, TaskType.REQUIREMENT_COLLECTION, user_msg.id)
            return StartSessionResponse(
                session_id=session.id,
                message_id=user_msg.id,
                seq_no=user_msg.seq_no,
                task_id=task.id,
                streaming=True,
                reply=None,
            )

    async def handle_message(
        self,
        session: Session,
        content: str,
    ) -> SendMessageResponse:
        """
        统一消息入口，按 session.stage 路由至对应处理方法。
        在进入阶段处理之前创建用户消息记录。

        并发保护：任何阶段，只要 session 内已有 PENDING/RUNNING/STREAMING 任务，
        都直接拒绝新消息（不写入消息表，不创建任务），把当前活跃 task_id 回传，
        前端据此恢复 SSE 订阅并展示"等待中"提示。这样避免：
          1) 同一会话被并发判定意图 / 多次入队 OUTLINE_GENERATION
          2) 重复用户消息污染对话历史
        """
        # 已完成的会话不再接收消息
        if session.stage == SessionStage.COMPLETED:
            raise BusinessException.exc(StatusCode.STAGE_MISMATCH.value)

        # 任何阶段都先做并发任务保护（不入库新用户消息）
        running = await self._task_repo.find_running_by_session(session.id)
        if running:
            raise BusinessException.exc(StatusCode.SESSION_TASK_IN_PROGRESS.value)

        user_msg = await self._create_user_message(session, content)

        if session.stage == SessionStage.REQUIREMENT_COLLECTION:
            return await self._route_requirement_collection(session, user_msg, content)

        if session.stage == SessionStage.OUTLINE_CONFIRMING:
            return await self._route_outline_confirming(session, user_msg, content)

        if session.stage == SessionStage.CONTENT_CONFIRMING:
            return await self._route_content_confirming(session, user_msg, content)

        # 仍在 OUTLINE_GENERATION/CONTENT_GENERATION 阶段但意外没有活跃任务：
        # 此时 stage 是上一轮任务结束前临时设置的，正常不会停留，
        # 如果停留说明上一个任务异常死亡，提示用户重试或刷新即可
        raise BusinessException.exc(StatusCode.STAGE_MISMATCH.value)

    async def get_session(self, user_id: int, session_id: int) -> Session:
        """获取会话，若不存在或不属于该用户则抛出异常。"""
        session = await self._session_repo.find_by_id_and_user(session_id, user_id)
        if session is None:
            raise BusinessException.exc(StatusCode.SESSION_NOT_FOUND.value)
        return session

    async def confirm_outline(self, session: Session) -> SendMessageResponse:
        """
        直接确认大纲并触发幻灯片生成，无需 LLM 语义判断。
        用于大纲编辑器中用户点击「确认生成」时调用。
        """
        if session.stage != SessionStage.OUTLINE_CONFIRMING:
            raise BusinessException.exc(StatusCode.STAGE_MISMATCH.value)

        session.stage = SessionStage.CONTENT_GENERATION
        await self._session_repo.update(session)

        outline = await self._outline_repo.find_latest_by_session(session.id)
        if outline:
            await self._outline_repo.confirm(outline.id)

        task = await self._enqueue_task(session, TaskType.SLIDE_BATCH)
        msg = await self._create_assistant_message(session, "大纲已确认，正在生成幻灯片内容，请稍候…")
        logger.info("Session %d: outline confirmed directly, enqueued SLIDE_BATCH task %d", session.id, task.id)

        return SendMessageResponse(
            session_id=session.id,
            message_id=msg.id,
            seq_no=msg.seq_no,
            task_id=task.id,
            streaming=True,
            reply="大纲已确认，正在生成幻灯片内容，请通过 SSE 获取进度。",
        )

    async def update_session_settings(
        self,
        session: Session,
        llm_config_id: int | None = None,
        rag_enabled: bool | None = None,
        deep_search_enabled: bool | None = None,
    ) -> Session:
        """更新会话设置（模型配置、RAG/DeepSearch 开关）。启用时校验对应配置是否存在。"""
        from app.modules.model.repository.model_repository import (
            UserRagConfigRepository,
            UserSearchConfigRepository,
        )
        db = self._session_repo._db

        if rag_enabled is True:
            rag_cfg = await UserRagConfigRepository(db).find_by_user(session.user_id)
            if rag_cfg is None:
                raise BusinessException.exc(StatusCode.USER_RAG_CONFIG_NOT_FOUND.value)

        if deep_search_enabled is True:
            search_cfg = await UserSearchConfigRepository(db).find_by_user(session.user_id)
            if search_cfg is None:
                raise BusinessException.exc(StatusCode.USER_SEARCH_CONFIG_NOT_FOUND.value)

        if llm_config_id is not None:
            session.current_user_llm_config_id = llm_config_id
        if rag_enabled is not None:
            session.rag_enabled = rag_enabled
        if deep_search_enabled is not None:
            session.deep_search_enabled = deep_search_enabled
        await self._session_repo.update(session)
        # Refresh to reload server-generated fields (updated_at) for Pydantic serialization
        await self._session_repo._db.refresh(session)
        logger.info("Updated session %d settings", session.id)
        return session

    # ──────────────────────────────────────────────
    # 阶段路由（私有）
    # ──────────────────────────────────────────────

    async def _route_requirement_collection(
        self,
        session: Session,
        user_msg: Message,
        content: str,
    ) -> SendMessageResponse:
        """REQUIREMENT_COLLECTION 阶段：创建需求收集任务，通过 SSE 流式回复。"""
        task = await self._enqueue_task(session, TaskType.REQUIREMENT_COLLECTION, user_msg.id)
        logger.info("Session %d: enqueued REQUIREMENT_COLLECTION task %d", session.id, task.id)
        return SendMessageResponse(
            session_id=session.id,
            message_id=user_msg.id,
            seq_no=user_msg.seq_no,
            task_id=task.id,
            streaming=True,
            reply=None,
        )

    async def _route_outline_confirming(
        self,
        session: Session,
        user_msg: Message,
        content: str,
    ) -> SendMessageResponse:
        """
        OUTLINE_CONFIRMING 阶段：异步意图判断。

        创建 INTENT_JUDGMENT 任务并立即返回 task_id；意图判断 + 后续动作
        （SLIDE_BATCH / OUTLINE_MODIFICATION / 引导回复）由 worker 完成，
        通过 SSE 推送给前端，HTTP 请求始终保持 < 200ms 响应。
        """
        task = await self._enqueue_task(session, TaskType.INTENT_JUDGMENT, user_msg.id)
        logger.info(
            "Session %d: enqueued INTENT_JUDGMENT task %d (outline_confirming)",
            session.id, task.id,
        )
        return SendMessageResponse(
            session_id=session.id,
            message_id=user_msg.id,
            seq_no=user_msg.seq_no,
            task_id=task.id,
            streaming=True,
            reply=None,
        )

    async def _route_content_confirming(
        self,
        session: Session,
        user_msg: Message,
        content: str,
    ) -> SendMessageResponse:
        """
        CONTENT_CONFIRMING 阶段：异步意图判断。
        与 _route_outline_confirming 同样把 LLM 判断挪到 worker 异步执行。
        """
        task = await self._enqueue_task(session, TaskType.INTENT_JUDGMENT, user_msg.id)
        logger.info(
            "Session %d: enqueued INTENT_JUDGMENT task %d (content_confirming)",
            session.id, task.id,
        )
        return SendMessageResponse(
            session_id=session.id,
            message_id=user_msg.id,
            seq_no=user_msg.seq_no,
            task_id=task.id,
            streaming=True,
            reply=None,
        )

    # ──────────────────────────────────────────────
    # 工具方法（私有）
    # ──────────────────────────────────────────────

    async def _create_user_message(self, session: Session, content: str) -> Message:
        session.message_count += 1
        await self._session_repo.update(session)
        return await self._message_repo.create(
            session_id=session.id,
            role=MessageRole.USER,
            seq_no=session.message_count,
            content=content,
        )

    async def _create_assistant_message(
        self,
        session: Session,
        content: str,
        outline_json: dict | None = None,
        slide_json: dict | None = None,
    ) -> Message:
        session.message_count += 1
        await self._session_repo.update(session)
        return await self._message_repo.create(
            session_id=session.id,
            role=MessageRole.ASSISTANT,
            seq_no=session.message_count,
            content=content,
            outline_json=outline_json,
            slide_json=slide_json,
        )

    async def _enqueue_task(
        self,
        session: Session,
        task_type: TaskType,
        trigger_message_id: int | None = None,
        extra: dict | None = None,
    ) -> Task:
        """创建 Task 记录并推入 Redis Stream。失败时最多重试 3 次。"""
        import asyncio as _asyncio
        task = await self._task_repo.create(
            session_id=session.id,
            task_type=task_type,
            trigger_message_id=trigger_message_id,
            snapshot_llm_config_id=session.current_user_llm_config_id,
            snapshot_rag_enabled=session.rag_enabled,
            snapshot_deep_search_enabled=session.deep_search_enabled,
        )

        from app.infrastructure.redis.redis import redis_client
        payload: dict = {
            "task_id": str(task.id),
            "session_id": str(session.id),
            "task_type": task_type.value,
        }
        if trigger_message_id:
            payload["trigger_message_id"] = str(trigger_message_id)
        if extra:
            payload["extra"] = json.dumps(extra, ensure_ascii=False)

        for attempt in range(3):
            try:
                await redis_client.xadd(TASK_STREAM_KEY, payload, maxlen=500)
                logger.info("Enqueued task %d type=%s to Redis", task.id, task_type.value)
                break
            except Exception as e:
                if attempt < 2:
                    await _asyncio.sleep(0.2 * (attempt + 1))
                else:
                    logger.error(
                        "Failed to push task %d to Redis after 3 attempts: %s — "
                        "task remains in DB and will be recovered on next startup",
                        task.id, e,
                    )

        return task

    async def _save_report(self, session: Session, file: UploadFile) -> None:
        """解析并保存报告文件。不支持的文件类型或内容为空时抛出 BusinessException。"""
        content = await file.read()
        file_type = file.content_type or "text/plain"

        logger.info(
            "Saving report for session %d: file=%s type=%s size=%d",
            session.id, file.filename, file_type, len(content),
        )

        if not DocumentParserService.is_supported(file_type):
            logger.warning(
                "Rejected unsupported report file type=%s for session %d", file_type, session.id
            )
            raise BusinessException.exc(StatusCode.REPORT_UNSUPPORTED_FILE_TYPE.value)

        parser = DocumentParserService()
        # parse() 内部会抛 BusinessException(UNSUPPORTED_FILE_TYPE / EMPTY_FILE_CONTENT / PARSE_FAILED)
        clean_text = parser.parse(content, file_type)
        content_hash = parser.compute_hash(clean_text)

        oss_key = f"reports/{session.id}/{file.filename or 'report'}"

        await self._report_repo.create(
            session_id=session.id,
            file_name=file.filename or "report",
            file_type=file_type,
            size_bytes=len(content),
            oss_key=oss_key,
            clean_text=clean_text,
            content_hash=content_hash,
        )
        logger.info(
            "Report saved for session %d: clean_text_len=%d hash=%s",
            session.id, len(clean_text), content_hash[:8],
        )

    async def _validate_prereqs(
        self,
        user_id: int,
        llm_config_id: int | None,
        rag_enabled: bool,
        deep_search_enabled: bool,
    ) -> int:
        """
        创建会话前校验并解析"实际生效"的 LLM 配置 ID：
          - 显式传入 llm_config_id 时校验其存在性后原样返回
          - 未传入时通过 resolve_active_llm_config 取默认/活跃配置，并返回其 id
        返回值会被写入 session.current_user_llm_config_id，
        避免该字段为 NULL 导致前端无法回显、task 快照拿不到配置。
        """
        from app.modules.model.repository.model_repository import (
            UserLLMConfigRepository,
            UserRagConfigRepository,
            UserSearchConfigRepository,
            resolve_active_llm_config,
        )
        db = self._session_repo._db

        if llm_config_id is not None:
            cfg = await UserLLMConfigRepository(db).find_by_id_and_user(llm_config_id, user_id)
            if cfg is None:
                raise BusinessException.exc(StatusCode.USER_LLM_CONFIG_NOT_FOUND.value)
            resolved_id = cfg.id
        else:
            cfg = await resolve_active_llm_config(db, user_id)
            resolved_id = cfg.id

        if rag_enabled:
            rag_cfg = await UserRagConfigRepository(db).find_by_user(user_id)
            if rag_cfg is None:
                raise BusinessException.exc(StatusCode.USER_RAG_CONFIG_NOT_FOUND.value)

        if deep_search_enabled:
            search_cfg = await UserSearchConfigRepository(db).find_by_user(user_id)
            if search_cfg is None:
                raise BusinessException.exc(StatusCode.USER_SEARCH_CONFIG_NOT_FOUND.value)

        return resolved_id

