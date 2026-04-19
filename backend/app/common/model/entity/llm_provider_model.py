from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.model.base_entity.base_entity import BaseEntity


class LLMProviderModel(BaseEntity):
    """
    LLM 提供商下的可用模型（管理员管理）。

    同一提供商下模型名唯一，不同提供商可有同名模型。
    """
    __tablename__ = "llm_provider_models"

    __table_args__ = (
        UniqueConstraint("provider_id", "model_name", name="uq_llm_provider_model"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    provider_id: Mapped[int] = mapped_column(
        ForeignKey("llm_providers.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # 模型标识符（如 "gpt-4o"、"qwen-max"）
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)

    # 可选描述
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 软禁用：管理员可停用某模型而不删除历史配置
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return (
            f"<LLMProviderModel id={self.id} provider={self.provider_id} "
            f"model={self.model_name!r} active={self.is_active}>"
        )
