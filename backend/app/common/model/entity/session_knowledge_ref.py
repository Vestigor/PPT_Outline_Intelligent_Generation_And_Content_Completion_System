from __future__ import annotations

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.common.model.base_entity.base_entity import BaseEntity


class SessionKnowledgeRef(BaseEntity):
    """
    会话与知识库文件的引用关系（多对多中间表）。
    """
    __tablename__ = "session_knowledge_refs"
    __table_args__ = (
        UniqueConstraint("session_id", "knowledge_file_id", name="uq_session_knowledge_refs"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )

    knowledge_file_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_files.id", ondelete="CASCADE"), nullable=False, index=True
    )

    def __repr__(self) -> str:
        return f"<SessionKnowledgeRef session={self.session_id} file={self.knowledge_file_id}>"
