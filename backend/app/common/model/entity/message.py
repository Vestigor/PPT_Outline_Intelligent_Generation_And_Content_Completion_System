from __future__ import annotations

import enum

from sqlalchemy import ForeignKey, Integer, JSON, Text, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.common.model.base_entity.base_entity import BaseEntity

class MessageRole(str, enum.Enum):
    USER      = "user"
    ASSISTANT = "assistant"
    SYSTEM    = "system"

class Message(BaseEntity):
    """
    会话消息。
    """
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    session_id: Mapped[int] = mapped_column(
        ForeignKey("ppt_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )

    role: Mapped[MessageRole] = mapped_column(
        SAEnum(MessageRole, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )

    # 会话内唯一递增序号
    seq_no: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # 普通文本内容
    content: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 大纲 JSON（大纲生成/修改任务完成后回填）；非大纲消息为 None
    outline_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    def __repr__(self) -> str:
        return f"<Message id={self.id} role={self.role.value!r} seq_no={self.seq_no}>"