from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.common.model.base_entity.base_entity import BaseEntity


class SessionReport(BaseEntity):
    """会话关联的报告文件，存储上传文件的元信息及清洗后文本。"""

    __tablename__ = "session_reports"

    __table_args__ = (
        UniqueConstraint("session_id", name="uq_session_reports_session_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )

    file_name: Mapped[str] = mapped_column(String(512), nullable=False)
    file_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # 对象存储路径
    oss_key: Mapped[str] = mapped_column(String(1024), nullable=False)

    # 清洗后纯文本（忽略图片等不可处理内容）
    clean_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 基于清洗后文本的 SHA-256 指纹（用于去重检测）
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    def __repr__(self) -> str:
        return f"<SessionReport id={self.id} session_id={self.session_id} file={self.file_name!r}>"
