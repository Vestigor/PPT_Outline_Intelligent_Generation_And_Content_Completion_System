from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile, status

from app.dependencies import (
    CurrentUser,
    SessionServiceDepend,
    OutlineRepoDepend,
    SlideRepoDepend,
    ReportRepoDepend,
)
from app.common.result.result import Result
from app.common.exception.code import StatusCode
from app.common.exception.exception import BusinessException

# from app.modules.session.dto.request import 
from app.modules.session.dto.response import (
    StartSessionResponse,
)

router = APIRouter(prefix="/sessions", tags=["会话管理"])


@router.post(
    "/start",
    response_model=Result[StartSessionResponse],
    summary="原子创建会话并处理第一条消息",
    description="建立会话，并且发送第一条消息，会话类型由是否携带报告文件自动确定",
)
async def start_session(
    current_user: CurrentUser,
    svc: SessionServiceDepend,
    current_user_llm_config_id: int,
    current_user_search_config_id: int,
    content: Annotated[str, Form(description="第一条消息内容")],
    title: Annotated[
        str, Form(description="会话标题（可选，留空则截取消息前 50 字）")
    ] = "",
    report_file: Annotated[
        UploadFile | None,
        File(description="报告文件"),
    ] = None,
    rag_enabled: Annotated[
        bool | None, Form(description="手动覆盖 RAG 开关")
    ] = None,
    deep_search_enabled: Annotated[
        bool | None, Form(description="手动覆盖 DeepSearch 开关")
    ] = None,

) -> Result[StartSessionResponse]:

    result = await svc.start_session(
        user_id=current_user.id,
        llm_config_id = current_user_llm_config_id,
        search_config_id = current_user_search_config_id,
        title=title,
        content=content,
        file = report_file,
        rag_enabled=rag_enabled,
        deep_search_enabled=deep_search_enabled,
    )
    return Result.success(result)
