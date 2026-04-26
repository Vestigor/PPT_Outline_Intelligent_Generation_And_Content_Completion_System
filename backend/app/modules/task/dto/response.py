from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.common.model.entity.task import TaskStatus, TaskType


class TaskResponse(BaseModel):
    """单个任务状态响应体。"""
    id: int
    session_id: int
    type: TaskType
    status: TaskStatus
    result: dict | None
    error: str | None
    retry_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TaskStatusResponse(BaseModel):
    """轻量任务状态查询响应（轮询用）。"""
    id: int
    status: TaskStatus
    progress: float | None = None  # 0.0 ~ 1.0，仅 SLIDE_BATCH 任务填充
    error: str | None = None

    class Config:
        from_attributes = True
