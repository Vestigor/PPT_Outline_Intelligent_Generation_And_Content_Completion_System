from __future__ import annotations

import asyncio
from typing import Any

from app.config import settings
from app.common.result.result import RetrievalResult
from app.infrastructure.log.logging_config import get_logger

logger = get_logger(__name__)


class RAGService:
    """
    检索增强生成服务。
    """

    def __init__(self) -> None:
        # 向量存储客户端 / 数据库
        pass

    