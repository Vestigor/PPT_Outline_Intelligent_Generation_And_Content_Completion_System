from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Form, Query, UploadFile
from fastapi.responses import StreamingResponse

from app.dependencies import (
    CurrentUser,
    OutlineRepoDepend,
    ReportRepoDepend,
    SessionRepoDepend,
    SessionServiceDepend,
    SlideRepoDepend,
)
from app.common.result.result import Result
from app.common.exception.code import StatusCode
from app.common.exception.exception import BusinessException

from app.modules.session.dto.request import (
    ConfirmOutlineRequest,
    ConfirmSlidesRequest,
    ModifyOutlineRequest,
    ModifySlideRequest,
    SendMessageRequest,
)
from app.modules.session.dto.response import (
    MessageResponse,
    OutlineResponse,
    SendMessageResponse,
    SessionDetailResponse,
    SessionListResponse,
    SlideResponse,
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
        llm_config_id=current_user_llm_config_id,
        search_config_id=current_user_search_config_id,
        title=title,
        content=content,
        file=report_file,
        rag_enabled=rag_enabled,
        deep_search_enabled=deep_search_enabled,
    )
    return Result.success(result)


@router.get(
    "",
    response_model=Result[SessionListResponse],
    summary="获取当前用户的会话列表（分页）",
)
async def list_sessions(
    current_user: CurrentUser,
    session_repo: SessionRepoDepend,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
) -> Result[SessionListResponse]:
    # TODO: 实现分页查询逻辑
    pass


@router.get(
    "/{session_id}",
    response_model=Result[SessionDetailResponse],
    summary="获取会话详情",
)
async def get_session(
    session_id: int,
    current_user: CurrentUser,
    session_repo: SessionRepoDepend,
) -> Result[SessionDetailResponse]:
    # TODO: 验证 session 归属当前用户，返回详情
    pass


@router.delete(
    "/{session_id}",
    response_model=Result[None],
    summary="删除会话（及其所有消息、大纲、幻灯片）",
)
async def delete_session(
    session_id: int,
    current_user: CurrentUser,
    session_repo: SessionRepoDepend,
) -> Result[None]:
    # TODO: 验证归属，软删或硬删
    pass


# ──────────────────────────────────────────────
# 消息
# ──────────────────────────────────────────────

@router.post(
    "/{session_id}/messages",
    response_model=Result[SendMessageResponse],
    summary="在已有会话中发送一条消息",
)
async def send_message(
    session_id: int,
    body: SendMessageRequest,
    current_user: CurrentUser,
    svc: SessionServiceDepend,
    session_repo: SessionRepoDepend,
) -> Result[SendMessageResponse]:
    # TODO: 验证归属，调用 svc.handle_message
    pass


@router.get(
    "/{session_id}/messages",
    response_model=Result[list[MessageResponse]],
    summary="获取会话完整消息历史",
)
async def list_messages(
    session_id: int,
    current_user: CurrentUser,
    session_repo: SessionRepoDepend,
) -> Result[list[MessageResponse]]:
    # TODO: 验证归属，查询消息列表
    pass


# ──────────────────────────────────────────────
# 大纲
# ──────────────────────────────────────────────

@router.get(
    "/{session_id}/outline",
    response_model=Result[OutlineResponse],
    summary="获取当前最新大纲",
)
async def get_outline(
    session_id: int,
    current_user: CurrentUser,
    session_repo: SessionRepoDepend,
    outline_repo: OutlineRepoDepend,
) -> Result[OutlineResponse]:
    # TODO: 验证归属，返回最新版本大纲
    pass


@router.post(
    "/{session_id}/outline/confirm",
    response_model=Result[OutlineResponse],
    summary="用户确认大纲，触发幻灯片批量生成任务",
)
async def confirm_outline(
    session_id: int,
    body: ConfirmOutlineRequest,
    current_user: CurrentUser,
    svc: SessionServiceDepend,
    session_repo: SessionRepoDepend,
    outline_repo: OutlineRepoDepend,
) -> Result[OutlineResponse]:
    # TODO: 验证归属，调用 svc._handle_outline_generation 完成流转，创建 SLIDE_BATCH 任务
    pass


@router.put(
    "/{session_id}/outline",
    response_model=Result[OutlineResponse],
    summary="用户直接编辑大纲 JSON（不触发 LLM，保存为新版本）",
)
async def update_outline(
    session_id: int,
    body: ModifyOutlineRequest,
    current_user: CurrentUser,
    session_repo: SessionRepoDepend,
    outline_repo: OutlineRepoDepend,
) -> Result[OutlineResponse]:
    # TODO: 验证归属和阶段，保存新版本大纲
    pass


# ──────────────────────────────────────────────
# 幻灯片
# ──────────────────────────────────────────────

@router.get(
    "/{session_id}/slides",
    response_model=Result[SlideResponse],
    summary="获取当前最新幻灯片内容",
)
async def get_slides(
    session_id: int,
    current_user: CurrentUser,
    session_repo: SessionRepoDepend,
    slide_repo: SlideRepoDepend,
) -> Result[SlideResponse]:
    # TODO: 验证归属，返回最新版本幻灯片内容
    pass


@router.post(
    "/{session_id}/slides/confirm",
    response_model=Result[SlideResponse],
    summary="用户确认幻灯片内容，会话进入 COMPLETED 阶段",
)
async def confirm_slides(
    session_id: int,
    body: ConfirmSlidesRequest,
    current_user: CurrentUser,
    svc: SessionServiceDepend,
    session_repo: SessionRepoDepend,
    slide_repo: SlideRepoDepend,
) -> Result[SlideResponse]:
    # TODO: 验证归属，确认幻灯片，会话阶段流转至 COMPLETED
    pass


@router.put(
    "/{session_id}/slides/{slide_id}",
    response_model=Result[SlideResponse],
    summary="用户直接编辑幻灯片内容 JSON",
)
async def update_slide(
    session_id: int,
    slide_id: int,
    body: ModifySlideRequest,
    current_user: CurrentUser,
    session_repo: SessionRepoDepend,
    slide_repo: SlideRepoDepend,
) -> Result[SlideResponse]:
    # TODO: 验证归属和阶段，更新幻灯片内容
    pass


# ──────────────────────────────────────────────
# 导出
# ──────────────────────────────────────────────

@router.get(
    "/{session_id}/export",
    summary="导出 PPT 文件（返回二进制流）",
    response_class=StreamingResponse,
)
async def export_ppt(
    session_id: int,
    current_user: CurrentUser,
    session_repo: SessionRepoDepend,
    slide_repo: SlideRepoDepend,
) -> StreamingResponse:
    # TODO: 调用 ExportService 生成 .pptx 字节流，以附件形式返回
    pass


# ──────────────────────────────────────────────
# SSE 流式推送
# ──────────────────────────────────────────────

@router.get(
    "/{session_id}/stream",
    summary="SSE：订阅会话内任务进度与 token 流",
    description="前端通过 EventSource 连接此接口，实时接收 token / progress / done / error 事件",
)
async def stream_session(
    session_id: int,
    current_user: CurrentUser,
    session_repo: SessionRepoDepend,
) -> StreamingResponse:
    # TODO: 验证归属；从 Redis 或内存队列读取 token 事件并以 SSE 格式推送
    pass
