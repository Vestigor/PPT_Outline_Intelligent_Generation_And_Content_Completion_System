from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column


def _camel_to_snake(name: str) -> str:
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BaseEntity(DeclarativeBase):
    """共享声明式基类，自动推断表名并为所有表添加审计时间戳。

    时间戳使用 Python 侧的 callable（default / onupdate）而非 server_default + onupdate=func.now()。
    原因：``onupdate=func.now()`` 是服务端表达式，UPDATE 后 SQLAlchemy 会将该列标记为 expired，
    再次访问时触发懒加载 SELECT。在异步会话中，从同步上下文（如 Pydantic ``model_validate``）
    访问该字段会抛出 ``MissingGreenlet``。改为 Python 侧 callable 后，列值在 flush 时直接写入
    内存对象，避免懒加载。``server_default`` 仍保留以兼容 Alembic 迁移和直接 SQL 操作。
    """

    @declared_attr.directive
    @classmethod
    def __tablename__(cls) -> str:
        return _camel_to_snake(cls.__name__)

    # 所有表自动拥有以下两列
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        server_default=func.now(),
        onupdate=_utcnow,
        nullable=False,
    )

    def to_dict(self) -> dict[str, Any]:
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}