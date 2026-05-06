from __future__ import annotations

from pydantic import BaseModel, Field


class SendMessageRequest(BaseModel):
    content: str = Field(..., description="消息内容", min_length=1, max_length=4000)


class ModifyOutlineRequest(BaseModel):
    """PUT /sessions/{id}/outline — 用户直接编辑大纲 JSON（保存为新版本，不触发 LLM）"""
    outline_json: dict = Field(..., description="修改后的完整大纲 JSON")


class ModifySlideRequest(BaseModel):
    """PUT /sessions/{id}/slides — 用户直接编辑幻灯片 JSON（全量修改，不触发 LLM）"""
    content: dict = Field(..., description="修改后的完整幻灯片内容 JSON")


class UpdateSessionSettingsRequest(BaseModel):
    """PATCH /sessions/{id}/settings — 更新会话模型/功能配置"""
    llm_config_id: int | None = Field(None, description="切换 LLM 配置 ID")
    rag_enabled: bool | None = Field(None, description="是否启用 RAG")
    deep_search_enabled: bool | None = Field(None, description="是否启用 DeepSearch")
