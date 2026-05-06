from __future__ import annotations

import json
from pathlib import Path

from app.infrastructure.log.logging_config import get_logger

logger = get_logger(__name__)

_SCHEMAS_DIR = Path(__file__).parent.parent.parent.parent / "resources" / "schemas"


class SchemaLoader:
    """
    从 resources/schemas/ 目录加载 JSON Schema 文件。
    内置缓存，首次读取后不再 IO。
    """

    _cache: dict[str, dict] = {}

    @classmethod
    def load(cls, name: str) -> dict:
        """
        加载 Schema 文件。

        Args:
            name: 文件名（不含 .json 后缀），如 "outline_schema"

        Returns:
            解析后的 Python dict

        Raises:
            FileNotFoundError: 文件不存在
            json.JSONDecodeError: JSON 格式错误
        """
        if name not in cls._cache:
            path = _SCHEMAS_DIR / f"{name}.json"
            if not path.exists():
                raise FileNotFoundError(f"Schema file not found: {path}")
            data = json.loads(path.read_text(encoding="utf-8"))
            cls._cache[name] = data
            logger.debug("Loaded schema: %s", name)
        return cls._cache[name]

    @classmethod
    def invalidate_cache(cls) -> None:
        cls._cache.clear()
