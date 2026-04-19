from __future__ import annotations

import enum

from sqlalchemy import BigInteger, ForeignKey, String, Text, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.common.model.base_entity.base_entity import BaseEntity

class DocumentStatus(str, enum.Enum):
    """知识库文件的处理状态。"""
    PENDING = "pending"         # 等待处理
    PROCESSING = "processing"   # 提取文本后、切块、向量化
    READY = "ready"             # 处理完成，可用于 RAG 检索
    FAILED = "failed"           # 处理失败

class DocumentFile(BaseEntity):
    """
    用户知识库文件。

    知识库属于用户，与会话之间存在引用关系。
    删除知识库文件或会话时，只需删除引用关系，双方互不影响。
    """
    __tablename__ = "knowledge_files"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    category: Mapped[str] =  mapped_column(String(512), nullable=False)

    file_name: Mapped[str] = mapped_column(String(512), nullable=False)

    file_type: Mapped[str] = mapped_column(String(128), nullable=False)

    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # SHA-256 内容哈希
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # 对象存储
    oss_key: Mapped[str] = mapped_column(String(1024), nullable=False)

    # 处理状态
    status: Mapped[DocumentStatus] = mapped_column(
        SAEnum(DocumentStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=DocumentStatus.PENDING,
    )

    # 失败时的错误信息
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<DocumentFile id={self.id} status={self.status.value!r} file_name={self.file_name!r}>"
