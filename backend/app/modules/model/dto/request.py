from __future__ import annotations

from pydantic import BaseModel, field_validator


# ──────────────────────────────────────────────
# 用户 LLM 配置
# ──────────────────────────────────────────────

class CreateUserLLMConfigRequest(BaseModel):
    provider_model_id: int
    api_key: str
    alias: str | None = None
    is_default: bool = False

    @field_validator("api_key")
    @classmethod
    def api_key_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("api_key 不能为空")
        return v


class UpdateUserLLMConfigRequest(BaseModel):
    api_key: str | None = None
    alias: str | None = None
    is_default: bool | None = None


# ──────────────────────────────────────────────
# 用户 RAG（Embedding）配置
# ──────────────────────────────────────────────

class CreateUserRagConfigRequest(BaseModel):
    api_key: str

    @field_validator("api_key")
    @classmethod
    def api_key_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("api_key 不能为空")
        return v


class UpdateUserRagConfigRequest(BaseModel):
    api_key: str

    @field_validator("api_key")
    @classmethod
    def api_key_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("api_key 不能为空")
        return v


# ──────────────────────────────────────────────
# 用户搜索配置（固定 Tavily，每用户一条）
# ──────────────────────────────────────────────

class CreateUserSearchConfigRequest(BaseModel):
    api_key: str

    @field_validator("api_key")
    @classmethod
    def api_key_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("api_key 不能为空")
        return v


class UpdateUserSearchConfigRequest(BaseModel):
    api_key: str

    @field_validator("api_key")
    @classmethod
    def api_key_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("api_key 不能为空")
        return v


# ──────────────────────────────────────────────
# 管理员 LLM 提供商
# ──────────────────────────────────────────────

class CreateLLMProviderRequest(BaseModel):
    name: str
    base_url: str
    description: str | None = None
    is_active: bool = True


class UpdateLLMProviderRequest(BaseModel):
    name: str | None = None
    base_url: str | None = None
    description: str | None = None
    is_active: bool | None = None


# ──────────────────────────────────────────────
# 管理员 LLM 模型
# ──────────────────────────────────────────────

class CreateLLMProviderModelRequest(BaseModel):
    model_name: str
    description: str | None = None
    is_active: bool = True


class UpdateLLMProviderModelRequest(BaseModel):
    model_name: str | None = None
    description: str | None = None
    is_active: bool | None = None
