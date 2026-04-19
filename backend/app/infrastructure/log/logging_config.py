from __future__ import annotations

import logging
import sys
from typing import Any

from app.config import settings


def setup_logging() -> None:
    """配置根日志记录器，使用结构化格式。"""
    level = logging.DEBUG if settings.DEBUG else logging.INFO

    fmt = "[%(asctime)s] %(levelname)-8s %(name)s — %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt=fmt, datefmt=datefmt))

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(handler)

    # Suppress noisy third-party loggers
    for noisy in ("sqlalchemy.engine", "httpcore", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)