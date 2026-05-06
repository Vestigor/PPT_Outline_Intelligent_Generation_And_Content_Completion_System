from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.common.model.base_entity.base_entity import BaseEntity

# 固定常量：阿里云 DashScope text-embedding-v4
_ALIBABA_RAG_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
_ALIBABA_RAG_MODEL: str    = "text-embedding-v4"


class UserRagConfig(BaseEntity):
    """
    用户的 RAG Embedding 配置。

    Embedding 提供商和模型固定为阿里云 DashScope text-embedding-v4，
    """
    __tablename__ = "user_rag_configs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # 每个用户只有一条 RAG 配置
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # 阿里云 DashScope API Key（加密存储）
    api_key: Mapped[str] = mapped_column(String(512), nullable=False)

    # --- 只读属性：固定参数，不持久化到数据库 ---

    @property
    def base_url(self) -> str:
        """DashScope OpenAI 兼容接口地址。"""
        return _ALIBABA_RAG_BASE_URL

    @property
    def model(self) -> str:
        """固定使用 text-embedding-v4。"""
        return _ALIBABA_RAG_MODEL

    def __repr__(self) -> str:
        return f"<UserRagConfig id={self.id} user={self.user_id}>"
