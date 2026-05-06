from __future__ import annotations

import string
from functools import lru_cache
from pathlib import Path

from app.common.model.entity.session import SessionType
from app.infrastructure.log.logging_config import get_logger

logger = get_logger(__name__)

# resources/prompts/ 相对于项目根
_PROMPTS_DIR = Path(__file__).parent.parent.parent.parent / "resources" / "prompts"


class PromptLoader:
    """
    从 resources/prompts/ 目录加载 Prompt 模板文件。

    目录结构：
      prompts/
        guided/          GUIDED 引导式会话的 Prompt
        report/          REPORT_DRIVEN 报告驱动式会话的 Prompt

    Prompt 文件内可使用 {variable} 占位符，由 load() 的 kwargs 填充。
    """

    _cache: dict[str, str] = {}

    @classmethod
    def load(
        cls,
        name: str,
        session_type: SessionType | None = None,
        **kwargs: str,
    ) -> str:
        """
        加载并渲染 Prompt 模板。

        Args:
            name:         文件名（不含 .txt 后缀），如 "outline_generate"
            session_type: 会话类型，决定加载 guided/ 或 report/ 子目录；
                          若为 None 则直接在 prompts/ 根目录查找
            **kwargs:     模板变量，用于 str.format_map 替换 {variable}

        Returns:
            渲染后的 Prompt 字符串

        Raises:
            FileNotFoundError: 文件不存在
        """
        key = cls._cache_key(name, session_type)
        if key not in cls._cache:
            cls._cache[key] = cls._read(name, session_type)

        template = cls._cache[key]
        if kwargs:
            try:
                return string.Formatter().vformat(template, (), kwargs)  # type: ignore[arg-type]
            except KeyError as e:
                logger.warning("Prompt template missing variable %s in %s", e, key)
                return template
        return template

    @classmethod
    def load_system(
        cls,
        name: str,
        session_type: SessionType | None = None,
        **kwargs: str,
    ) -> dict[str, str]:
        """便捷方法：返回 {"role": "system", "content": <prompt>}"""
        return {"role": "system", "content": cls.load(name, session_type, **kwargs)}

    @classmethod
    def invalidate_cache(cls) -> None:
        cls._cache.clear()

    # ──────────────────────────────────────────────
    # 私有
    # ──────────────────────────────────────────────

    @classmethod
    def _cache_key(cls, name: str, session_type: SessionType | None) -> str:
        prefix = session_type.value if session_type else "common"
        return f"{prefix}/{name}"

    @classmethod
    def _read(cls, name: str, session_type: SessionType | None) -> str:
        if session_type is not None:
            subdir = "guided" if session_type == SessionType.GUIDED else "report"
            path = _PROMPTS_DIR / subdir / f"{name}.txt"
            # 如果特定类型文件不存在，回退到公共目录
            if not path.exists():
                path = _PROMPTS_DIR / f"{name}.txt"
        else:
            path = _PROMPTS_DIR / f"{name}.txt"

        if not path.exists():
            raise FileNotFoundError(f"Prompt file not found: {path}")

        content = path.read_text(encoding="utf-8")
        logger.debug("Loaded prompt: %s (%d chars)", path, len(content))
        return content
