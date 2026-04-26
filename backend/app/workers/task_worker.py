from __future__ import annotations

import asyncio

from app.common.model.entity.task import TaskType
from app.infrastructure.log.logging_config import get_logger

logger = get_logger(__name__)

# Redis Stream 键名与消费者组配置
TASK_STREAM_KEY = "tasks:pending"
CONSUMER_GROUP = "task_workers"
CONSUMER_NAME = "worker-1"
BATCH_SIZE = 5
BLOCK_MS = 5000


class TaskWorker:
    """
    异步任务执行 Worker。
    以 Redis Stream Consumer Group 模式消费 tasks:pending 流，
    按任务类型分发至对应处理器。

    支持的任务类型：
      - OUTLINE_GENERATION   大纲生成（调用 LLM，流式输出到 Redis Pub/Sub）
      - OUTLINE_MODIFICATION 大纲修改（同上）
      - SLIDE_BATCH          批量幻灯片生成（每页并行创建子协程，进度广播）

    SSE 推送机制：
      Worker 执行过程中通过 Redis Pub/Sub 频道 "task:{task_id}:events"
      发布 token / progress / done / error 事件，
      session_controller 和 task_controller 的 SSE 端点订阅对应频道并转发给前端。
    """

    def __init__(self) -> None:
        # TODO: 注入 RedisClient、TaskService、SessionService、LLMClient、RAGService、DeepSearchService
        self._redis = None
        self._task_svc = None
        self._session_svc = None
        self._llm_client = None
        self._rag_svc = None
        self._deepsearch_svc = None

    async def start(self) -> None:
        """启动 Worker 主循环，由 FastAPI lifespan 以 asyncio.create_task 调用。"""
        await self._ensure_consumer_group()
        logger.info("TaskWorker started, listening on stream: %s", TASK_STREAM_KEY)
        while True:
            try:
                await self._process_batch()
            except Exception as exc:
                logger.error("TaskWorker error: %s", exc, exc_info=True)
                await asyncio.sleep(3)

    async def _ensure_consumer_group(self) -> None:
        """确保 Stream 和 Consumer Group 存在（幂等）。"""
        # TODO: XGROUP CREATE tasks:pending task_workers $ MKSTREAM
        pass

    async def _process_batch(self) -> None:
        """拉取一批任务消息并逐条分发。"""
        # TODO: XREADGROUP GROUP task_workers worker-1 COUNT 5 BLOCK 5000 STREAMS tasks:pending >
        # TODO: 遍历消息，调用 _dispatch，异常时 mark_failed + XACK
        pass

    async def _dispatch(self, message_id: str, payload: dict) -> None:
        """
        根据 task_type 分发到对应处理器。
        payload 格式：{"task_id": "1", "session_id": "2", "task_type": "outline_generation"}
        """
        task_id = int(payload["task_id"])
        task_type = TaskType(payload["task_type"])

        if task_type == TaskType.OUTLINE_GENERATION:
            await self._handle_outline_generation(task_id)
        elif task_type == TaskType.OUTLINE_MODIFICATION:
            await self._handle_outline_modification(task_id)
        elif task_type == TaskType.SLIDE_BATCH:
            await self._handle_slide_batch(task_id)
        else:
            logger.warning("Unknown task type: %s", task_type)

    async def _handle_outline_generation(self, task_id: int) -> None:
        """
        大纲生成任务处理器。
        流程：
          1. mark_running
          2. 从 DB 加载 session + requirements
          3. 构造 outline_from_requirements.txt Prompt（或 outline_from_report.txt）
          4. LLMClient.chat_with_schema（JSON Schema 约束输出）
          5. 流式 token 发布到 Redis Pub/Sub 频道
          6. 解析大纲 JSON，写入 Outline 表，新建 Message（outline_json 回填）
          7. 更新 Session.stage → OUTLINE_CONFIRMING
          8. mark_completed，发布 done 事件
        """
        # TODO: 实现上述完整流程
        pass

    async def _handle_outline_modification(self, task_id: int) -> None:
        """
        大纲修改任务处理器。
        流程与 outline_generation 类似，但使用 outline_modification.txt Prompt，
        并基于当前最新大纲 JSON 进行增量修改。
        """
        # TODO: 加载当前大纲，调用修改 Prompt，更新 Outline 表（新版本）
        pass

    async def _handle_slide_batch(self, task_id: int) -> None:
        """
        批量幻灯片生成任务处理器。
        对大纲中的每一张幻灯片并行创建独立协程：
          1. 以页面主题 + 要点为锚点，并行调用 RAGService.retrieve + DeepSearchService.search
          2. 合并检索结果（RRF 重排序）
          3. 调用 slide_batch.txt Prompt 生成幻灯片内容 JSON
          4. 写入 Slide 表
          5. 更新进度并广播 progress 事件（已完成页数 / 总页数）
        完成后：
          6. 更新 Session.stage → CONTENT_CONFIRMING
          7. mark_completed，广播 done 事件
        """
        # TODO: 实现并行幻灯片生成，进度广播
        pass

    async def _publish_event(self, task_id: int, event_type: str, data: dict) -> None:
        """
        向 Redis Pub/Sub 频道 "task:{task_id}:events" 发布 SSE 事件。
        event_type: token | progress | done | error
        """
        # TODO: PUBLISH task:{task_id}:events json.dumps({"type": event_type, "data": data})
        pass

    @staticmethod
    def _rrf_merge(
        rag_results: list,
        search_results: list,
        k: int = 60,
    ) -> list:
        """
        倒数排名融合（Reciprocal Rank Fusion）合并 RAG 与 DeepSearch 检索结果。
        score = Σ 1/(k + rank_i)，k=60 为经验常数。
        """
        # TODO: 实现 RRF 融合算法，去重并按得分降序返回
        pass
