from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.common.model.entity.message import MessageRole
from app.common.model.entity.session import SessionStage, SessionType


class StartSessionResponse(BaseModel):
    """POST /sessions/start 响应：原子创建会话 + 处理首条消息。"""
    session_id: int
    message_id: int
    seq_no: int = 0
    task_id: int | None = None
    reply: str | None = None
    streaming: bool = False


class SendMessageResponse(BaseModel):
    """POST /sessions/{id}/messages 响应。"""
    session_id: int
    message_id: int
    seq_no: int
    task_id: int | None = None
    reply: str | None = None
    streaming: bool = False


class MessageResponse(BaseModel):
    """单条消息，含可选结构化数据。"""
    id: int
    session_id: int
    role: MessageRole
    seq_no: int
    content: str | None
    outline_json: dict | None
    slide_json: dict | None
    created_at: datetime

    class Config:
        from_attributes = True


class OutlineResponse(BaseModel):
    """大纲版本。"""
    id: int
    session_id: int
    version: int
    outline_json: dict
    confirmed_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


class SlideResponse(BaseModel):
    """幻灯片内容版本。"""
    id: int
    session_id: int
    version: int
    content: dict
    confirmed_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


class SessionSummaryResponse(BaseModel):
    """会话列表摘要。"""
    id: int
    title: str
    session_type: SessionType
    stage: SessionStage
    requirements_complete: bool
    rag_enabled: bool
    deep_search_enabled: bool
    message_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SessionDetailResponse(BaseModel):
    """GET /sessions/{id} 详情。"""
    id: int
    user_id: int
    title: str
    session_type: SessionType
    stage: SessionStage
    requirements: dict
    requirements_complete: bool
    rag_enabled: bool
    deep_search_enabled: bool
    message_count: int
    current_user_llm_config_id: int | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SessionListResponse(BaseModel):
    """GET /sessions 分页响应。"""
    items: list[SessionSummaryResponse]
    total: int
    page: int
    page_size: int
