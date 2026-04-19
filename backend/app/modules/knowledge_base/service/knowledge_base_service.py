from __future__ import annotations

import hashlib

from app.common.exception.code import StatusCode
from app.common.exception.exception import BusinessException
from app.common.model.entity.document import DocumentFile, DocumentStatus
from app.config import settings
from app.modules.knowledge_base.dto.response import (
    DocumentResponse,
    DocumentUploadResponse,
    SessionKnowledgeRefResponse,
)
from app.modules.knowledge_base.repository.knowledge_repository import (
    DocumentFileRepository,
    SessionKnowledgeRefRepository,
)


class KnowledgeBaseService:
    def __init__(
        self,
        doc_repo: DocumentFileRepository,
        ref_repo: SessionKnowledgeRefRepository,
    ) -> None:
        self._doc_repo = doc_repo
        self._ref_repo = ref_repo

    # ──────────────────────────────────────────────
    # 文件管理
    # ──────────────────────────────────────────────

    async def list_documents(self, user_id: int) -> list[DocumentFile]:
        return await self._doc_repo.find_by_user(user_id)

    async def get_document(self, user_id: int, file_id: int) -> DocumentFile:
        doc = await self._doc_repo.find_by_id_and_user(file_id, user_id)
        if doc is None:
            raise BusinessException.exc(StatusCode.DOCUMENT_NOT_FOUND.value)
        return doc

    async def upload_document(
        self,
        user_id: int,
        category: str,
        file_name: str,
        file_type: str,
        content: bytes,
    ) -> DocumentUploadResponse:
        size_bytes = len(content)
        max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if size_bytes > max_bytes:
            raise BusinessException.exc(StatusCode.DOCUMENT_SIZE_EXCEEDED.value)

        ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
        if ext not in settings.ALLOWED_EXTENSIONS:
            raise BusinessException.exc(StatusCode.UPLOAD_DOCUMENT_FAILED.value)

        content_hash = hashlib.sha256(content).hexdigest()

        # 同一用户相同内容已存在时复用（幂等上传）
        existing = await self._doc_repo.find_by_content_hash(content_hash, user_id)
        if existing is not None:
            return DocumentUploadResponse.model_validate(existing)
        
        # TODO: 存储到 OSS, 创建异步任务
        # 以下逻辑为暂时逻辑

        oss_key = f"knowledge/{user_id}/{content_hash[:16]}_{file_name}"
        doc = await self._doc_repo.create(
            user_id=user_id,
            category=category,
            file_name=file_name,
            file_type=file_type,
            size_bytes=size_bytes,
            content_hash=content_hash,
            oss_key=oss_key,
        )
        return DocumentUploadResponse.model_validate(doc)

    async def retry_document(self, user_id: int, file_id: int) -> DocumentFile:
        doc = await self._doc_repo.find_by_id_and_user(file_id, user_id)

        # TODO: 从 OSS 下载, 重新创建异步任务
        # 以下逻辑为暂时逻辑

        if doc is None:
            raise BusinessException.exc(StatusCode.DOCUMENT_NOT_FOUND.value)
        if doc.status != DocumentStatus.FAILED:
            raise BusinessException.exc(StatusCode.UPLOAD_DOCUMENT_FAILED.value)
        await self._doc_repo.update_status(file_id, DocumentStatus.PENDING, None)
        # 重新加载，返回最新状态
        doc = await self._doc_repo.find_by_id(file_id)
        return doc  # type: ignore[return-value]

    async def delete_document(self, user_id: int, file_id: int) -> None:
        doc = await self._doc_repo.find_by_id_and_user(file_id, user_id)
        if doc is None:
            raise BusinessException.exc(StatusCode.DOCUMENT_NOT_FOUND.value)
        deleted = await self._doc_repo.delete_by_id_and_user(file_id, user_id)
        if not deleted:
            raise BusinessException.exc(StatusCode.DELETE_DOCUMENT_FAILED.value)

    # ──────────────────────────────────────────────
    # 会话引用管理
    # ──────────────────────────────────────────────

    async def list_session_refs(self, session_id: int) -> list[SessionKnowledgeRefResponse]:
        refs = await self._ref_repo.find_by_session(session_id)
        result = []
        for ref in refs:
            doc = await self._doc_repo.find_by_id(ref.knowledge_file_id)
            if doc is None:
                continue
            result.append(
                SessionKnowledgeRefResponse(
                    id=ref.id,
                    session_id=ref.session_id,
                    knowledge_file_id=ref.knowledge_file_id,
                    knowledge_file=DocumentResponse.model_validate(doc),
                    created_at=ref.created_at,
                )
            )
        return result

    async def add_refs(
        self,
        user_id: int,
        session_id: int,
        knowledge_file_ids: list[int],
    ) -> list[SessionKnowledgeRefResponse]:
        added = []
        for file_id in knowledge_file_ids:
            # 验证文件属于当前用户
            doc = await self._doc_repo.find_by_id_and_user(file_id, user_id)
            if doc is None:
                raise BusinessException.exc(StatusCode.DOCUMENT_NOT_FOUND.value)
            # 已存在则跳过
            existing = await self._ref_repo.find_by_session_and_file(session_id, file_id)
            if existing is not None:
                continue
            ref = await self._ref_repo.create(session_id, file_id)
            added.append(
                SessionKnowledgeRefResponse(
                    id=ref.id,
                    session_id=ref.session_id,
                    knowledge_file_id=ref.knowledge_file_id,
                    knowledge_file=DocumentResponse.model_validate(doc),
                    created_at=ref.created_at,
                )
            )
        return added

    async def remove_ref(self, session_id: int, knowledge_file_id: int) -> None:
        deleted = await self._ref_repo.delete_by_session_and_file(session_id, knowledge_file_id)
        if not deleted:
            raise BusinessException.exc(StatusCode.REMOVE_KNOWLEDGE_REF_FAILED.value)
