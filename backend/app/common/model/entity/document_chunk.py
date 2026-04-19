from __future__ import annotations

import enum

from sqlalchemy import Integer, JSON, ForeignKey, String, Text, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from pgvector.sqlalchemy import Vector

from app.common.model.base_entity.base_entity import BaseEntity

class DocumentChunk(BaseEntity):
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )

    total_chunk: Mapped[int] = mapped_column(Integer, nullable=False)

    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)

    content: Mapped[str] = mapped_column(Text, nullable=False)

    # 向量数据
    embedding: Mapped[list[float]] = mapped_column(Vector(), nullable=False)

    metadata: Mapped[dict] = mapped_column(JSON, default=dict)


    def __repr__(self) -> str:
        return f"<DocumentChunk id={self.id} document_id={self.document_id} total_chunk={self.total_chunk} chunk_index={self.chunk_index}>"