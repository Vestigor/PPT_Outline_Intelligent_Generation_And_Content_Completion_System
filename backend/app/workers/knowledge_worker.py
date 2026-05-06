from __future__ import annotations

import asyncio

from app.common.exception.code import StatusCode
from app.common.exception.exception import BusinessException
from app.common.model.entity.document import DocumentStatus
from app.infrastructure.database.postgre_sql import AsyncSessionLocal
from app.infrastructure.file.file_parser_service import DocumentParserService
from app.infrastructure.log.logging_config import get_logger
from app.infrastructure.redis.redis import redis_helper
from app.modules.knowledge_base.repository.knowledge_repository import DocumentFileRepository

logger = get_logger(__name__)

KNOWLEDGE_STREAM_KEY = "knowledge:processing"
CONSUMER_GROUP = "knowledge_workers"
CONSUMER_NAME = "worker-1"
BATCH_SIZE = 10
BLOCK_MS = 5000

_parser = DocumentParserService()


class KnowledgeWorker:
    """
    知识库文档处理 Worker。
    以 Redis Stream Consumer Group 模式消费 knowledge:processing 流。

    处理流程（每条消息对应一个文件）：
      1. XREADGROUP 拉取待处理消息
      2. 更新 DocumentFile.status = PROCESSING
      3. 从 OSS 下载原始文件字节（_download_from_oss，需配置后启用）
      4. DocumentParserService.parse 按格式提取纯文本
      5. DocumentParserService.split_into_chunks 语义分块
      6. RAGService.embed_and_store 批量 Embedding → 写入 document_chunks 表
      7. 更新 DocumentFile.status = READY
      8. XACK 确认消息，释放 PEL 槽位
      9. 异常时更新 status = FAILED，记录 error_message，XACK（防止无限重试）

    Redis Stream 消息格式：
      {"file_id": "123", "user_id": "456", "oss_key": "knowledge/...", "file_type": "application/pdf"}
    """

    def __init__(self) -> None:
        self._redis = redis_helper

    async def start(self) -> None:
        """启动 Worker 主循环，由 FastAPI lifespan 以 asyncio.create_task 调用。"""
        await self._ensure_consumer_group()
        logger.info("KnowledgeWorker started, listening on stream: %s", KNOWLEDGE_STREAM_KEY)
        while True:
            try:
                await self._process_batch()
            except Exception as exc:
                logger.error("KnowledgeWorker error: %s", exc, exc_info=True)
                await asyncio.sleep(3)

    async def _ensure_consumer_group(self) -> None:
        """确保 Stream 和 Consumer Group 存在（幂等）。"""
        await self._redis.xgroup_create(KNOWLEDGE_STREAM_KEY, CONSUMER_GROUP, id="$")

    async def _process_batch(self) -> None:
        """拉取一批消息，逐条处理，无论成功或失败均 XACK。"""
        messages = await self._redis.xreadgroup(
            stream=KNOWLEDGE_STREAM_KEY,
            group=CONSUMER_GROUP,
            consumer=CONSUMER_NAME,
            count=BATCH_SIZE,
            block=BLOCK_MS,
        )
        for msg_id, payload in messages:
            try:
                await self._process_one(msg_id, payload)
            except Exception as exc:
                logger.error("Failed to process message %s: %s", msg_id, exc, exc_info=True)
            finally:
                await self._redis.xack(KNOWLEDGE_STREAM_KEY, CONSUMER_GROUP, msg_id)

    async def _process_one(self, message_id: str, payload: dict) -> None:
        """
        处理单条文件消息。

        payload 格式：
          {"file_id": "123", "user_id": "456", "oss_key": "knowledge/...", "file_type": "application/pdf"}
        """
        from app.infrastructure.vector.vector_service import RAGService

        file_id = int(payload["file_id"])
        user_id = int(payload.get("user_id", 0))
        oss_key = payload["oss_key"]
        file_type = payload.get("file_type", "text/plain")

        async with AsyncSessionLocal() as db:
            doc_repo = DocumentFileRepository(db)

            # 解析用户 RAG API Key（用于 DashScope Embedding）
            rag_api_key: str | None = None
            if user_id:
                try:
                    from app.modules.model.repository.model_repository import UserRagConfigRepository
                    from app.infrastructure.security.security import decrypt_api_key
                    rag_cfg = await UserRagConfigRepository(db).find_by_user(user_id)
                    if rag_cfg:
                        rag_api_key = decrypt_api_key(rag_cfg.api_key)
                except Exception as e:
                    logger.warning("Failed to resolve RAG API key for user %d: %s", user_id, e)

            rag_svc = RAGService(db, api_key=rag_api_key)

            try:
                # 1. 标记为处理中
                await doc_repo.update_status(file_id, DocumentStatus.PROCESSING)
                await db.commit()

                doc = await doc_repo.find_by_id(file_id)
                file_name = doc.file_name if doc else f"file_id={file_id}"
                logger.info("Processing: %s (file_id=%d, user_id=%d)", file_name, file_id, user_id)

                # 2. 从 OSS 下载文件字节
                content: bytes = await self._download_from_oss(oss_key)

                # 3. 提取纯文本（parse 内部会抛 BusinessException，如不支持格式或内容为空）
                text = _parser.parse(content, file_type)

                # 4. 语义分块
                chunks = _parser.split_into_chunks(text)
                logger.info(
                    "Chunked: %s → %d chunks (text_len=%d)",
                    file_name, len(chunks), len(text),
                )

                # 5. 批量 Embedding → 写入 document_chunks 表（embed_document 内部幂等清理旧向量）
                await rag_svc.embed_document(file_id, chunks)

                # 7. 标记为完成
                await doc_repo.update_status(file_id, DocumentStatus.READY)
                await db.commit()
                logger.info("Done: %s vectorized → %d chunks stored", file_name, len(chunks))

            except Exception as exc:
                logger.error("Error processing file %d: %s", file_id, exc, exc_info=True)
                await doc_repo.update_status(file_id, DocumentStatus.FAILED, str(exc))
                await db.commit()
                raise

    @staticmethod
    async def _download_from_oss(oss_key: str) -> bytes:
        """从对象存储下载文件字节（通过 FileService）。"""
        from app.infrastructure.file.file_service import FileService
        try:
            data = await FileService().download(oss_key)
            return data
        except Exception as e:
            logger.error("OSS download failed for key=%s: %s", oss_key, e)
            raise BusinessException.exc(StatusCode.PARSE_FAILED.value)
