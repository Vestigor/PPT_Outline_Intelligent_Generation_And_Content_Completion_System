from __future__ import annotations

from typing import List

from pydantic import BaseModel


class AddKnowledgeRefsRequest(BaseModel):
    """批量为会话添加知识库引用请求体。"""
    knowledge_file_ids: List[int]


class RenameCategoryRequest(BaseModel):
    """重命名知识库分类请求体。"""
    new_name: str


class UpdateFileCategoryRequest(BaseModel):
    """修改单个文件分类请求体。"""
    category: str
