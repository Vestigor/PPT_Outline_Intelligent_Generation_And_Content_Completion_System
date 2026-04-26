from __future__ import annotations

from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.model.entity.message import Message, MessageRole
from app.common.model.entity.outline import Outline
from app.common.model.entity.report import SessionReport
from app.common.model.entity.session import Session, SessionStage, SessionType
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
        from sqlalchemy import func
        result = await self._db.execute(
            select(func.count()).select_from(Session).where(Session.user_id == user_id)
        )
        return result.scalar_one()

    async def create(
        self,
        user_id: int,
        title: str,
        session_type: SessionType,
        llm_config_id: int | None,
        search_config_id: int | None,
        rag_enabled: bool = True,
        deep_search_enabled: bool = True,
    ) -> Session:
        session = Session(
            user_id=user_id,
            title=title,
            session_type=session_type,
            stage=SessionStage.REQUIREMENT_COLLECTION,
            requirements={},
            requirements_complete=False,
            message_count=0,
            current_user_llm_config_id=llm_config_id,
            current_user_search_config_id=search_config_id,
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

    async def create(
        self,
        session_id: int,
        role: MessageRole,
        seq_no: int,
        content: str | None = None,
        outline_json: dict | None = None,
    ) -> Message:
        msg = Message(
            session_id=session_id,
            role=role,
            seq_no=seq_no,
            content=content,
            outline_json=outline_json,
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
        from datetime import datetime, timezone
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

    async def find_by_session(self, session_id: int) -> list[Slide]:
        result = await self._db.execute(
            select(Slide)
            .where(Slide.session_id == session_id)
            .order_by(Slide.version.desc())
            .limit(1)
        )
        return list(result.scalars().all())

    async def find_latest_by_session(self, session_id: int) -> Optional[Slide]:
        result = await self._db.execute(
            select(Slide)
            .where(Slide.session_id == session_id)
            .order_by(Slide.version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

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
        from datetime import datetime, timezone
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
    ) -> SessionReport:
        report = SessionReport(
            session_id=session_id,
            file_name=file_name,
            file_type=file_type,
            size_bytes=size_bytes,
            oss_key=oss_key,
            clean_text=clean_text,
        )
        self._db.add(report)
        await self._db.flush()
        await self._db.refresh(report)
        return report

    async def update_clean_text(self, report_id: int, clean_text: str) -> None:
        result = await self._db.execute(
            select(SessionReport).where(SessionReport.id == report_id)
        )
        report = result.scalar_one_or_none()
        if report is not None:
            report.clean_text = clean_text
            await self._db.flush()
