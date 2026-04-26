from __future__ import annotations

from pydantic import BaseModel, Field


class SendMessageRequest(BaseModel):
    """POST /sessions/{session_id}/messages 的请求体"""
    content: str = Field(..., description="消息内容", min_length=1)


class ConfirmOutlineRequest(BaseModel):
    """POST /sessions/{session_id}/outline/confirm 的请求体"""
    outline_id: int = Field(..., description="要确认的大纲 ID")


class ModifyOutlineRequest(BaseModel):
    """PUT /sessions/{session_id}/outline 的请求体（用户直接编辑大纲 JSON）"""
    outline_json: dict = Field(..., description="修改后的完整大纲 JSON")


class ConfirmSlidesRequest(BaseModel):
    """POST /sessions/{session_id}/slides/confirm 的请求体"""
    slide_id: int = Field(..., description="要确认的幻灯片内容 ID")


class ModifySlideRequest(BaseModel):
    """PUT /sessions/{session_id}/slides/{slide_id} 的请求体（用户直接编辑幻灯片内容）"""
    content: dict = Field(..., description="修改后的幻灯片内容 JSON")
