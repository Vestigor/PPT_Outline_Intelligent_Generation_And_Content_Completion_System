from __future__ import annotations

import re

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.common.exception.code import StatusCode
from app.common.exception.exception import BusinessException


def _check_password_strength(v: str) -> str:
    if len(v) < 8 or len(v) > 16:
        raise BusinessException(StatusCode.PASSWORD_TOO_WEAK.value)
    if ' ' in v:
        raise BusinessException(StatusCode.PASSWORD_TOO_WEAK.value)
    if not re.search(r'[A-Z]', v):
        raise BusinessException(StatusCode.PASSWORD_TOO_WEAK.value)
    if not re.search(r'[a-z]', v):
        raise BusinessException(StatusCode.PASSWORD_TOO_WEAK.value)
    if not re.search(r'\d', v):
        raise BusinessException(StatusCode.PASSWORD_TOO_WEAK.value)
    return v


class SendEmailCodeRequest(BaseModel):
    email: EmailStr
    purpose: str = Field(..., pattern=r'^(register|reset_password|bind_email)$')


class UserRegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(..., min_length=8, max_length=16)
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _check_password_strength(v)


class UserLoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)
    new_password: str = Field(..., min_length=8, max_length=16)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _check_password_strength(v)


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=16)

    @field_validator("new_password")
    @classmethod
    def passwords_must_differ(cls, v: str, info: object) -> str:
        _check_password_strength(v)
        if getattr(info, "data", {}).get("old_password") == v:
            raise BusinessException(StatusCode.SAME_PASSWORD.value)
        return v


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)


class AdminCreateUserRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(..., min_length=8, max_length=16)
    role: str = Field(..., min_length=1, max_length=32)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _check_password_strength(v)


class AdminChangePasswordRequest(BaseModel):
    user_id: int
    new_password: str = Field(..., min_length=8, max_length=16)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _check_password_strength(v)


class UpdateEmailRequest(BaseModel):
    new_email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)
    password: str = Field(..., min_length=1)


class AdminSetEmailRequest(BaseModel):
    email: EmailStr | None = None


class AdminDeleteUserRequest(BaseModel):
    user_id: int


class AdminGetUserPageRequest(BaseModel):
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1, le=100)
    username: str | None = Field(default=None)
