from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exception.code import StatusCode
from app.common.exception.exception import BusinessException
from app.common.model.entity.document_chunk import DocumentChunk
from app.common.result.result import RetrievalResult
from app.config import settings
from app.infrastructure.log.logging_config import get_logger

logger = get_logger(__name__)

# DashScope text-embedding-v4 单次请求最大条数（官方限制 10）
_DASHSCOPE_BATCH_SIZE = 10


class RAGService:
    """
    检索增强生成服务。
    调用关系：
      KnowledgeWorker._process_one → embed_document（构建知识库）
      TaskWorker._handle_slide_batch → retrieve（RAG 检索）
    """

    def __init__(self, db: AsyncSession, api_key: str | None = None) -> None:
        self._db = db
        self._api_key = api_key

    # ──────────────────────────────────────────────
    # 知识库构建
    # ──────────────────────────────────────────────

    async def embed_document(
        self,
        file_id: int,
        text_chunks: list[str],
    ) -> None:
        """
        对文档分块列表批量 Embedding，写入 document_chunks 表。
        先清理旧向量再写入，保证幂等。
        """
        if not text_chunks:
            logger.warning("embed_document: no chunks for file_id=%d", file_id)
            return

        logger.info("Embedding document: file_id=%d chunks=%d", file_id, len(text_chunks))

        # 清理旧向量（幂等重试时覆盖）
        await self.delete_document_vectors(file_id)

        embeddings = await self._embed_batch(text_chunks)
        total = len(text_chunks)

        for idx, (content, vector) in enumerate(zip(text_chunks, embeddings)):
            chunk = DocumentChunk(
                document_id=file_id,
                chunk_index=idx,
                total_chunk=total,
                content=content,
                embedding=vector,
                chunk_metadata={},
            )
            self._db.add(chunk)

        await self._db.flush()
        logger.info("Embedding done: file_id=%d total_chunks=%d", file_id, total)

    async def delete_document_vectors(self, file_id: int) -> None:
        """删除 document_chunks 表中指定文档的所有分块。"""
        result = await self._db.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == file_id)
        )
        deleted = result.rowcount
        if deleted:
            logger.info("Deleted %d chunks for document file_id=%d", deleted, file_id)
        await self._db.flush()

    # ──────────────────────────────────────────────
    # RAG 检索
    # ──────────────────────────────────────────────

    async def retrieve(
        self,
        query: str,
        session_knowledge_file_ids: list[int],
        top_k: int = settings.RAG_TOP_K,
        score_threshold: float = settings.RAG_SIMILARITY_THRESHOLD,
        file_name_map: dict[int, str] | None = None,
    ) -> list[RetrievalResult]:
        """
        按查询语句在指定文件集合中检索 Top-K 相关分块。
        pgvector 余弦距离：<=> 算子，相似度 = 1 - 距离。
        file_name_map 用于将 document_id 映射为可读文件名（显示在 source 字段）。
        """
        if not session_knowledge_file_ids:
            return []

        query_vec = await self._embed_text(query)

        distance_col = DocumentChunk.embedding.cosine_distance(query_vec).label("distance")
        stmt = (
            select(DocumentChunk, distance_col)
            .where(DocumentChunk.document_id.in_(session_knowledge_file_ids))
            .order_by(distance_col)
            .limit(top_k)
        )
        rows = (await self._db.execute(stmt)).all()

        results: list[RetrievalResult] = []
        for chunk, distance in rows:
            score = 1.0 - float(distance)
            if score >= score_threshold:
                source = (
                    file_name_map.get(chunk.document_id, f"文档#{chunk.document_id}")
                    if file_name_map else str(chunk.document_id)
                )
                results.append(
                    RetrievalResult(
                        source=source,
                        content=chunk.content,
                        score=score,
                        metadata=chunk.chunk_metadata or {},
                    )
                )

        return results

    async def rerank(
        self,
        results: list[RetrievalResult],
    ) -> list[RetrievalResult]:
        """按相似度降序重排序（当前使用简单分数排序，可替换为交叉编码器）。"""
        return sorted(results, key=lambda r: r.score, reverse=True)

    def generate_query_from_outline_node(
        self,
        chapter: str,
        slide_title: str,
        points: list[str],
    ) -> str:
        """将大纲节点拼接为向量检索查询语句。"""
        points_str = "; ".join(points)
        return f"{chapter} · {slide_title}: {points_str}"

    # ──────────────────────────────────────────────
    # Embedding 工具
    # ──────────────────────────────────────────────

    async def _embed_text(self, text: str) -> list[float]:
        """单条文本 Embedding，调用 DashScope text-embedding-v4。"""
        results = await self._embed_batch([text])
        return results[0]

    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        批量文本 Embedding。DashScope 单次最多 10 条，超出自动分批。
        返回与输入顺序一一对应的向量列表。

        DashScope SDK 的 TextEmbedding.call() 是同步阻塞调用；直接 await
        会冻结整个 event loop，使得并发的 worker 任务、SSE 推送、HTTP 请求
        全部停摆，最终触发 PER_TASK_TIMEOUT_SECONDS 硬超时。这里通过
        asyncio.to_thread 把每次调用放到独立线程，并加一个稳健的总超时，
        防止 DashScope 单次响应过慢拖垮整条任务。
        """
        import asyncio

        from dashscope import TextEmbedding

        api_key = self._api_key or settings.DASHSCOPE_API_KEY
        if not api_key:
            logger.error("No DASHSCOPE API key available (user config or system config)")
            raise BusinessException.exc(StatusCode.RAG_API_KEY_INVALID.value)

        all_embeddings: list[list[float]] = []
        n_batches = (len(texts) + _DASHSCOPE_BATCH_SIZE - 1) // _DASHSCOPE_BATCH_SIZE
        # 单次 DashScope 调用最多等待 60s；超出视为故障
        SINGLE_CALL_TIMEOUT = 60.0

        for i in range(0, len(texts), _DASHSCOPE_BATCH_SIZE):
            batch_no = i // _DASHSCOPE_BATCH_SIZE + 1
            batch = texts[i: i + _DASHSCOPE_BATCH_SIZE]
            logger.info("Embedding batch %d/%d (%d texts)", batch_no, n_batches, len(batch))
            try:
                resp = await asyncio.wait_for(
                    asyncio.to_thread(
                        TextEmbedding.call,
                        model=settings.EMBEDDING_MODEL,
                        input=batch,
                        api_key=api_key,
                        dimension=settings.EMBEDDING_DIMENSION,
                    ),
                    timeout=SINGLE_CALL_TIMEOUT,
                )
            except asyncio.TimeoutError:
                logger.error(
                    "DashScope embedding timed out after %.0fs (batch %d/%d)",
                    SINGLE_CALL_TIMEOUT, batch_no, n_batches,
                )
                raise BusinessException.exc(StatusCode.RAG_EMBEDDING_FAILED.value)
            except Exception as e:
                logger.error("DashScope embedding call failed: %s", e)
                raise BusinessException.exc(StatusCode.RAG_EMBEDDING_FAILED.value)

            if resp.status_code != 200:
                logger.error(
                    "DashScope embedding error: status=%d message=%s",
                    resp.status_code, resp.message,
                )
                if resp.status_code == 401:
                    raise BusinessException.exc(StatusCode.RAG_API_KEY_INVALID.value)
                raise BusinessException.exc(StatusCode.RAG_EMBEDDING_FAILED.value)

            batch_vecs = [e["embedding"] for e in resp.output["embeddings"]]
            all_embeddings.extend(batch_vecs)

        return all_embeddings
