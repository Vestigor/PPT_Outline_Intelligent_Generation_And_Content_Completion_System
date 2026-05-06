from __future__ import annotations

import logging
import sys

from app.config import settings

_initialized = False


def setup_logging() -> None:
    """配置根日志记录器。幂等：多次调用只生效一次。"""
    global _initialized
    if _initialized:
        return
    _initialized = True

    level = logging.DEBUG if settings.DEBUG else logging.INFO

    fmt = "[%(asctime)s] %(levelname)-8s %(name)s — %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt=fmt, datefmt=datefmt))

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(handler)

    # 压制高频第三方日志
    for noisy in ("sqlalchemy.engine", "httpcore", "httpx", "uvicorn.access",
                  "dashscope", "openai", "urllib3",
                  "pdfminer", "pdfplumber"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


# 模块导入时立即初始化，确保任何地方的 get_logger() 都能生效
setup_logging()


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)