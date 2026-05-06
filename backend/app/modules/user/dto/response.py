from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class TokenResponse(BaseModel):
    username: str
    access_token: str
    refresh_token: str


class UserResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    username: str
    email: str | None
    is_email_verified: bool
    role: str
    is_active: bool
    created_at: datetime
