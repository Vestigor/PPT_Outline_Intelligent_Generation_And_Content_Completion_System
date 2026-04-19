from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.common.model.entity.message import MessageRole

class StartSessionResponse(BaseModel):
    """
    POST /sessions/start 的响应体（原子创建会话 + 处理首条消息）。
    """
    session_id: int
    message_id: int
    seq_no: int = 0
    task_id: int | None = None
    reply: str | None = None
    streaming: bool = False