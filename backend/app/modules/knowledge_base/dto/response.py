from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.common.model.entity.document import DocumentStatus


class DocumentResponse(BaseModel):
    """知识库文件详情响应体。"""
    model_config = {"from_attributes": True}

    id: int
    category: str
    file_name: str
    file_type: str
    size_bytes: int
    status: DocumentStatus
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class DocumentUploadResponse(BaseModel):
    """知识库文件上传响应体。"""
    model_config = {"from_attributes": True}

    id: int
    category: str
    file_name: str
    file_type: str
    size_bytes: int
    status: DocumentStatus
    created_at: datetime
    updated_at: datetime


class SessionKnowledgeRefResponse(BaseModel):
    """会话知识库引用响应体（含文件详情）。"""

    id: int
    session_id: int
    knowledge_file_id: int
    knowledge_file: DocumentResponse
    created_at: datetime
