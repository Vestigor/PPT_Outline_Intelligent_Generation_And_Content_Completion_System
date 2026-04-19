from __future__ import annotations

from datetime import datetime
import enum

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Text, Enum as SAEnum, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.model.base_entity.base_entity import BaseEntity


class TaskType(str, enum.Enum):
    OUTLINE_GENERATION = "outline_generation"      # 大纲生成 / 修改
    SLIDE_BATCH = "slide_batch"                    # 批量幻灯片内容生成
    OUTLINE_MODIFICATION = "outline_modification"  # 大纲修改


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    STREAMING = "streaming"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Task(BaseEntity):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("ppt_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[TaskType] = mapped_column(
        SAEnum(TaskType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    status: Mapped[TaskStatus] = mapped_column(
        SAEnum(TaskStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=TaskStatus.PENDING,
    )
    # 最终结果
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # 失败时的错误信息
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 重试计数
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    def __repr__(self) -> str:
        return f"<Task id={self.id} type={self.type.value!r} status={self.status.value!r}>"