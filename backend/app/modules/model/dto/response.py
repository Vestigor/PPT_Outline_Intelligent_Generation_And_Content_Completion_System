from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


# ══════════════════════════════════════════════
# 浏览可用提供商 / 搜索服务
# ══════════════════════════════════════════════

class UserLLMModelBrowseResponse(BaseModel):
    id: int
    model_name: str
    description: str | None
    created_at: datetime
    updated_at: datetime


class UserLLMProviderBrowseResponse(BaseModel):
    id: int
    name: str
    description: str | None
    models: list[UserLLMModelBrowseResponse]
    created_at: datetime
    updated_at: datetime


class UserSearchProviderBrowseResponse(BaseModel):
    id: int
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime


# ══════════════════════════════════════════════
# 用户端已配置项
# ══════════════════════════════════════════════

class UserLLMConfigResponse(BaseModel):
    id: int
    provider_model_id: int
    provider_name: str
    model_name: str
    alias: str | None
    is_default: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UserSearchConfigResponse(BaseModel):
    id: int
    provider_id: int
    provider_name: str
    alias: str | None
    is_default: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UserRagConfigResponse(BaseModel):
    id: int
    base_url: str
    model: str
    created_at: datetime
    updated_at: datetime


# ══════════════════════════════════════════════
# 管理员端，LLM 提供商 / 模型
# ══════════════════════════════════════════════

class AdminLLMModelResponse(BaseModel):
    id: int
    provider_id: int
    model_name: str
    description: str | None
    is_active: bool
    effective_is_active: bool
    created_at: datetime
    updated_at: datetime


class AdminLLMProviderWithModelsResponse(BaseModel):
    id: int
    name: str
    base_url: str
    description: str | None
    is_active: bool
    models: list[AdminLLMModelResponse]
    created_at: datetime
    updated_at: datetime


class AdminLLMProviderResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    name: str
    base_url: str
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ══════════════════════════════════════════════
# 管理员端，搜索服务提供商
# ══════════════════════════════════════════════

class AdminSearchProviderResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    name: str
    api_endpoint: str | None
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
