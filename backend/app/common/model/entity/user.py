from __future__ import annotations

import enum

from sqlalchemy import Boolean, String, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.model.base_entity.base_entity import BaseEntity


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    USER  = "user"


class User(BaseEntity):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)

    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=UserRole.USER,
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r} role={self.role.value!r}>"
