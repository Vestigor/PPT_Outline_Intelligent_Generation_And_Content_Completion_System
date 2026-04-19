from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column


def _camel_to_snake(name: str) -> str:
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


class BaseEntity(DeclarativeBase):
    """共享声明式基类，自动推断表名并为所有表添加审计时间戳。"""

    @declared_attr.directive
    @classmethod
    def __tablename__(cls) -> str:
        return _camel_to_snake(cls.__name__)

    # 所有表自动拥有以下两列
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def to_dict(self) -> dict[str, Any]:
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}