from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.common.model.base_entity.base_entity import BaseEntity

_TAVILY_PROVIDER = "tavily"


class UserSearchConfig(BaseEntity):
    """
    用户的 DeepSearch 配置。
    """
    __tablename__ = "user_search_configs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # 每个用户只有一条搜索配置
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Tavily API Key，加密存储
    api_key: Mapped[str] = mapped_column(String(512), nullable=False)

    @property
    def provider(self) -> str:
        return _TAVILY_PROVIDER

    def __repr__(self) -> str:
        return f"<UserSearchConfig id={self.id} user={self.user_id}>"
