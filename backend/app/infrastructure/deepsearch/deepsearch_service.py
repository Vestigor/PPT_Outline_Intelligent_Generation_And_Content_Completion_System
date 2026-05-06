from __future__ import annotations

from app.common.exception.code import StatusCode
from app.common.exception.exception import BusinessException
from app.common.result.result import RetrievalResult
from app.config import settings
from app.infrastructure.decorator.decorators import retry
from app.infrastructure.log.logging_config import get_logger

logger = get_logger(__name__)


class DeepSearchService:
    """
    网络深度搜索服务（基于 Tavily Search API）。

    用于在幻灯片内容生成时补充实时网络信息，
    结果与 RAGService.retrieve() 共用 RetrievalResult 数据结构。
    api_key 由调用方从用户的 UserSearchConfig 中解密后传入。
    """

    @retry(max_attempts=2, delay=2.0)
    async def search(
        self,
        query: str,
        api_key: str,
        num_results: int | None = None,
    ) -> list[RetrievalResult]:
        """
        执行单轮网络搜索，自动超时重试。

        Args:
            query:       搜索查询语句
            api_key:     用户配置的 Tavily API Key（解密后明文）
            num_results: 返回结果数量，默认使用 settings.SEARCH_MAX_RESULTS

        Returns:
            按相关性降序排列的 RetrievalResult 列表
        """
        if not api_key:
            raise BusinessException.exc(StatusCode.SEARCH_API_KEY_INVALID.value)

        max_results = num_results or settings.SEARCH_MAX_RESULTS
        logger.info("DeepSearch: query=%r max_results=%d", query[:80], max_results)

        try:
            from tavily import TavilyClient
            client = TavilyClient(api_key=api_key)

            # tavily-python 暂无原生 async 支持，在线程池中调用
            import asyncio
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: client.search(
                    query=query,
                    max_results=max_results,
                    search_depth="advanced",
                    include_answer=False,
                ),
            )
        except BusinessException:
            raise
        except Exception as e:
            logger.error("DeepSearch failed: query=%r error=%s", query[:80], e)
            raise BusinessException.exc(StatusCode.WEB_SEARCH_FAILED.value)

        results: list[RetrievalResult] = []
        for item in response.get("results", []):
            content = item.get("content", "").strip()
            url = item.get("url", "")
            score = float(item.get("score", 0.0))
            if content:
                results.append(
                    RetrievalResult(
                        source=url,
                        content=content,
                        score=score,
                        metadata={"title": item.get("title", ""), "url": url},
                    )
                )

        logger.info("DeepSearch done: query=%r results=%d", query[:80], len(results))
        return results
