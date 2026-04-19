from __future__ import annotations

from typing import Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.model.entity.document import DocumentFile, DocumentStatus
from app.common.model.entity.session_knowledge_ref import SessionKnowledgeRef


class DocumentFileRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def find_by_id(self, file_id: int) -> Optional[DocumentFile]:
        result = await self._db.execute(
            select(DocumentFile).where(DocumentFile.id == file_id)
        )
        return result.scalar_one_or_none()

    async def find_by_id_and_user(self, file_id: int, user_id: int) -> Optional[DocumentFile]:
        result = await self._db.execute(
            select(DocumentFile).where(
                DocumentFile.id == file_id,
                DocumentFile.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def find_by_user(self, user_id: int) -> list[DocumentFile]:
        result = await self._db.execute(
            select(DocumentFile)
            .where(DocumentFile.user_id == user_id)
            .order_by(DocumentFile.id.desc())
        )
        return list(result.scalars().all())

    async def find_by_content_hash(self, content_hash: str, user_id: int) -> Optional[DocumentFile]:
        result = await self._db.execute(
            select(DocumentFile).where(
                DocumentFile.content_hash == content_hash,
                DocumentFile.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        user_id: int,
        category: str,
        file_name: str,
        file_type: str,
        size_bytes: int,
        content_hash: str,
        oss_key: str,
    ) -> DocumentFile:
        doc = DocumentFile(
            user_id=user_id,
            category=category,
            file_name=file_name,
            file_type=file_type,
            size_bytes=size_bytes,
            content_hash=content_hash,
            oss_key=oss_key,
            status=DocumentStatus.PENDING,
        )
        self._db.add(doc)
        await self._db.flush()
        await self._db.refresh(doc)
        return doc

    async def update_status(
        self,
        file_id: int,
        status: DocumentStatus,
        error_message: str | None = None,
    ) -> None:
        doc = await self.find_by_id(file_id)
        if doc is not None:
            doc.status = status
            doc.error_message = error_message
            await self._db.flush()

    async def delete_by_id_and_user(self, file_id: int, user_id: int) -> bool:
        result = await self._db.execute(
            delete(DocumentFile).where(
                DocumentFile.id == file_id,
                DocumentFile.user_id == user_id,
            )
        )
        return result.rowcount > 0


class SessionKnowledgeRefRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def find_by_session(self, session_id: int) -> list[SessionKnowledgeRef]:
        result = await self._db.execute(
            select(SessionKnowledgeRef)
            .where(SessionKnowledgeRef.session_id == session_id)
            .order_by(SessionKnowledgeRef.id)
        )
        return list(result.scalars().all())

    async def find_by_session_and_file(
        self, session_id: int, knowledge_file_id: int
    ) -> Optional[SessionKnowledgeRef]:
        result = await self._db.execute(
            select(SessionKnowledgeRef).where(
                SessionKnowledgeRef.session_id == session_id,
                SessionKnowledgeRef.knowledge_file_id == knowledge_file_id,
            )
        )
        return result.scalar_one_or_none()

    async def create(self, session_id: int, knowledge_file_id: int) -> SessionKnowledgeRef:
        ref = SessionKnowledgeRef(
            session_id=session_id,
            knowledge_file_id=knowledge_file_id,
        )
        self._db.add(ref)
        await self._db.flush()
        await self._db.refresh(ref)
        return ref

    async def delete_by_session_and_file(
        self, session_id: int, knowledge_file_id: int
    ) -> bool:
        result = await self._db.execute(
            delete(SessionKnowledgeRef).where(
                SessionKnowledgeRef.session_id == session_id,
                SessionKnowledgeRef.knowledge_file_id == knowledge_file_id,
            )
        )
        return result.rowcount > 0
