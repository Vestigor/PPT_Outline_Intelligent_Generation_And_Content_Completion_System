from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile, status

from app.dependencies import CurrentUser, KnowledgeServiceDepend, SessionServiceDepend
from app.common.result.result import Result
from app.modules.knowledge_base.dto.request import (
    AddKnowledgeRefsRequest, RenameCategoryRequest, UpdateFileCategoryRequest,
)
from app.modules.knowledge_base.dto.response import (
    DocumentResponse,
    DocumentUploadResponse,
    SessionKnowledgeRefResponse,
)

router = APIRouter(prefix="/knowledge", tags=["知识库管理"])


@router.get(
    "",
    response_model=Result[list[DocumentResponse]],
    summary="获取用户的知识库文件列表",
    description="返回当前用户的所有知识库文件，按上传时间倒序。",
)
async def list_documents(
    current_user: CurrentUser,
    svc: KnowledgeServiceDepend,
) -> Result[list[DocumentResponse]]:
    files = await svc.list_documents(current_user.id)
    return Result.success([DocumentResponse.model_validate(f) for f in files])


@router.post(
    "",
    response_model=Result[DocumentUploadResponse],
    status_code=status.HTTP_201_CREATED,
    summary="上传知识库文件",
    description="上传文件到用户知识库。文件处理（文本提取、切块、向量化）**异步**完成。",
)
async def upload_document(
    current_user: CurrentUser,
    svc: KnowledgeServiceDepend,
    file: UploadFile = File(..., description="知识库文件（PDF / DOCX / MD / TXT）"),
    category: str = Form("default"),
) -> Result[DocumentUploadResponse]:
    content = await file.read()
    result = await svc.upload_document(
        user_id=current_user.id,
        category=category,
        file_name=file.filename or "upload",
        file_type=file.content_type or "application/octet-stream",
        content=content,
    )
    return Result.success(result)


@router.get(
    "/{file_id}",
    response_model=Result[DocumentResponse],
    summary="查询知识库文件处理状态",
    description="查询单个知识库文件的处理状态（`pending` / `processing` / `ready` / `failed`）。",
)
async def get_document(
    file_id: int,
    current_user: CurrentUser,
    svc: KnowledgeServiceDepend,
) -> Result[DocumentResponse]:
    file = await svc.get_document(current_user.id, file_id)
    return Result.success(DocumentResponse.model_validate(file))


@router.post(
    "/{file_id}/retry",
    response_model=Result[DocumentResponse],
    summary="重试失败的知识库文件处理",
    description="仅 `failed` 状态的文件可重试。重试后文件重置为 `pending` 并重新入队处理。",
)
async def retry_knowledge_file(
    file_id: int,
    current_user: CurrentUser,
    svc: KnowledgeServiceDepend,
) -> Result[DocumentResponse]:
    file = await svc.retry_document(current_user.id, file_id)
    return Result.success(DocumentResponse.model_validate(file))


@router.delete(
    "/{file_id}",
    response_model=Result[None],
    summary="删除知识库文件",
    description="删除知识库文件及其所有会话引用关系。",
)
async def delete_document(
    file_id: int,
    current_user: CurrentUser,
    svc: KnowledgeServiceDepend,
) -> Result[None]:
    await svc.delete_document(current_user.id, file_id)
    return Result.success()


@router.patch(
    "/{file_id}/category",
    response_model=Result[DocumentResponse],
    summary="修改知识库文件的分类",
    description="将单个文件移动到指定分类，分类名为空时归入 default。",
)
async def update_file_category(
    file_id: int,
    body: UpdateFileCategoryRequest,
    current_user: CurrentUser,
    svc: KnowledgeServiceDepend,
) -> Result[DocumentResponse]:
    new_cat = body.category.strip() or "default"
    file = await svc.update_file_category(current_user.id, file_id, new_cat)
    return Result.success(DocumentResponse.model_validate(file))


@router.patch(
    "/categories/{category}",
    response_model=Result[None],
    summary="重命名知识库分类",
    description="将当前用户指定分类下的所有文件批量改名到新分类。目标分类名不能与其他已有分类重名。",
)
async def rename_category(
    category: str,
    body: RenameCategoryRequest,
    current_user: CurrentUser,
    svc: KnowledgeServiceDepend,
) -> Result[None]:
    await svc.rename_category(current_user.id, category, body.new_name.strip())
    return Result.success()


# ──────────────────────────────────────────────
# 会话知识库引用管理
# ──────────────────────────────────────────────

@router.get(
    "/sessions/{session_id}/refs",
    response_model=Result[list[SessionKnowledgeRefResponse]],
    summary="获取会话引用的知识库文件列表",
    description="返回当前会话引用的所有知识库文件及其处理状态。",
)
async def list_session_knowledge_refs(
    session_id: int,
    current_user: CurrentUser,
    svc: KnowledgeServiceDepend,
    session_svc: SessionServiceDepend,
) -> Result[list[SessionKnowledgeRefResponse]]:
    await session_svc.get_session(current_user.id, session_id)
    refs = await svc.list_session_refs(session_id)
    return Result.success(refs)


@router.post(
    "/sessions/{session_id}/refs",
    response_model=Result[dict],
    summary="为会话添加知识库引用（支持批量）",
    description="将知识库文件关联到会话，建立引用关系。已关联的文件自动跳过。",
)
async def add_session_knowledge_refs(
    session_id: int,
    body: AddKnowledgeRefsRequest,
    current_user: CurrentUser,
    svc: KnowledgeServiceDepend,
    session_svc: SessionServiceDepend,
) -> Result[dict]:
    await session_svc.get_session(current_user.id, session_id)
    refs = await svc.add_refs(current_user.id, session_id, body.knowledge_file_ids)
    return Result.success({
        "added_count": len(refs),
        "message": f"已成功引用 {len(refs)} 个知识库文件",
    })


@router.delete(
    "/sessions/{session_id}/refs/{knowledge_file_id}",
    response_model=Result[None],
    summary="取消引用知识库文件",
    description="删除会话与知识库文件的引用关系。",
)
async def remove_session_knowledge_ref(
    session_id: int,
    knowledge_file_id: int,
    current_user: CurrentUser,
    svc: KnowledgeServiceDepend,
    session_svc: SessionServiceDepend,
) -> Result[None]:
    await session_svc.get_session(current_user.id, session_id)
    await svc.remove_ref(session_id, knowledge_file_id)
    return Result.success()
