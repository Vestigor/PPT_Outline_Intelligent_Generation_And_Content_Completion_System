from __future__ import annotations

import asyncio

from app.config import settings
from app.common.result.result import RetrievalResult
from app.infrastructure.decorator.decorators import retry
from app.infrastructure.log.logging_config import get_logger

logger = get_logger(__name__)

class DeepSearchService:
    """
    网络深度搜索服务。
    """
    def __init__(self) -> None:
        # TODO: 初始化搜索 API 客户端（Tavily / Serper 等）
        self._client = None

    @retry(max_attempts=2, delay=2.0)
    async def search(
        self,
        query: str,
        num_results: int | None = None,
    ) -> list[RetrievalResult]:
        """
        执行单轮网络搜索，自动超时重试。

        返回的结果与 RAGService 共用 RetrievalResult 数据结构，
        便于两者结果在 merge_results 中统一处理。
        """
        pass
   
