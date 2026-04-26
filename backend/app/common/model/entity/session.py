from __future__ import annotations

import enum

from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.model.base_entity.base_entity import BaseEntity


class SessionStage(str, enum.Enum):
    """会话阶段枚举，代表 PPT 创作的生命周期状态，仅允许正向流转。"""
    REQUIREMENT_COLLECTION = "requirement_collection"   # 需求收集
    OUTLINE_GENERATION     = "outline_generation"       # 大纲生成中
    OUTLINE_CONFIRMING     = "outline_confirming"       # 等待用户确认/修改大纲
    CONTENT_GENERATION     = "content_generation"       # 内容生成中
    CONTENT_CONFIRMING     = "content_confirming"       # 等待用户确认内容
    COMPLETED              = "completed"                # 已完成


class SessionType(str, enum.Enum):
    """
    会话类型枚举，在发送第一条消息时确定，之后不可更改。
    """
    REPORT_DRIVEN = "report_driven"
    GUIDED        = "guided"


class Session(BaseEntity):
    """
    PPT 创作会话。
    """
    __tablename__ = "ppt_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    title: Mapped[str] = mapped_column(String(256), nullable=False, default="未命名 PPT")

    # 会话类型（第一条消息时确定，不可更改）
    session_type: Mapped[SessionType] = mapped_column(
        SAEnum(SessionType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=SessionType.GUIDED,
    )

    # 当前阶段（仅允许正向流转）
    stage: Mapped[SessionStage] = mapped_column(
        SAEnum(SessionStage, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=SessionStage.REQUIREMENT_COLLECTION,
    )

    # 结构化需求字段
    # 结构：{"topic": str|null, "audience": str|null, "duration_minutes": int|null,
    #        "style": str|null, "focus_points": list|null}
    requirements: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # 需求是否已完整（topic + audience 均非空即视为完整）
    requirements_complete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # 消息序号生成器，每次创建消息前递增，当前值即下一条消息的 seq_no
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    current_user_llm_config_id: Mapped[int | None] = mapped_column(
        ForeignKey("user_llm_configs.id", ondelete="SET NULL"), nullable=True, index=True
    )

    current_user_search_config_id: Mapped[int | None] = mapped_column(
        ForeignKey("user_search_configs.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # RAG 和 DeepSearch 开关
    rag_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    deep_search_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    @property
    def is_report_driven(self) -> bool:
        return self.session_type == SessionType.REPORT_DRIVEN

    def __repr__(self) -> str:
        return (
            f"<PPTSession id={self.id} type={self.session_type.value!r} "
            f"stage={self.stage.value!r}>"
        )