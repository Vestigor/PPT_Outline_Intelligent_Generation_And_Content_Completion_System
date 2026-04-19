from __future__ import annotations

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.model.base_entity.base_entity import BaseEntity


class LLMProvider(BaseEntity):
    """
    LLM 服务提供商（管理员管理）。

    管理员可添加/删除提供商；每个提供商下挂载若干可用模型。
    """
    __tablename__ = "llm_providers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # 提供商名称，全局唯一（如 "OpenAI"、"Qwen"）
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)

    # OpenAI 兼容接口的 base_url（如 https://api.openai.com/v1）
    base_url: Mapped[str] = mapped_column(String(512), nullable=False)

    # 可选描述
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 软禁用：False 时前端不展示，不影响历史配置
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return f"<LLMProvider id={self.id} name={self.name!r} active={self.is_active}>"
