from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.model.entity.message import Message, MessageRole
from app.common.model.entity.outline import Outline
from app.common.model.entity.report import SessionReport
from app.common.model.entity.session import Session, SessionStage, SessionType
from app.common.model.entity.session_knowledge_ref import SessionKnowledgeRef
from app.common.model.entity.slide import Slide


class SessionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def find_by_id(self, session_id: int) -> Optional[Session]:
        result = await self._db.execute(
            select(Session).where(Session.id == session_id)
        )
        return result.scalar_one_or_none()

    async def find_by_id_and_user(self, session_id: int, user_id: int) -> Optional[Session]:
        result = await self._db.execute(
            select(Session).where(
                Session.id == session_id,
                Session.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def find_by_user(
        self, user_id: int, page: int = 1, page_size: int = 20
    ) -> list[Session]:
        offset = (page - 1) * page_size
        result = await self._db.execute(
            select(Session)
            .where(Session.user_id == user_id)
            .order_by(Session.id.desc())
            .offset(offset)
            .limit(page_size)
        )
        return list(result.scalars().all())

    async def count_by_user(self, user_id: int) -> int:
        result = await self._db.execute(
            select(func.count()).select_from(Session).where(Session.user_id == user_id)
        )
        return result.scalar_one()

    async def create(
        self,
        user_id: int,
        title: str,
        session_type: SessionType,
        stage: SessionStage = SessionStage.REQUIREMENT_COLLECTION,
        llm_config_id: int | None = None,
        rag_enabled: bool = False,
        deep_search_enabled: bool = False,
    ) -> Session:
        session = Session(
            user_id=user_id,
            title=title,
            session_type=session_type,
            stage=stage,
            requirements={},
            requirements_complete=False,
            message_count=0,
            current_user_llm_config_id=llm_config_id,
            rag_enabled=rag_enabled,
            deep_search_enabled=deep_search_enabled,
        )
        self._db.add(session)
        await self._db.flush()
        await self._db.refresh(session)
        return session

    async def update(self, session: Session) -> None:
        await self._db.flush()

    async def delete_by_id_and_user(self, session_id: int, user_id: int) -> bool:
        result = await self._db.execute(
            delete(Session).where(
                Session.id == session_id,
                Session.user_id == user_id,
            )
        )
        return result.rowcount > 0


class MessageRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def find_by_id(self, message_id: int) -> Optional[Message]:
        result = await self._db.execute(
            select(Message).where(Message.id == message_id)
        )
        return result.scalar_one_or_none()

    async def find_by_session(self, session_id: int) -> list[Message]:
        result = await self._db.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.seq_no)
        )
        return list(result.scalars().all())

    async def find_latest_by_session(self, session_id: int) -> Optional[Message]:
        result = await self._db.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.seq_no.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def find_conversation_history(
        self, session_id: int, limit: int = 20
    ) -> list[dict[str, str]]:
        """返回适合作为 LLM messages 列表的对话历史（最近 limit 条）。"""
        result = await self._db.execute(
            select(Message)
            .where(
                Message.session_id == session_id,
                Message.role.in_([MessageRole.USER, MessageRole.ASSISTANT]),
                Message.content.isnot(None),
            )
            .order_by(Message.seq_no.desc())
            .limit(limit)
        )
        msgs = list(reversed(result.scalars().all()))
        return [{"role": m.role.value, "content": m.content} for m in msgs]

    async def create(
        self,
        session_id: int,
        role: MessageRole,
        seq_no: int,
        content: str | None = None,
        outline_json: dict | None = None,
        slide_json: dict | None = None,
    ) -> Message:
        msg = Message(
            session_id=session_id,
            role=role,
            seq_no=seq_no,
            content=content,
            outline_json=outline_json,
            slide_json=slide_json,
        )
        self._db.add(msg)
        await self._db.flush()
        await self._db.refresh(msg)
        return msg

    async def update_outline_json(self, message_id: int, outline_json: dict) -> None:
        msg = await self.find_by_id(message_id)
        if msg is not None:
            msg.outline_json = outline_json
            await self._db.flush()

    async def update_slide_json(self, message_id: int, slide_json: dict) -> None:
        msg = await self.find_by_id(message_id)
        if msg is not None:
            msg.slide_json = slide_json
            await self._db.flush()

    async def update_content(self, message_id: int, content: str) -> None:
        msg = await self.find_by_id(message_id)
        if msg is not None:
            msg.content = content
            await self._db.flush()


class OutlineRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def find_by_id(self, outline_id: int) -> Optional[Outline]:
        result = await self._db.execute(
            select(Outline).where(Outline.id == outline_id)
        )
        return result.scalar_one_or_none()

    async def find_latest_by_session(self, session_id: int) -> Optional[Outline]:
        result = await self._db.execute(
            select(Outline)
            .where(Outline.session_id == session_id)
            .order_by(Outline.version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def find_all_by_session(self, session_id: int) -> list[Outline]:
        result = await self._db.execute(
            select(Outline)
            .where(Outline.session_id == session_id)
            .order_by(Outline.version)
        )
        return list(result.scalars().all())

    async def get_next_version(self, session_id: int) -> int:
        result = await self._db.execute(
            select(func.max(Outline.version)).where(Outline.session_id == session_id)
        )
        current_max = result.scalar_one_or_none()
        return (current_max or 0) + 1

    async def create(
        self, session_id: int, version: int, outline_json: dict
    ) -> Outline:
        outline = Outline(
            session_id=session_id,
            version=version,
            outline_json=outline_json,
        )
        self._db.add(outline)
        await self._db.flush()
        await self._db.refresh(outline)
        return outline

    async def update_json(self, outline_id: int, outline_json: dict) -> None:
        outline = await self.find_by_id(outline_id)
        if outline is not None:
            outline.outline_json = outline_json
            await self._db.flush()

    async def confirm(self, outline_id: int) -> Optional[Outline]:
        outline = await self.find_by_id(outline_id)
        if outline is not None:
            outline.confirmed_at = datetime.now(timezone.utc)
            await self._db.flush()
        return outline


class SlideRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def find_by_id(self, slide_id: int) -> Optional[Slide]:
        result = await self._db.execute(
            select(Slide).where(Slide.id == slide_id)
        )
        return result.scalar_one_or_none()

    async def find_latest_by_session(self, session_id: int) -> Optional[Slide]:
        result = await self._db.execute(
            select(Slide)
            .where(Slide.session_id == session_id)
            .order_by(Slide.version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def find_all_by_session(self, session_id: int) -> list[Slide]:
        result = await self._db.execute(
            select(Slide)
            .where(Slide.session_id == session_id)
            .order_by(Slide.version)
        )
        return list(result.scalars().all())

    async def get_next_version(self, session_id: int) -> int:
        result = await self._db.execute(
            select(func.max(Slide.version)).where(Slide.session_id == session_id)
        )
        current_max = result.scalar_one_or_none()
        return (current_max or 0) + 1

    async def create(
        self, session_id: int, version: int, content: dict
    ) -> Slide:
        slide = Slide(
            session_id=session_id,
            version=version,
            content=content,
        )
        self._db.add(slide)
        await self._db.flush()
        await self._db.refresh(slide)
        return slide

    async def update_content(self, slide_id: int, content: dict) -> None:
        slide = await self.find_by_id(slide_id)
        if slide is not None:
            slide.content = content
            await self._db.flush()

    async def confirm(self, slide_id: int) -> Optional[Slide]:
        slide = await self.find_by_id(slide_id)
        if slide is not None:
            slide.confirmed_at = datetime.now(timezone.utc)
            await self._db.flush()
        return slide


class ReportRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def find_by_session(self, session_id: int) -> Optional[SessionReport]:
        result = await self._db.execute(
            select(SessionReport).where(SessionReport.session_id == session_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        session_id: int,
        file_name: str,
        file_type: str,
        size_bytes: int,
        oss_key: str,
        clean_text: str | None = None,
        content_hash: str | None = None,
    ) -> SessionReport:
        report = SessionReport(
            session_id=session_id,
            file_name=file_name,
            file_type=file_type,
            size_bytes=size_bytes,
            oss_key=oss_key,
            clean_text=clean_text,
            content_hash=content_hash,
        )
        self._db.add(report)
        await self._db.flush()
        await self._db.refresh(report)
        return report

    async def update_clean_text(self, report_id: int, clean_text: str, content_hash: str) -> None:
        result = await self._db.execute(
            select(SessionReport).where(SessionReport.id == report_id)
        )
        report = result.scalar_one_or_none()
        if report is not None:
            report.clean_text = clean_text
            report.content_hash = content_hash
            await self._db.flush()


class KnowledgeRefRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def find_file_ids_by_session(self, session_id: int) -> list[int]:
        """返回会话关联的所有 ready 状态知识文件 ID。"""
        from app.common.model.entity.document import DocumentFile, DocumentStatus
        result = await self._db.execute(
            select(SessionKnowledgeRef.knowledge_file_id)
            .join(DocumentFile, DocumentFile.id == SessionKnowledgeRef.knowledge_file_id)
            .where(
                SessionKnowledgeRef.session_id == session_id,
                DocumentFile.status == DocumentStatus.READY,
            )
        )
        return list(result.scalars().all())
