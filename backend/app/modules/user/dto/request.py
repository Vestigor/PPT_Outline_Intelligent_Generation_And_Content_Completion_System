from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

class UserRegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(..., min_length=6, max_length=128)

class UserLoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)

class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=6, max_length=128)

    @field_validator("new_password")
    @classmethod
    def passwords_must_differ(cls, v: str, info: any) -> str:
        if info.data.get("old_password") == v:
            raise ValueError("新密码不能与旧密码相同")
        return v
    
class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)

class AdminCreateUserRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(..., min_length=6, max_length=128)
    role: str = Field(..., min_length=1, max_length=32)

class AdminChangePasswordRequest(BaseModel):
    user_id: int
    new_password: str = Field(..., min_length=6, max_length=128)

class AdminDeleteUserRequest(BaseModel):
    user_id: int

class AdminGetUserPageRequest(BaseModel):
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1, le=100)
    username: str | None = Field(default=None)