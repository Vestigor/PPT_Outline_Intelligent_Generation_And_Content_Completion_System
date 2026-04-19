from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.model.base_entity.base_entity import BaseEntity


class UserLLMConfig(BaseEntity):
    """
    用户配置的 LLM（可配置多个，其中恰好一个标记为默认）。

    - 用户从管理员已录入的 LLMProviderModel 中选择一个模型；
    - 填写自己的 API Key（加密存储）；
    - 可起别名方便识别（如"我的 GPT-4o"）；
    - 对话时可显式指定使用哪个配置，不指定则使用 is_default=True 的那条。
    """
    __tablename__ = "user_llm_configs"

    __table_args__ = (
        # 同一用户不能重复配置同一模型
        UniqueConstraint("user_id", "provider_model_id", name="uq_user_llm_config"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    provider_model_id: Mapped[int] = mapped_column(
        ForeignKey("llm_provider_models.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # 用户的 API Key，加密存储
    api_key: Mapped[str] = mapped_column(String(512), nullable=False)

    # 用户自定义别名，不填则展示模型名
    alias: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # 是否为该用户的默认 LLM 配置
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    def __repr__(self) -> str:
        return (
            f"<UserLLMConfig id={self.id} user={self.user_id} "
            f"model={self.provider_model_id} default={self.is_default}>"
        )
