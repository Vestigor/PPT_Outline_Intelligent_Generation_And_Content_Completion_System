from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, Query, UploadFile
from fastapi.responses import Response

from app.dependencies import (
    CurrentUser,
    MessageRepoDepend,
    OutlineRepoDepend,
    SessionRepoDepend,
    SessionServiceDepend,
    SlideRepoDepend,
)
from app.common.result.result import Result
from app.common.exception.code import StatusCode
from app.common.exception.exception import BusinessException
from app.modules.session.dto.request import (
    ModifyOutlineRequest,
    ModifySlideRequest,
    SendMessageRequest,
    UpdateSessionSettingsRequest,
)
from app.modules.session.dto.response import (
    MessageResponse,
    OutlineResponse,
    SendMessageResponse,
    SessionDetailResponse,
    SessionListResponse,
    SessionSummaryResponse,
    SlideResponse,
    StartSessionResponse,
)
from app.infrastructure.log.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/sessions", tags=["会话管理"])


# ──────────────────────────────────────────────
# 会话生命周期
# ──────────────────────────────────────────────

@router.post(
    "/start",
    response_model=Result[StartSessionResponse],
    summary="创建会话并发送第一条消息",
    description=(
        "原子操作：创建会话并处理首条消息。\n"
        "- 携带报告文件 → REPORT_DRIVEN（跳过需求收集，直接生成大纲）\n"
        "- 纯文本 → GUIDED（多轮对话收集需求）\n"
        "返回 task_id 时，通过 GET /tasks/{task_id}/stream 订阅 SSE 流式输出。"
    ),
)
async def start_session(
    current_user: CurrentUser,
    svc: SessionServiceDepend,
    content: Annotated[str, Form(description="第一条消息内容")],
    llm_config_id: Annotated[int | None, Form(description="LLM 配置 ID")] = None,
    title: Annotated[str, Form(description="会话标题（留空自动截取消息前 50 字）")] = "",
    report_file: Annotated[UploadFile | None, File(description="报告文件（PDF/DOCX/MD/TXT）")] = None,
    rag_enabled: Annotated[bool, Form(description="是否启用 RAG")] = False,
    deep_search_enabled: Annotated[bool, Form(description="是否启用 DeepSearch")] = False,
) -> Result[StartSessionResponse]:
    result = await svc.start_session(
        user_id=current_user.id,
        llm_config_id=llm_config_id,
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
    sessions = await session_repo.find_by_user(
        current_user.id, page=page, page_size=page_size
    )
    total = await session_repo.count_by_user(current_user.id)
    items = [SessionSummaryResponse.model_validate(s) for s in sessions]
    return Result.success(
        SessionListResponse(items=items, total=total, page=page, page_size=page_size)
    )


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
    session = await session_repo.find_by_id_and_user(session_id, current_user.id)
    if session is None:
        raise BusinessException.exc(StatusCode.SESSION_NOT_FOUND.value)
    return Result.success(SessionDetailResponse.model_validate(session))


@router.delete(
    "/{session_id}",
    response_model=Result[None],
    summary="删除会话（级联删除所有消息、大纲、幻灯片）",
)
async def delete_session(
    session_id: int,
    current_user: CurrentUser,
    session_repo: SessionRepoDepend,
) -> Result[None]:
    deleted = await session_repo.delete_by_id_and_user(session_id, current_user.id)
    if not deleted:
        raise BusinessException.exc(StatusCode.SESSION_NOT_FOUND.value)
    logger.info("Deleted session %d by user %d", session_id, current_user.id)
    return Result.success(None)


@router.patch(
    "/{session_id}/settings",
    response_model=Result[SessionDetailResponse],
    summary="更新会话设置（模型配置、RAG/DeepSearch 开关）",
)
async def update_session_settings(
    session_id: int,
    body: UpdateSessionSettingsRequest,
    current_user: CurrentUser,
    svc: SessionServiceDepend,
    session_repo: SessionRepoDepend,
) -> Result[SessionDetailResponse]:
    session = await session_repo.find_by_id_and_user(session_id, current_user.id)
    if session is None:
        raise BusinessException.exc(StatusCode.SESSION_NOT_FOUND.value)
    updated = await svc.update_session_settings(
        session,
        llm_config_id=body.llm_config_id,
        rag_enabled=body.rag_enabled,
        deep_search_enabled=body.deep_search_enabled,
    )
    return Result.success(SessionDetailResponse.model_validate(updated))


# ──────────────────────────────────────────────
# 消息
# ──────────────────────────────────────────────

@router.post(
    "/{session_id}/messages",
    response_model=Result[SendMessageResponse],
    summary="在已有会话中发送消息",
    description=(
        "消息由语义路由：\n"
        "- 需求收集阶段：持续收集需求，完整后自动触发大纲生成\n"
        "- 大纲确认阶段：语义判断「确认/修改/无关」\n"
        "- 内容确认阶段：语义判断「确认/修改/无关」\n"
        "返回 task_id 时通过 SSE 订阅实时输出。"
    ),
)
async def send_message(
    session_id: int,
    body: SendMessageRequest,
    current_user: CurrentUser,
    svc: SessionServiceDepend,
    session_repo: SessionRepoDepend,
) -> Result[SendMessageResponse]:
    session = await session_repo.find_by_id_and_user(session_id, current_user.id)
    if session is None:
        raise BusinessException.exc(StatusCode.SESSION_NOT_FOUND.value)
    result = await svc.handle_message(session=session, content=body.content)
    return Result.success(result)


@router.get(
    "/{session_id}/messages",
    response_model=Result[list[MessageResponse]],
    summary="获取会话完整消息历史",
)
async def list_messages(
    session_id: int,
    current_user: CurrentUser,
    session_repo: SessionRepoDepend,
    message_repo: MessageRepoDepend,
) -> Result[list[MessageResponse]]:
    session = await session_repo.find_by_id_and_user(session_id, current_user.id)
    if session is None:
        raise BusinessException.exc(StatusCode.SESSION_NOT_FOUND.value)
    messages = await message_repo.find_by_session(session_id)
    return Result.success([MessageResponse.model_validate(m) for m in messages])


# ──────────────────────────────────────────────
# 大纲
# ──────────────────────────────────────────────

@router.get(
    "/{session_id}/outline",
    response_model=Result[OutlineResponse],
    summary="获取最新版本大纲",
)
async def get_outline(
    session_id: int,
    current_user: CurrentUser,
    session_repo: SessionRepoDepend,
    outline_repo: OutlineRepoDepend,
) -> Result[OutlineResponse]:
    session = await session_repo.find_by_id_and_user(session_id, current_user.id)
    if session is None:
        raise BusinessException.exc(StatusCode.SESSION_NOT_FOUND.value)
    outline = await outline_repo.find_latest_by_session(session_id)
    if outline is None:
        raise BusinessException.exc(StatusCode.OUTLINE_NOT_FOUND.value)
    return Result.success(OutlineResponse.model_validate(outline))


@router.post(
    "/{session_id}/outline/confirm",
    response_model=Result[SendMessageResponse],
    summary="直接确认大纲并启动幻灯片生成",
    description="无需发消息，直接确认当前大纲并触发 SLIDE_BATCH 任务（大纲编辑器专用）。",
)
async def confirm_outline(
    session_id: int,
    current_user: CurrentUser,
    svc: SessionServiceDepend,
    session_repo: SessionRepoDepend,
) -> Result[SendMessageResponse]:
    session = await session_repo.find_by_id_and_user(session_id, current_user.id)
    if session is None:
        raise BusinessException.exc(StatusCode.SESSION_NOT_FOUND.value)
    result = await svc.confirm_outline(session)
    return Result.success(result)


@router.put(
    "/{session_id}/outline",
    response_model=Result[OutlineResponse],
    summary="直接编辑大纲 JSON（保存为新版本，不触发 LLM）",
    description="用户在前端直接修改大纲后提交，保存为新版本。如需 LLM 协助修改，请通过发消息触发。",
)
async def update_outline(
    session_id: int,
    body: ModifyOutlineRequest,
    current_user: CurrentUser,
    session_repo: SessionRepoDepend,
    outline_repo: OutlineRepoDepend,
) -> Result[OutlineResponse]:
    session = await session_repo.find_by_id_and_user(session_id, current_user.id)
    if session is None:
        raise BusinessException.exc(StatusCode.SESSION_NOT_FOUND.value)
    from app.common.model.entity.session import SessionStage
    if session.stage not in (SessionStage.OUTLINE_CONFIRMING,):
        raise BusinessException.exc(StatusCode.STAGE_MISMATCH.value)

    version = await outline_repo.get_next_version(session_id)
    outline = await outline_repo.create(
        session_id=session_id,
        version=version,
        outline_json=body.outline_json,
    )
    logger.info("User %d manually updated outline for session %d, version=%d",
                current_user.id, session_id, version)
    return Result.success(OutlineResponse.model_validate(outline))


# ──────────────────────────────────────────────
# 幻灯片
# ──────────────────────────────────────────────

@router.get(
    "/{session_id}/slides",
    response_model=Result[SlideResponse],
    summary="获取最新版本幻灯片内容",
)
async def get_slides(
    session_id: int,
    current_user: CurrentUser,
    session_repo: SessionRepoDepend,
    slide_repo: SlideRepoDepend,
) -> Result[SlideResponse]:
    session = await session_repo.find_by_id_and_user(session_id, current_user.id)
    if session is None:
        raise BusinessException.exc(StatusCode.SESSION_NOT_FOUND.value)
    slide = await slide_repo.find_latest_by_session(session_id)
    if slide is None:
        raise BusinessException.exc(StatusCode.SLIDE_NOT_FOUND.value)
    return Result.success(SlideResponse.model_validate(slide))


@router.put(
    "/{session_id}/slides",
    response_model=Result[SlideResponse],
    summary="直接编辑幻灯片内容 JSON（全量保存为新版本，不触发 LLM）",
)
async def update_slides(
    session_id: int,
    body: ModifySlideRequest,
    current_user: CurrentUser,
    session_repo: SessionRepoDepend,
    slide_repo: SlideRepoDepend,
) -> Result[SlideResponse]:
    session = await session_repo.find_by_id_and_user(session_id, current_user.id)
    if session is None:
        raise BusinessException.exc(StatusCode.SESSION_NOT_FOUND.value)
    from app.common.model.entity.session import SessionStage
    if session.stage not in (SessionStage.CONTENT_CONFIRMING,):
        raise BusinessException.exc(StatusCode.STAGE_MISMATCH.value)

    version = await slide_repo.get_next_version(session_id)
    slide = await slide_repo.create(
        session_id=session_id,
        version=version,
        content=body.content,
    )
    logger.info("User %d manually updated slides for session %d, version=%d",
                current_user.id, session_id, version)
    return Result.success(SlideResponse.model_validate(slide))


# ──────────────────────────────────────────────
# 导出
# ──────────────────────────────────────────────

@router.get(
    "/{session_id}/export",
    summary="导出 PPT 为纯文本文件",
    description=(
        "将幻灯片内容导出为 Markdown 或 Word 文件。\n"
        "- `format=md`（默认）：返回 .md 文本文件\n"
        "- `format=docx`：返回 .docx Word 文件"
    ),
)
async def export_ppt(
    session_id: int,
    current_user: CurrentUser,
    session_repo: SessionRepoDepend,
    slide_repo: SlideRepoDepend,
    format: Literal["md", "docx"] = Query("md", description="导出格式：md 或 docx"),
) -> Response:
    from app.infrastructure.export.export_service import ExportService

    session = await session_repo.find_by_id_and_user(session_id, current_user.id)
    if session is None:
        raise BusinessException.exc(StatusCode.SESSION_NOT_FOUND.value)
    slide = await slide_repo.find_latest_by_session(session_id)
    if slide is None:
        raise BusinessException.exc(StatusCode.SLIDE_NOT_FOUND.value)

    svc = ExportService()
    logger.info(
        "Export request: session_id=%d user_id=%d format=%s",
        session_id, current_user.id, format,
    )

    if format == "docx":
        data = svc.to_word(slide.content)
        return Response(
            content=data,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f"attachment; filename=ppt_{session_id}.docx"},
        )

    # 默认 md
    text = svc.to_markdown(slide.content)
    return Response(
        content=text.encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=ppt_{session_id}.md"},
    )
