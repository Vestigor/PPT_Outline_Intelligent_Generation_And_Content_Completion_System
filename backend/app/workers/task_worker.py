from __future__ import annotations

import asyncio
import json
import os

from sqlalchemy import update

from app.common.model.entity.message import MessageRole
from app.common.model.entity.session import SessionStage, SessionType
from app.common.model.entity.task import Task, TaskStatus, TaskType
from app.infrastructure.log.logging_config import get_logger
from app.infrastructure.prompt.prompt_loader import PromptLoader
from app.infrastructure.schema_loader.schema_loader import SchemaLoader

logger = get_logger(__name__)

TASK_STREAM_KEY = "tasks:pending"
CONSUMER_GROUP = "task_workers"
CONSUMER_NAME = f"worker-{os.getpid()}"
BATCH_SIZE = 10
BLOCK_MS = 5000
TASK_STREAM_MAXLEN = 1000  # approximate max entries kept in stream (MAXLEN ~)
MAX_CONCURRENT_TASKS = 4
PER_TASK_TIMEOUT_SECONDS = 600  # 10 minutes hard cap to avoid stuck workers
PEL_MIN_IDLE_MS = 60_000  # claim other consumers' messages idle ≥ 60s


class TaskWorker:
    """
    异步任务执行 Worker（Redis Stream Consumer Group 模式）。

    设计要点：
      - 消费 tasks:pending 流，按任务类型分发至对应处理器
      - 多任务并发执行（asyncio.create_task + Semaphore），避免单任务阻塞流
      - 每任务硬超时（PER_TASK_TIMEOUT_SECONDS），防止 LLM 端无限挂起
      - DB 原子状态切换（PENDING → RUNNING）保证幂等，重复消息直接 ACK
      - 启动时认领自己 PEL + 接管 idle 过久的孤儿消息
      - 任务在 DB 仍是 PENDING 时，定时器从 DB 重推入 stream，实现端到端可恢复

    任务类型：
      - REQUIREMENT_COLLECTION  需求收集阶段 LLM 对话（流式输出）
      - OUTLINE_GENERATION      大纲生成（流式输出 JSON）
      - OUTLINE_MODIFICATION    大纲修改（流式输出 JSON）
      - SLIDE_BATCH             批量幻灯片生成（并行 + 进度广播）
      - SLIDE_MODIFICATION      幻灯片修改（流式输出 JSON）

    SSE 推送机制：
      通过 Redis Pub/Sub 频道 `task:{task_id}:events` 发布事件，
      task_controller 的 SSE 端点订阅并转发给前端。

    事件格式：
      {"type": "token",    "data": {"token": "..."}}
      {"type": "progress", "data": {"current": 3, "total": 10, "percentage": 0.3}}
      {"type": "done",     "data": {"message_id": 123, "text": "...", "outline": {...}, "slides": {...}}}
      {"type": "error",    "data": {"error": "..."}}
    """

    def __init__(self) -> None:
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
        self._inflight: set[asyncio.Task] = set()

    async def start(self) -> None:
        await self._ensure_consumer_group()
        logger.info(
            "TaskWorker started: stream=%s consumer=%s concurrency=%d",
            TASK_STREAM_KEY, CONSUMER_NAME, MAX_CONCURRENT_TASKS,
        )
        await self._recover_pending()
        await self._claim_orphan_messages()
        while True:
            try:
                await self._process_batch()
            except Exception as exc:
                logger.error("TaskWorker loop error: %s", exc, exc_info=True)
                await asyncio.sleep(3)

    async def _recover_pending(self) -> None:
        """启动时回收本 Consumer 自己 PEL 中尚未 ACK 的消息（一次性，非阻塞）。"""
        from app.infrastructure.redis.redis import redis_client
        recovered = 0
        try:
            results = await redis_client.xreadgroup(
                CONSUMER_GROUP, CONSUMER_NAME,
                {TASK_STREAM_KEY: "0"},
                count=BATCH_SIZE,
                block=100,  # 100ms — only check current PEL, never block
            )
        except Exception as e:
            logger.warning("PEL recovery read failed: %s", e)
            return

        if not results:
            logger.debug("PEL recovery: no pending messages")
            return

        for _, messages in results:
            for message_id, payload in messages:
                task_id_str = payload.get("task_id")
                task_id = int(task_id_str) if task_id_str else 0

                # 终态任务直接 ACK，不再处理
                if task_id and await self._is_terminal_task(task_id):
                    await redis_client.xack(TASK_STREAM_KEY, CONSUMER_GROUP, message_id)
                    continue

                logger.info(
                    "Recovering PEL message %s (task_id=%s)", message_id, task_id_str
                )
                recovered += 1
                # 异步处理，避免顺序阻塞
                self._spawn_task(message_id, payload)

        logger.info("PEL recovery: spawned %d task(s) from own PEL", recovered)

    async def _claim_orphan_messages(self) -> None:
        """
        接管其他 Consumer 留下的孤儿消息（idle > PEL_MIN_IDLE_MS）。
        典型场景：Pod 重启、Consumer 名变化导致原 PEL 残留。
        """
        from app.infrastructure.redis.redis import redis_client
        claimed = 0
        try:
            # XAUTOCLAIM 自动转移 idle 过久的消息归属，并返回 [next_cursor, [(id, fields)...]]
            cursor = "0-0"
            for _ in range(5):  # 至多扫 5 批，避免长占主循环
                resp = await redis_client._client.xautoclaim(  # type: ignore[attr-defined]
                    name=TASK_STREAM_KEY,
                    groupname=CONSUMER_GROUP,
                    consumername=CONSUMER_NAME,
                    min_idle_time=PEL_MIN_IDLE_MS,
                    start_id=cursor,
                    count=BATCH_SIZE,
                )
                # redis-py 7.x 返回 (next_cursor, claimed_msgs, deleted_ids)
                next_cursor = resp[0]
                msgs = resp[1] or []
                if not msgs:
                    break
                for message_id, fields in msgs:
                    fields = fields or {}
                    task_id_str = fields.get("task_id")
                    task_id = int(task_id_str) if task_id_str else 0
                    if task_id and await self._is_terminal_task(task_id):
                        await redis_client.xack(TASK_STREAM_KEY, CONSUMER_GROUP, message_id)
                        continue
                    claimed += 1
                    self._spawn_task(message_id, fields)
                cursor = next_cursor or "0-0"
                if cursor in (b"0-0", "0-0"):
                    break
        except AttributeError:
            # redis-py 6.x 没有 xautoclaim，回退到 noop
            pass
        except Exception as e:
            logger.warning("Orphan message claim failed: %s", e)

        if claimed:
            logger.info("Claimed %d orphan PEL message(s) from other consumers", claimed)

    async def _ensure_consumer_group(self) -> None:
        from app.infrastructure.redis.redis import redis_client
        try:
            await redis_client.xgroup_create(
                TASK_STREAM_KEY, CONSUMER_GROUP, id="$", mkstream=True
            )
        except Exception:
            pass  # group already exists

    async def _process_batch(self) -> None:
        from app.infrastructure.redis.redis import redis_client
        try:
            results = await redis_client.xreadgroup(
                CONSUMER_GROUP,
                CONSUMER_NAME,
                {TASK_STREAM_KEY: ">"},
                count=BATCH_SIZE,
                block=BLOCK_MS,
            )
        except Exception as e:
            logger.error("XREADGROUP error: %s", e)
            await asyncio.sleep(1)
            return

        if not results:
            # 周期性接管孤儿消息（每次空闲循环顺便清理 PEL）
            await self._claim_orphan_messages()
            return

        for _, messages in results:
            for message_id, payload in messages:
                self._spawn_task(message_id, payload)

    def _spawn_task(self, message_id: str, payload: dict) -> None:
        """创建一个独立 asyncio 任务处理消息，受全局 Semaphore 限流。"""
        async def _runner() -> None:
            async with self._semaphore:
                await self._process_message(message_id, payload)

        t = asyncio.create_task(_runner())
        self._inflight.add(t)
        t.add_done_callback(self._inflight.discard)

    async def _process_message(self, message_id: str, payload: dict) -> None:
        """处理单条消息的完整流程：原子切换 → 派发 → ACK。"""
        from app.infrastructure.redis.redis import redis_client

        task_id_str = payload.get("task_id")
        task_id = int(task_id_str) if task_id_str else 0

        # 1) 终态任务直接 ACK
        if task_id and await self._is_terminal_task(task_id):
            try:
                await redis_client.xack(TASK_STREAM_KEY, CONSUMER_GROUP, message_id)
            except Exception:
                pass
            return

        # 2) 原子状态切换 PENDING → RUNNING（防止多 Worker 重复处理）
        if task_id and not await self._claim_task_for_running(task_id):
            logger.info(
                "Task %d is not in PENDING state; another worker may be processing it. ACK msg %s",
                task_id, message_id,
            )
            try:
                await redis_client.xack(TASK_STREAM_KEY, CONSUMER_GROUP, message_id)
            except Exception:
                pass
            return

        # 3) 在硬超时下派发处理
        try:
            await asyncio.wait_for(
                self._dispatch(payload),
                timeout=PER_TASK_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            logger.error(
                "Task %d timed out after %ds, marking failed", task_id, PER_TASK_TIMEOUT_SECONDS
            )
            if task_id:
                await self._mark_failed_and_notify(task_id, "任务执行超时，请重试")
        except Exception as e:
            logger.error(
                "Task dispatch failed for msg %s task_id=%d: %s",
                message_id, task_id, e, exc_info=True,
            )
            if task_id:
                await self._mark_failed_and_notify(task_id, str(e))
        finally:
            try:
                await redis_client.xack(TASK_STREAM_KEY, CONSUMER_GROUP, message_id)
            except Exception as e:
                logger.warning("XACK failed for msg %s: %s", message_id, e)

    async def _claim_task_for_running(self, task_id: int) -> bool:
        """
        原子地将任务从 PENDING 切到 RUNNING；返回 True 表示当前 Worker 持有该任务。
        其他状态（已 RUNNING/STREAMING/COMPLETED 等）一律视为他人处理中或已结束。
        """
        try:
            async with self._get_db_session() as db:
                result = await db.execute(
                    update(Task)
                    .where(Task.id == task_id, Task.status == TaskStatus.PENDING)
                    .values(status=TaskStatus.RUNNING)
                )
                await db.commit()
                return result.rowcount > 0
        except Exception as e:
            logger.warning("Failed to claim task %d for running: %s", task_id, e)
            return False

    async def _dispatch(self, payload: dict) -> None:
        task_id = int(payload["task_id"])
        task_type = TaskType(payload["task_type"])
        extra: dict = json.loads(payload["extra"]) if payload.get("extra") else {}

        if task_type == TaskType.REQUIREMENT_COLLECTION:
            await self._handle_requirement_collection(task_id)
        elif task_type == TaskType.OUTLINE_GENERATION:
            await self._handle_outline_generation(task_id)
        elif task_type == TaskType.OUTLINE_MODIFICATION:
            await self._handle_outline_modification(task_id, extra)
        elif task_type == TaskType.SLIDE_BATCH:
            await self._handle_slide_batch(task_id)
        elif task_type == TaskType.SLIDE_MODIFICATION:
            await self._handle_slide_modification(task_id, extra)
        elif task_type == TaskType.INTENT_JUDGMENT:
            await self._handle_intent_judgment(task_id)
        else:
            logger.warning("Unknown task type: %s", task_type)

    # ──────────────────────────────────────────────
    # 任务处理器
    # ──────────────────────────────────────────────

    async def _handle_requirement_collection(self, task_id: int) -> None:
        """
        需求收集阶段处理：
        1. 加载会话历史和当前需求状态
        2. 调用 LLM 判断需求是否完整 + 生成回复
        3. 流式输出回复文本
        4. 若需求完整则触发大纲生成任务
        """
        async with self._get_db_session() as db:
            from app.modules.session.repository.session_repository import (
                MessageRepository,
                SessionRepository,
            )
            from app.modules.task.repository.task_repository import TaskRepository

            task_repo = TaskRepository(db)
            await task_repo.update_status(task_id, TaskStatus.RUNNING)

            task = await task_repo.find_by_id(task_id)
            if task is None:
                return

            session_repo = SessionRepository(db)
            message_repo = MessageRepository(db)
            session = await session_repo.find_by_id(task.session_id)
            if session is None:
                return

            llm = await self._build_llm_client(task, session, db)
            if llm is None:
                await self._mark_failed_and_notify(task_id, "LLM 未配置或已停用，请添加有效的 LLM 配置")
                return

            req = session.requirements or {}
            collected_str = json.dumps(req, ensure_ascii=False, indent=2) if req else "（尚未收集到任何需求）"

            trigger_msg_id = task.trigger_message_id

            schema = SchemaLoader.load("requirement_judge_schema")
            system_prompt = PromptLoader.load(
                "requirement_judge",
                session_type=session.session_type,
                collected_requirements=collected_str,
            )

            # 取最近对话历史（含本次用户消息）作为 messages
            history = await message_repo.find_conversation_history(session.id, limit=10)
            messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
            messages.extend(history)

            try:
                judgment = await llm.chat_with_schema(
                    messages,
                    schema,
                    temperature=0.3,
                )
            except Exception as e:
                await self._mark_failed_and_notify(task_id, f"LLM 调用失败: {e}")
                return

            extracted = judgment.get("extracted", {})
            user_wants_to_proceed = bool(judgment.get("user_wants_to_proceed", False))
            is_complete = bool(judgment.get("is_complete", False))
            reply_text = judgment.get("reply") or "请继续描述您的需求。"

            new_req = dict(req)
            for field in ("topic", "audience", "duration_minutes", "style", "focus_points"):
                val = extracted.get(field)
                if val is not None:
                    new_req[field] = val

            has_topic = bool(new_req.get("topic"))
            secondary_fields_count = sum(
                1 for k in ("audience", "duration_minutes", "style", "focus_points")
                if new_req.get(k)
            )

            # ── 服务端硬规则（覆盖 LLM 判断）─────────────────────────────
            # 1. 没有 topic 永远不能完成
            if is_complete and not has_topic:
                is_complete = False
                reply_text = (
                    "好的！不过我需要先知道您要做什么主题的 PPT。"
                    "请告诉我这次演示的主题或核心内容方向。"
                )
            # 2. 用户没有明确要求进入下一步、且收集的信息维度不够时，强制继续追问
            elif (
                is_complete
                and not user_wants_to_proceed
                and has_topic
                and secondary_fields_count < 2
            ):
                is_complete = False
                if not new_req.get("audience"):
                    reply_text = (
                        f"好的，主题是「{new_req['topic']}」。"
                        "请问这个 PPT 主要讲给谁听？比如学生、同事、客户等。"
                        "（如果不需要补充其他要求，您可以直接说\"开始生成\"）"
                    )
                elif not new_req.get("duration_minutes"):
                    reply_text = (
                        f"好的，受众是「{new_req['audience']}」。"
                        "请问演示时长大约多少分钟？"
                        "（如果不需要补充其他要求，您可以直接说\"开始生成\"）"
                    )
                elif not new_req.get("style"):
                    reply_text = (
                        "请问您希望 PPT 的风格偏向哪种？比如学术、商务、活泼或极简。"
                        "（如果不需要补充其他要求，您可以直接说\"开始生成\"）"
                    )
                else:
                    reply_text = (
                        "还有什么内容需要重点强调的吗？"
                        "（如果不需要补充其他要求，您可以直接说\"开始生成\"）"
                    )

            session.requirements = new_req
            session.requirements_complete = is_complete
            if is_complete:
                session.stage = SessionStage.OUTLINE_GENERATION
            await session_repo.update(session)

            await self._stream_text(task_id, reply_text)

            session.message_count += 1
            await session_repo.update(session)
            assistant_msg = await message_repo.create(
                session_id=session.id,
                role=MessageRole.ASSISTANT,
                seq_no=session.message_count,
                content=reply_text,
            )
            await db.commit()

            next_task_id: int | None = None
            if is_complete:
                new_task = await task_repo.create(
                    session_id=session.id,
                    task_type=TaskType.OUTLINE_GENERATION,
                    trigger_message_id=trigger_msg_id,
                )
                next_task_id = new_task.id
                from app.infrastructure.redis.redis import redis_client
                await redis_client.xadd(TASK_STREAM_KEY, {
                    "task_id": str(new_task.id),
                    "session_id": str(session.id),
                    "task_type": TaskType.OUTLINE_GENERATION.value,
                }, maxlen=TASK_STREAM_MAXLEN)
                await db.commit()
                logger.info(
                    "Requirements complete, enqueued OUTLINE_GENERATION task %d", new_task.id
                )

            await self._publish_done(task_id, {
                "message_id": assistant_msg.id,
                "text": reply_text,
                "outline": None,
                "slides": None,
                "requirements_complete": is_complete,
                "next_task_id": next_task_id,
            })
            await task_repo.update_status(
                task_id,
                TaskStatus.COMPLETED,
                result={"requirements_complete": is_complete},
            )
            await db.commit()

    async def _handle_outline_generation(self, task_id: int) -> None:
        """
        大纲生成：
        1. 加载 session + requirements（GUIDED）或 report（REPORT_DRIVEN）
        2. 构造 Prompt，流式调用 LLM
        3. 解析 JSON，存入 Outline 表
        4. 创建 assistant 消息（text + outline_json）
        5. 推进阶段 → OUTLINE_CONFIRMING
        """
        async with self._get_db_session() as db:
            from app.modules.session.repository.session_repository import (
                MessageRepository,
                OutlineRepository,
                ReportRepository,
                SessionRepository,
            )
            from app.modules.task.repository.task_repository import TaskRepository

            task_repo = TaskRepository(db)
            await task_repo.update_status(task_id, TaskStatus.RUNNING)

            task = await task_repo.find_by_id(task_id)
            if task is None:
                return

            session_repo = SessionRepository(db)
            message_repo = MessageRepository(db)
            outline_repo = OutlineRepository(db)
            report_repo = ReportRepository(db)
            session = await session_repo.find_by_id(task.session_id)
            if session is None:
                return

            llm = await self._build_llm_client(task, session, db)
            if llm is None:
                await self._mark_failed_and_notify(task_id, "LLM 未配置或已停用，请添加有效的 LLM 配置")
                return

            if session.session_type == SessionType.REPORT_DRIVEN:
                report = await report_repo.find_by_session(session.id)
                report_text = (report.clean_text or "（报告内容为空）") if report else "（未找到报告）"
                trigger_msg = None
                if task.trigger_message_id:
                    trigger_msg = await message_repo.find_by_id(task.trigger_message_id)
                user_note = trigger_msg.content if trigger_msg else ""
                prompt = PromptLoader.load(
                    "outline_generate",
                    session_type=session.session_type,
                    report_text=report_text[:8000],
                    user_note=user_note or "",
                )
            else:
                req = session.requirements or {}
                prompt = PromptLoader.load(
                    "outline_generate",
                    session_type=session.session_type,
                    topic=req.get("topic", "未指定"),
                    audience=req.get("audience", "未指定"),
                    duration_minutes=str(req.get("duration_minutes", "不限")),
                    style=req.get("style", "不限"),
                    focus_points=", ".join(req.get("focus_points") or []) or "无",
                )

            await task_repo.update_status(task_id, TaskStatus.STREAMING)
            full_text = await self._stream_and_collect(task_id, llm, prompt)

            try:
                outline_json = self._extract_json(full_text)
            except Exception as e:
                await self._mark_failed_and_notify(task_id, f"大纲 JSON 解析失败: {e}")
                return

            version = await outline_repo.get_next_version(session.id)
            outline = await outline_repo.create(session.id, version, outline_json)

            session.stage = SessionStage.OUTLINE_CONFIRMING
            await session_repo.update(session)

            reply_text = "大纲已生成，请查看并告诉我您是否满意，或提出修改意见。"
            session.message_count += 1
            await session_repo.update(session)
            assistant_msg = await message_repo.create(
                session_id=session.id,
                role=MessageRole.ASSISTANT,
                seq_no=session.message_count,
                content=reply_text,
                outline_json=outline_json,
            )

            await task_repo.update_status(
                task_id, TaskStatus.COMPLETED, result={"outline_id": outline.id}
            )
            await db.commit()

            await self._publish_done(task_id, {
                "message_id": assistant_msg.id,
                "text": reply_text,
                "outline": outline_json,
                "slides": None,
            })
            logger.info(
                "Outline generated: session=%d version=%d", session.id, version
            )

    async def _handle_outline_modification(self, task_id: int, extra: dict) -> None:
        """大纲修改：基于当前大纲和修改要求，生成新版本大纲。"""
        async with self._get_db_session() as db:
            from app.modules.session.repository.session_repository import (
                MessageRepository,
                OutlineRepository,
                ReportRepository,
                SessionRepository,
            )
            from app.modules.task.repository.task_repository import TaskRepository

            task_repo = TaskRepository(db)
            await task_repo.update_status(task_id, TaskStatus.RUNNING)
            task = await task_repo.find_by_id(task_id)
            if task is None:
                return

            session_repo = SessionRepository(db)
            message_repo = MessageRepository(db)
            outline_repo = OutlineRepository(db)
            report_repo = ReportRepository(db)
            session = await session_repo.find_by_id(task.session_id)
            if session is None:
                return

            llm = await self._build_llm_client(task, session, db)
            if llm is None:
                await self._mark_failed_and_notify(task_id, "LLM 未配置或已停用，请添加有效的 LLM 配置")
                return

            current_outline = await outline_repo.find_latest_by_session(session.id)
            if current_outline is None:
                await self._mark_failed_and_notify(task_id, "未找到当前大纲")
                return

            modification_request = extra.get("modification_request", "")
            # Fallback: if extra was lost (e.g. task recovered from DB), read from trigger message
            if not modification_request and task.trigger_message_id:
                trigger_msg = await message_repo.find_by_id(task.trigger_message_id)
                if trigger_msg and trigger_msg.content:
                    modification_request = trigger_msg.content
            kwargs: dict[str, str] = {
                "current_outline": json.dumps(
                    current_outline.outline_json, ensure_ascii=False
                ),
                "modification_request": modification_request,
            }
            if session.session_type == SessionType.REPORT_DRIVEN:
                report = await report_repo.find_by_session(session.id)
                kwargs["report_text"] = (report.clean_text or "")[:6000] if report else ""

            prompt = PromptLoader.load(
                "outline_modify", session_type=session.session_type, **kwargs
            )

            await task_repo.update_status(task_id, TaskStatus.STREAMING)
            full_text = await self._stream_and_collect(task_id, llm, prompt)

            try:
                outline_json = self._extract_json(full_text)
            except Exception as e:
                await self._mark_failed_and_notify(task_id, f"大纲 JSON 解析失败: {e}")
                return

            version = await outline_repo.get_next_version(session.id)
            outline = await outline_repo.create(session.id, version, outline_json)

            reply_text = "大纲已按您的要求更新，请确认修改后的版本是否满意。"
            session.message_count += 1
            await session_repo.update(session)
            assistant_msg = await message_repo.create(
                session_id=session.id,
                role=MessageRole.ASSISTANT,
                seq_no=session.message_count,
                content=reply_text,
                outline_json=outline_json,
            )

            await task_repo.update_status(
                task_id, TaskStatus.COMPLETED, result={"outline_id": outline.id}
            )
            await db.commit()
            await self._publish_done(task_id, {
                "message_id": assistant_msg.id,
                "text": reply_text,
                "outline": outline_json,
                "slides": None,
            })

    async def _handle_slide_batch(self, task_id: int) -> None:
        """
        批量幻灯片生成：
        1. 加载确认后的大纲
        2. 逐幻灯片检索 RAG（每张幻灯片单独检索，结果合并去重）
        3. DeepSearch（使用用户配置的 Tavily API Key）
        4. 调用 LLM 生成完整幻灯片 JSON
        5. 存储 Slide，推进阶段 → CONTENT_CONFIRMING
        """
        async with self._get_db_session() as db:
            from app.modules.session.repository.session_repository import (
                KnowledgeRefRepository,
                MessageRepository,
                OutlineRepository,
                ReportRepository,
                SessionRepository,
                SlideRepository,
            )
            from app.modules.task.repository.task_repository import TaskRepository

            task_repo = TaskRepository(db)
            await task_repo.update_status(task_id, TaskStatus.RUNNING)
            task = await task_repo.find_by_id(task_id)
            if task is None:
                return

            session_repo = SessionRepository(db)
            message_repo = MessageRepository(db)
            outline_repo = OutlineRepository(db)
            slide_repo = SlideRepository(db)
            report_repo = ReportRepository(db)
            session = await session_repo.find_by_id(task.session_id)
            if session is None:
                return

            llm = await self._build_llm_client(task, session, db)
            if llm is None:
                await self._mark_failed_and_notify(task_id, "LLM 未配置或已停用，请添加有效的 LLM 配置")
                return

            outline = await outline_repo.find_latest_by_session(session.id)
            if outline is None:
                await self._mark_failed_and_notify(task_id, "未找到大纲")
                return

            req = session.requirements or {}

            # ── 解析大纲结构（兼容新旧字段命名）─────────────────────────────
            outline_data = outline.outline_json
            chapters = outline_data.get("chapters") or outline_data.get("outline") or []
            outline_topic = (
                outline_data.get("topic")
                or outline_data.get("title")
                or req.get("topic", "")
            )

            # ── RAG 上下文（章节级查询并发，结果合并去重，硬性长度上限）─────
            rag_context = ""
            if task.snapshot_rag_enabled:
                rag_context = await self._collect_rag_context(
                    db, session, chapters, task_id
                )

            # ── DeepSearch 上下文（topic + 章节标题构造查询，限制结果总长）──
            deepsearch_context = ""
            if task.snapshot_deep_search_enabled:
                deepsearch_context = await self._collect_deepsearch_context(
                    db, session, chapters, outline_topic, task_id
                )

            # ── 合并参考资料上下文 ─────────────────────────────────────────
            context_parts = []
            if rag_context:
                context_parts.append(f"**知识库参考资料（优先引用）：**\n{rag_context}")
            if deepsearch_context:
                context_parts.append(f"**网络搜索参考资料：**\n{deepsearch_context}")
            reference_context = "\n\n".join(context_parts) if context_parts else "（无外部参考资料）"

            kwargs: dict[str, str] = {
                "outline_json": json.dumps(outline_data, ensure_ascii=False),
                "reference_context": reference_context,
            }
            if session.session_type == SessionType.REPORT_DRIVEN:
                report = await report_repo.find_by_session(session.id)
                kwargs["report_text"] = (report.clean_text or "")[:8000] if report else ""
            else:
                kwargs.update({
                    "topic": req.get("topic", outline_topic),
                    "audience": req.get("audience", "通用受众"),
                    "style": req.get("style", "通用商务"),
                })

            prompt = PromptLoader.load(
                "slide_generate", session_type=session.session_type, **kwargs
            )

            await task_repo.update_status(task_id, TaskStatus.STREAMING)
            await self._publish_event(task_id, "progress", {"current": 0, "total": 1, "percentage": 0.0})

            full_text = await self._stream_and_collect(task_id, llm, prompt)

            try:
                slides_json = self._extract_json(full_text)
            except Exception as e:
                await self._mark_failed_and_notify(task_id, f"幻灯片 JSON 解析失败: {e}")
                return

            version = await slide_repo.get_next_version(session.id)
            slide = await slide_repo.create(session.id, version, slides_json)

            session.stage = SessionStage.CONTENT_CONFIRMING
            await session_repo.update(session)

            reply_text = "幻灯片内容已生成，请查看各页内容，告诉我是否满意或提出修改意见。"
            session.message_count += 1
            await session_repo.update(session)
            assistant_msg = await message_repo.create(
                session_id=session.id,
                role=MessageRole.ASSISTANT,
                seq_no=session.message_count,
                content=reply_text,
                slide_json=slides_json,
            )

            total = len(slides_json.get("slides", []))
            await self._publish_event(
                task_id, "progress", {"current": total, "total": total, "percentage": 1.0}
            )
            await task_repo.update_status(
                task_id, TaskStatus.COMPLETED, result={"slide_id": slide.id}
            )
            await db.commit()
            await self._publish_done(task_id, {
                "message_id": assistant_msg.id,
                "text": reply_text,
                "outline": None,
                "slides": slides_json,
            })
            logger.info(
                "Slides generated: session=%d version=%d slides=%d", session.id, version, total
            )

    async def _handle_slide_modification(self, task_id: int, extra: dict) -> None:
        """幻灯片修改：基于当前幻灯片 JSON 和修改要求，生成全量新版本。"""
        async with self._get_db_session() as db:
            from app.modules.session.repository.session_repository import (
                MessageRepository,
                ReportRepository,
                SessionRepository,
                SlideRepository,
            )
            from app.modules.task.repository.task_repository import TaskRepository

            task_repo = TaskRepository(db)
            await task_repo.update_status(task_id, TaskStatus.RUNNING)
            task = await task_repo.find_by_id(task_id)
            if task is None:
                return

            session_repo = SessionRepository(db)
            message_repo = MessageRepository(db)
            slide_repo = SlideRepository(db)
            report_repo = ReportRepository(db)
            session = await session_repo.find_by_id(task.session_id)
            if session is None:
                return

            llm = await self._build_llm_client(task, session, db)
            if llm is None:
                await self._mark_failed_and_notify(task_id, "LLM 未配置或已停用，请添加有效的 LLM 配置")
                return

            current_slide = await slide_repo.find_latest_by_session(session.id)
            if current_slide is None:
                await self._mark_failed_and_notify(task_id, "未找到当前幻灯片")
                return

            modification_request = extra.get("modification_request", "")
            # Fallback: if extra was lost (e.g. task recovered from DB), read from trigger message
            if not modification_request and task.trigger_message_id:
                trigger_msg = await message_repo.find_by_id(task.trigger_message_id)
                if trigger_msg and trigger_msg.content:
                    modification_request = trigger_msg.content
            kwargs: dict[str, str] = {
                "current_slides": json.dumps(current_slide.content, ensure_ascii=False),
                "modification_request": modification_request,
            }
            if session.session_type == SessionType.REPORT_DRIVEN:
                report = await report_repo.find_by_session(session.id)
                kwargs["report_text"] = (report.clean_text or "")[:6000] if report else ""

            prompt = PromptLoader.load(
                "slide_modify", session_type=session.session_type, **kwargs
            )

            await task_repo.update_status(task_id, TaskStatus.STREAMING)
            full_text = await self._stream_and_collect(task_id, llm, prompt)

            try:
                slides_json = self._extract_json(full_text)
            except Exception as e:
                await self._mark_failed_and_notify(task_id, f"幻灯片 JSON 解析失败: {e}")
                return

            version = await slide_repo.get_next_version(session.id)
            slide = await slide_repo.create(session.id, version, slides_json)

            reply_text = "幻灯片已按您的要求更新，请确认修改后的版本是否满意。"
            session.message_count += 1
            await session_repo.update(session)
            assistant_msg = await message_repo.create(
                session_id=session.id,
                role=MessageRole.ASSISTANT,
                seq_no=session.message_count,
                content=reply_text,
                slide_json=slides_json,
            )

            await task_repo.update_status(
                task_id, TaskStatus.COMPLETED, result={"slide_id": slide.id}
            )
            await db.commit()
            await self._publish_done(task_id, {
                "message_id": assistant_msg.id,
                "text": reply_text,
                "outline": None,
                "slides": slides_json,
            })

    async def _handle_intent_judgment(self, task_id: int) -> None:
        """
        意图判断（异步）：
        - 把原本同步阻塞在 HTTP 请求里的 LLM 意图判断挪到 worker，
          让 POST /messages 在 < 200ms 内立刻返回 task_id，前端通过 SSE 拿进度
        - 根据 session.stage 选择 outline_judge / slide_judge prompt
        - CONFIRM/MODIFY 时通过 next_task_id 链接到 SLIDE_BATCH / *_MODIFICATION 任务
        """
        async with self._get_db_session() as db:
            from app.modules.session.repository.session_repository import (
                MessageRepository,
                OutlineRepository,
                SessionRepository,
                SlideRepository,
            )
            from app.modules.task.repository.task_repository import TaskRepository

            task_repo = TaskRepository(db)
            await task_repo.update_status(task_id, TaskStatus.RUNNING)
            task = await task_repo.find_by_id(task_id)
            if task is None:
                return

            session_repo = SessionRepository(db)
            message_repo = MessageRepository(db)
            outline_repo = OutlineRepository(db)
            slide_repo = SlideRepository(db)

            session = await session_repo.find_by_id(task.session_id)
            if session is None:
                return

            if session.stage == SessionStage.OUTLINE_CONFIRMING:
                judge_kind = "outline"
            elif session.stage == SessionStage.CONTENT_CONFIRMING:
                judge_kind = "slide"
            else:
                await self._mark_failed_and_notify(
                    task_id, f"会话状态 {session.stage.value} 不支持意图判断"
                )
                return

            if not task.trigger_message_id:
                await self._mark_failed_and_notify(task_id, "缺少触发消息，无法判断意图")
                return
            trigger_msg = await message_repo.find_by_id(task.trigger_message_id)
            if trigger_msg is None:
                await self._mark_failed_and_notify(task_id, "触发消息已不存在")
                return
            user_content = trigger_msg.content or ""

            llm = await self._build_llm_client(task, session, db)
            if llm is None:
                await self._mark_failed_and_notify(task_id, "LLM 未配置或已停用，请添加有效的 LLM 配置")
                return

            prompt_name = "outline_judge" if judge_kind == "outline" else "slide_judge"
            schema_name = "outline_judge_schema" if judge_kind == "outline" else "slide_judge_schema"
            try:
                schema = SchemaLoader.load(schema_name)
                prompt = PromptLoader.load(
                    prompt_name,
                    session_type=session.session_type,
                    user_message=user_content,
                )
                judgment = await llm.chat_with_schema(
                    [{"role": "user", "content": prompt}], schema, temperature=0.1
                )
            except Exception as e:
                await self._mark_failed_and_notify(task_id, f"LLM 调用失败: {e}")
                return

            intent = judgment.get("intent", "IRRELEVANT")
            modification_request = (
                judgment.get("modification_request") or user_content
            )
            logger.info("Session %d intent (%s): %s", session.id, judge_kind, intent)

            followup_task_type: TaskType | None = None
            followup_extra: dict | None = None
            reply_text: str

            if judge_kind == "outline":
                if intent == "CONFIRM":
                    session.stage = SessionStage.CONTENT_GENERATION
                    outline = await outline_repo.find_latest_by_session(session.id)
                    if outline:
                        await outline_repo.confirm(outline.id)
                    followup_task_type = TaskType.SLIDE_BATCH
                    reply_text = "大纲已确认，正在生成幻灯片内容，请稍候…"
                elif intent == "MODIFY":
                    followup_task_type = TaskType.OUTLINE_MODIFICATION
                    followup_extra = {"modification_request": modification_request}
                    reply_text = "好的，正在按您的要求修改大纲…"
                else:
                    reply_text = "请针对当前大纲提出您的修改意见，或确认大纲以继续生成幻灯片内容。"
            else:
                if intent == "CONFIRM":
                    session.stage = SessionStage.COMPLETED
                    slide = await slide_repo.find_latest_by_session(session.id)
                    if slide:
                        await slide_repo.confirm(slide.id)
                    reply_text = "恭喜！您的 PPT 已全部完成，可以导出了。"
                elif intent == "MODIFY":
                    followup_task_type = TaskType.SLIDE_MODIFICATION
                    followup_extra = {"modification_request": modification_request}
                    reply_text = "好的，正在按您的要求修改幻灯片…"
                else:
                    reply_text = "请针对当前幻灯片提出您的修改意见，或确认内容以完成 PPT 创作。"

            await session_repo.update(session)

            await self._stream_text(task_id, reply_text)

            session.message_count += 1
            await session_repo.update(session)
            assistant_msg = await message_repo.create(
                session_id=session.id,
                role=MessageRole.ASSISTANT,
                seq_no=session.message_count,
                content=reply_text,
            )
            await db.commit()

            next_task_id: int | None = None
            if followup_task_type is not None:
                new_task = await task_repo.create(
                    session_id=session.id,
                    task_type=followup_task_type,
                    trigger_message_id=task.trigger_message_id,
                    snapshot_llm_config_id=session.current_user_llm_config_id,
                    snapshot_rag_enabled=session.rag_enabled,
                    snapshot_deep_search_enabled=session.deep_search_enabled,
                )
                next_task_id = new_task.id
                from app.infrastructure.redis.redis import redis_client
                payload: dict = {
                    "task_id": str(new_task.id),
                    "session_id": str(session.id),
                    "task_type": followup_task_type.value,
                    "trigger_message_id": str(task.trigger_message_id),
                }
                if followup_extra:
                    payload["extra"] = json.dumps(followup_extra, ensure_ascii=False)
                await redis_client.xadd(TASK_STREAM_KEY, payload, maxlen=TASK_STREAM_MAXLEN)
                await db.commit()
                logger.info(
                    "Intent=%s, enqueued followup task %d type=%s",
                    intent, new_task.id, followup_task_type.value,
                )

            await self._publish_done(task_id, {
                "message_id": assistant_msg.id,
                "text": reply_text,
                "outline": None,
                "slides": None,
                "intent": intent,
                "next_task_id": next_task_id,
            })
            await task_repo.update_status(
                task_id, TaskStatus.COMPLETED, result={"intent": intent}
            )
            await db.commit()

    # ──────────────────────────────────────────────
    # 工具方法
    # ──────────────────────────────────────────────

    async def _is_terminal_task(self, task_id: int) -> bool:
        """Return True if the task is already completed or cancelled (skip re-processing)."""
        try:
            async with self._get_db_session() as db:
                from app.modules.task.repository.task_repository import TaskRepository
                task = await TaskRepository(db).find_by_id(task_id)
                if task is None:
                    return True
                return task.status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED)
        except Exception:
            return False

    async def _stream_and_collect(self, task_id: int, llm, prompt: str) -> str:
        """流式调用 LLM，实时发布 token 事件，返回完整输出文本。

        诊断特性：
          - 进入循环前打印 prompt 字符数，便于关联超长输入与卡顿
          - 每 200 个 token / 5 秒打一次进度日志，避免长生成期间日志静默
          - 无活动看门狗（IDLE_ABORT_SECONDS）：若超过该秒数无 token 到达，
            主动抛 TimeoutError，让用户立刻拿到失败而不是等 worker 硬超时
        """
        import time
        IDLE_ABORT_SECONDS = 90.0
        LOG_EVERY_N_TOKENS = 200
        LOG_EVERY_N_SECONDS = 5.0

        logger.info(
            "LLM stream start: task=%d prompt_chars=%d",
            task_id, len(prompt),
        )
        messages = [{"role": "user", "content": prompt}]
        full_text = ""
        token_count = 0
        last_token_at = time.monotonic()
        last_log_at = last_token_at
        last_log_count = 0
        stream_started = last_token_at

        stream_iter = llm.chat_stream(messages, temperature=0.3).__aiter__()
        while True:
            try:
                token = await asyncio.wait_for(
                    stream_iter.__anext__(), timeout=IDLE_ABORT_SECONDS
                )
            except StopAsyncIteration:
                break
            except asyncio.TimeoutError as e:
                idle = time.monotonic() - last_token_at
                logger.error(
                    "LLM stream idle abort: task=%d idle=%.1fs tokens_so_far=%d "
                    "elapsed=%.1fs — provider sent no data within idle threshold",
                    task_id, idle, token_count, time.monotonic() - stream_started,
                )
                raise TimeoutError(
                    f"LLM 流式响应空闲超过 {IDLE_ABORT_SECONDS:.0f} 秒未返回数据；"
                    "可能是模型/提供方暂时不可用或 prompt 触发了限流，请稍后重试。"
                ) from e

            now = time.monotonic()
            full_text += token
            token_count += 1
            last_token_at = now
            await self._publish_event(task_id, "token", {"token": token})

            if (
                token_count - last_log_count >= LOG_EVERY_N_TOKENS
                or now - last_log_at >= LOG_EVERY_N_SECONDS
            ):
                logger.info(
                    "LLM stream progress: task=%d tokens=%d chars=%d elapsed=%.1fs",
                    task_id, token_count, len(full_text), now - stream_started,
                )
                last_log_at = now
                last_log_count = token_count

        logger.info(
            "LLM stream done: task=%d tokens=%d chars=%d elapsed=%.1fs",
            task_id, token_count, len(full_text), time.monotonic() - stream_started,
        )
        return full_text

    async def _stream_text(self, task_id: int, text: str) -> None:
        """
        将预生成文本以小块形式发布为 token 事件，模拟流式输出。
        中文按 6 字符一块、英文按词分块，兼顾视觉流畅与发布频率。
        """
        if not text:
            return
        # 简单分块：每 6 个字符一个 token，中文/英文统一处理
        CHUNK_SIZE = 6
        for i in range(0, len(text), CHUNK_SIZE):
            chunk = text[i : i + CHUNK_SIZE]
            await self._publish_event(task_id, "token", {"token": chunk})
            await asyncio.sleep(0.02)

    async def _publish_event(self, task_id: int, event_type: str, data: dict) -> None:
        from app.infrastructure.redis.redis import redis_client
        try:
            payload = json.dumps({"type": event_type, "data": data}, ensure_ascii=False)
            await redis_client.publish(f"task:{task_id}:events", payload)
        except Exception as e:
            logger.warning("Failed to publish event for task %d: %s", task_id, e)

    async def _publish_done(self, task_id: int, data: dict) -> None:
        await self._publish_event(task_id, "done", data)

    async def _mark_failed_and_notify(self, task_id: int, error: str) -> None:
        try:
            async with self._get_db_session() as db:
                from app.modules.task.repository.task_repository import TaskRepository
                repo = TaskRepository(db)
                await repo.update_status(task_id, TaskStatus.FAILED, error=error)
                await repo.increment_retry(task_id)
                await db.commit()
        except Exception as e:
            logger.error("Failed to mark task %d as failed: %s", task_id, e)
        await self._publish_event(task_id, "error", {"error": error})
        logger.error("Task %d failed: %s", task_id, error)

    @staticmethod
    def _extract_json(text: str) -> dict:
        """从 LLM 输出中提取 JSON，处理 Markdown 代码块包裹与回退解析。"""
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            end = -1 if lines[-1].strip() == "```" else len(lines)
            text = "\n".join(lines[1:end])
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # 回退：抓取首个 { ... } 平衡块
            start = text.find("{")
            if start == -1:
                raise
            depth = 0
            in_str = False
            esc = False
            for i in range(start, len(text)):
                ch = text[i]
                if in_str:
                    if esc:
                        esc = False
                    elif ch == "\\":
                        esc = True
                    elif ch == '"':
                        in_str = False
                else:
                    if ch == '"':
                        in_str = True
                    elif ch == "{":
                        depth += 1
                    elif ch == "}":
                        depth -= 1
                        if depth == 0:
                            return json.loads(text[start : i + 1])
            raise

    # ──────────────────────────────────────────────
    # RAG / DeepSearch 检索辅助
    # ──────────────────────────────────────────────

    async def _collect_rag_context(
        self, db, session, chapters: list[dict], task_id: int
    ) -> str:
        """
        按章节并发执行 RAG 检索，合并去重，限制总文本长度。
        返回拼接后的引用上下文字符串（带 [来源: ...] 前缀）。
        """
        try:
            from app.infrastructure.security.security import decrypt_api_key
            from app.infrastructure.vector.vector_service import RAGService
            from app.modules.knowledge_base.repository.knowledge_repository import (
                DocumentFileRepository,
            )
            from app.modules.model.repository.model_repository import (
                UserRagConfigRepository,
            )
            from app.modules.session.repository.session_repository import (
                KnowledgeRefRepository,
            )

            rag_cfg = await UserRagConfigRepository(db).find_by_user(session.user_id)
            knowledge_file_ids = await KnowledgeRefRepository(db).find_file_ids_by_session(
                session.id
            )
            if not rag_cfg or not knowledge_file_ids:
                logger.debug(
                    "RAG skipped: rag_cfg=%s file_count=%d",
                    bool(rag_cfg), len(knowledge_file_ids),
                )
                return ""

            rag_svc = RAGService(db, api_key=decrypt_api_key(rag_cfg.api_key))
            file_name_map = await DocumentFileRepository(db).find_names_by_ids(
                knowledge_file_ids
            )

            # 章节级（不再每张幻灯片都查）查询，避免过多 Embedding 调用
            queries: list[str] = []
            for chapter in chapters:
                chapter_title = chapter.get("title") or chapter.get("chapter_title", "")
                if not chapter_title.strip():
                    continue
                slide_titles = [
                    s.get("title", "") for s in chapter.get("slides", [])
                    if s.get("title")
                ]
                # 拼章节 + 各 slide title 作为查询语义增强
                query = chapter_title
                if slide_titles:
                    query += "：" + "、".join(slide_titles[:5])
                queries.append(query)

            if not queries:
                return ""

            # DashScope embedding 在 _embed_batch 内是同步阻塞，串行调用 retrieve 即可
            seen: set[str] = set()
            collected: list = []
            for q in queries:
                try:
                    results = await rag_svc.retrieve(
                        q,
                        knowledge_file_ids,
                        top_k=4,
                        score_threshold=0.6,
                        file_name_map=file_name_map,
                    )
                except Exception as e:
                    logger.warning("RAG retrieve failed for query '%s': %s", q[:60], e)
                    continue
                for r in results:
                    key = r.content[:120]
                    if key in seen:
                        continue
                    seen.add(key)
                    collected.append(r)

            if not collected:
                logger.info("RAG: no chunks above threshold for task_id=%d", task_id)
                return ""

            collected.sort(key=lambda r: r.score, reverse=True)
            collected = collected[:24]  # 最多保留 24 段，控制 prompt 长度

            from collections import Counter
            for fname, cnt in Counter(r.source for r in collected).items():
                logger.info(
                    "RAG: %d chunk(s) from '%s' (task_id=%d)", cnt, fname, task_id
                )
            logger.info(
                "RAG total %d unique chunks for task_id=%d", len(collected), task_id
            )

            return "\n\n".join(
                f"[来源: {r.source}]\n{r.content}" for r in collected
            )
        except Exception as e:
            logger.warning("RAG retrieval failed for task_id=%d: %s", task_id, e)
            return ""

    async def _collect_deepsearch_context(
        self, db, session, chapters: list[dict], outline_topic: str, task_id: int
    ) -> str:
        """
        基于 topic + 章节标题构造单条精炼查询；可扩展为多查询并发，
        但 Tavily 配额昂贵，先以单查询为默认。
        """
        try:
            from app.infrastructure.deepsearch.deepsearch_service import DeepSearchService
            from app.infrastructure.security.security import decrypt_api_key
            from app.modules.model.repository.model_repository import (
                UserSearchConfigRepository,
            )

            search_cfg = await UserSearchConfigRepository(db).find_by_user(session.user_id)
            if not search_cfg:
                logger.warning(
                    "DeepSearch enabled but no search config for user_id=%d",
                    session.user_id,
                )
                return ""

            api_key = decrypt_api_key(search_cfg.api_key)
            chapter_titles = [
                c.get("title") or c.get("chapter_title", "")
                for c in chapters[:5]
            ]
            chapter_titles = [t for t in chapter_titles if t]
            if outline_topic and chapter_titles:
                search_query = f"{outline_topic}：{'、'.join(chapter_titles)}"
            elif outline_topic:
                search_query = outline_topic
            elif chapter_titles:
                search_query = "、".join(chapter_titles)
            else:
                search_query = "PPT presentation"

            search_results = await DeepSearchService().search(
                search_query, api_key=api_key
            )
            if not search_results:
                logger.info("DeepSearch: empty results for task_id=%d", task_id)
                return ""

            search_results = search_results[:8]
            logger.info(
                "DeepSearch found %d results for task_id=%d",
                len(search_results), task_id,
            )
            return "\n\n".join(
                f"[来源: {r.source}]\n{r.content}" for r in search_results
            )
        except Exception as e:
            logger.warning("DeepSearch failed for task_id=%d: %s", task_id, e)
            return ""

    @staticmethod
    def _get_db_session():
        from app.infrastructure.database.postgre_sql import AsyncSessionLocal
        return AsyncSessionLocal()

    @staticmethod
    async def _build_llm_client(task, session, db):
        """
        从任务快照或会话配置构建 LLMClient。
        优先使用任务创建时的快照 LLM 配置 ID，确保任务执行使用创建时的配置。
        快照无效时降级到会话当前配置，再降级到用户默认活跃配置。
        配置缺失时返回 None（任务层处理错误）。
        """
        from app.common.ai.llm_client import LLMClient
        from app.common.exception.exception import BusinessException
        from app.infrastructure.security.security import decrypt_api_key
        from app.modules.model.repository.model_repository import (
            UserLLMConfigRepository,
            resolve_active_llm_config,
        )

        try:
            llm_config_id = task.snapshot_llm_config_id or session.current_user_llm_config_id
            if llm_config_id is not None:
                cfg = await UserLLMConfigRepository(db).find_by_id(llm_config_id)
                if cfg is not None:
                    return LLMClient(
                        api_key=decrypt_api_key(cfg.api_key),
                        base_url=cfg.base_url,
                        model=cfg.model_name,
                    )

            cfg = await resolve_active_llm_config(db, session.user_id)
            return LLMClient(
                api_key=decrypt_api_key(cfg.api_key),
                base_url=cfg.base_url,
                model=cfg.model_name,
            )
        except BusinessException:
            logger.warning(
                "No active LLM config for session %d user %d",
                session.id,
                session.user_id,
            )
            return None
        except Exception as e:
            logger.error("Failed to build LLM client: %s", e)
            return None
