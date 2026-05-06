from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.common.model.base_entity.base_entity import BaseEntity


class UserLLMConfig(BaseEntity):
    """
    用户配置的 LLM（可配置多个，其中恰好一个标记为默认）。

    provider_name / model_name / base_url 在创建时从提供商快照写入，
    避免每次使用时都 JOIN 两张表。is_active 状态仍需实时 JOIN 判断。
    采用懒更新策略：管理员禁用模型/提供商时，仅清零受影响配置的 is_default；
    下次用户实际使用时，再惰性晋升最新有效配置为默认。
    """
    __tablename__ = "user_llm_configs"

    __table_args__ = (
        UniqueConstraint("user_id", "provider_model_id", name="uq_user_llm_config"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    provider_model_id: Mapped[int] = mapped_column(
        ForeignKey("llm_provider_models.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # 快照字段（创建时一次性写入，供调用时直接使用，无需再 JOIN）
    provider_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    model_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    base_url: Mapped[str] = mapped_column(String(512), nullable=False, default="")

    # 用户的 API Key，加密存储
    api_key: Mapped[str] = mapped_column(String(512), nullable=False)

    # 用户自定义别名
    alias: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # 是否为该用户的默认配置（懒更新）
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    def __repr__(self) -> str:
        return (
            f"<UserLLMConfig id={self.id} user={self.user_id} "
            f"model={self.model_name!r} default={self.is_default}>"
        )
