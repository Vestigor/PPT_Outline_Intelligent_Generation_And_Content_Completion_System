from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Result(BaseModel, Generic[T]):
    """统一 API 响应包装器。"""

    code: int = 0
    message: str = "success"
    data: T | None = None

    @classmethod
    def success(cls, data: T | None = None, *, code: int = 200, message: str = "success") -> "Result[T]":
        return cls(code=code, message=message, data=data)

    @classmethod
    def error(cls, code: int, message: str) -> "Result[None]":
        return cls(code=code, message=message, data=None)


class PageResult(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class RetrievalResult:
    """单条检索结果"""
    __slots__ = ("source", "content", "score", "metadata")

    def __init__(self, source: str, content: str, score: float, metadata: dict | None = None) -> None:
        self.source = source
        self.content = content
        self.score = score
        self.metadata = metadata or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "content": self.content,
            "score": self.score,
            "metadata": self.metadata,
        }
