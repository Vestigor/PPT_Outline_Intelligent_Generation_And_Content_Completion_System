"""
面向切面编程（AOP）风格的横切关注点装饰器。
"""
from __future__ import annotations

import functools
import time
from typing import Any, Callable, Iterable

from app.infrastructure.log.logging_config import get_logger

logger = get_logger(__name__)


# 日志装饰器
def log_execution(func: Callable) -> Callable:
    """记录异步函数的调用入口、退出及耗时。"""

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        fn_name = f"{func.__module__}.{func.__qualname__}"
        logger.debug("→ %s called", fn_name)
        t0 = time.perf_counter()
        try:
            result = await func(*args, **kwargs)
            elapsed = (time.perf_counter() - t0) * 1000
            logger.debug("← %s completed in %.1f ms", fn_name, elapsed)
            return result
        except Exception as exc:
            elapsed = (time.perf_counter() - t0) * 1000
            logger.error("✗ %s raised %s after %.1f ms: %s", fn_name, type(exc).__name__, elapsed, exc)
            raise

    return wrapper


# 重试装饰器
def retry(max_attempts: int = 3, delay: float = 1.0, exceptions: Iterable[type] = (Exception,)):
    """在指定异常发生时，自动重试异步函数。"""
    import asyncio

    exc_tuple = tuple(exceptions)

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: Exception | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exc_tuple as exc:
                    last_exc = exc
                    if attempt < max_attempts:
                        logger.warning(
                            "第 %d/%d 次重试 %s：%s",
                            attempt, max_attempts, func.__qualname__, exc,
                        )
                        await asyncio.sleep(delay * attempt)
            raise last_exc  # type: ignore[misc]

        return wrapper

    return decorator


# 阶段守卫装饰器
def require_stage(*allowed_stages: str) -> Callable:
    """
    限制 Service 方法仅在指定会话阶段下可调用。

    被装饰方法必须通过关键字参数接收 `session`，
    装饰器将检查其 `.stage` 属性是否在 *allowed_stages* 中。
    """
    from app.common.exception.code import Status, StatusCode
    from app.common.exception.exception import BusinessException

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            session = kwargs.get("session")
            if session is None and len(args) > 1:
                session = args[1]  # 常见模式：(self, session, ...)
            if session is not None and session.stage not in allowed_stages:
                raise BusinessException(
                    code = StatusCode.INVALID_STAGE_TRANSITION.value.code,
                    message =
                    f"操作 '{func.__name__}' 需要在阶段 {', '.join(allowed_stages)} 中执行，当前阶段为 '{session.stage}'"
                )
            return await func(*args, **kwargs)

        return wrapper

    return decorator