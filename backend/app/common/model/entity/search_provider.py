from __future__ import annotations

import enum

from sqlalchemy import Boolean, Enum as SAEnum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.common.model.base_entity.base_entity import BaseEntity


class SearchProvider(BaseEntity):
    """
    搜索服务提供商。

    """
    __tablename__ = "search_providers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # 提供商名称，全局唯一
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)

    # 服务接口地址（可选；部分 SDK 接入方式无需显式配置）
    api_endpoint: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # 可选描述
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 软禁用：False 时不对用户展示
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return (
            f"<SearchProvider id={self.id} name={self.name!r} "
            f"active={self.is_active}>"
        )
