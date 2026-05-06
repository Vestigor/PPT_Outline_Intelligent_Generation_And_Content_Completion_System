from __future__ import annotations

from datetime import datetime
import enum

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Text, Enum as SAEnum, func
from sqlalchemy.orm import Mapped, mapped_column

from app.common.model.base_entity.base_entity import BaseEntity


class TaskType(str, enum.Enum):
    REQUIREMENT_COLLECTION = "requirement_collection"  # 需求收集阶段 LLM 对话
    OUTLINE_GENERATION     = "outline_generation"      # 大纲生成
    OUTLINE_MODIFICATION   = "outline_modification"    # 大纲修改
    SLIDE_BATCH            = "slide_batch"             # 批量幻灯片内容生成
    SLIDE_MODIFICATION     = "slide_modification"      # 幻灯片修改
    INTENT_JUDGMENT        = "intent_judgment"         # 大纲/内容确认阶段的意图判断（异步）


class TaskStatus(str, enum.Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    STREAMING = "streaming"
    COMPLETED = "completed"
    FAILED    = "failed"
    CANCELLED = "cancelled"


class Task(BaseEntity):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
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
    # 触发此任务的用户消息 ID（可选）
    trigger_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 最终结果
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # 失败时的错误信息
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 重试计数
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 任务创建时的配置快照（避免任务执行时会话设置已改变）
    snapshot_llm_config_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    snapshot_rag_enabled: Mapped[bool] = mapped_column(default=False, nullable=False, server_default="false")
    snapshot_deep_search_enabled: Mapped[bool] = mapped_column(default=False, nullable=False, server_default="false")

    def __repr__(self) -> str:
        return f"<Task id={self.id} type={self.type.value!r} status={self.status.value!r}>"
