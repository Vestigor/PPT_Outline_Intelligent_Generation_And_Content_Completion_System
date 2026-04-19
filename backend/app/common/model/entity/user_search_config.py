from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.model.base_entity.base_entity import BaseEntity


class UserSearchConfig(BaseEntity):
    """
    用户配置的搜索服务（web 搜索 / 检索，可配置多个，其中恰好一个标记为默认）。

    - 用户从管理员已录入的 SearchProvider 中选择；
    - 填写自己的 API Key（加密存储）；
    - 可起别名方便识别（如"我的 Bing"）；
    - 对话时可显式指定使用哪个配置，不指定则使用 is_default=True 的那条。
    - web_search 和 retrieval 两种类型各自独立，is_default 在同类型中生效。
    """
    __tablename__ = "user_search_configs"

    __table_args__ = (
        # 同一用户不能重复配置同一搜索服务提供商
        UniqueConstraint("user_id", "provider_id", name="uq_user_search_config"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    provider_id: Mapped[int] = mapped_column(
        ForeignKey("search_providers.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # 用户的 API Key，加密存储
    api_key: Mapped[str] = mapped_column(String(512), nullable=False)

    # 用户自定义别名
    alias: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # 是否为该用户的默认配置
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    def __repr__(self) -> str:
        return (
            f"<UserSearchConfig id={self.id} user={self.user_id} "
            f"provider={self.provider_id} default={self.is_default}>"
        )
