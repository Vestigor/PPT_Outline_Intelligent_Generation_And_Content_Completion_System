from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.common.model.base_entity.base_entity import BaseEntity


class Outline(BaseEntity):
    __tablename__ = "outlines"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # 每个会话内单调递增的版本号（1, 2, 3, …）
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # 完整的四级大纲存储为 JSON
    outline_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # 在用户明确确认之前为 null
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    def __repr__(self) -> str:
        return f"<Outline id={self.id} session_id={self.session_id} version={self.version}>"