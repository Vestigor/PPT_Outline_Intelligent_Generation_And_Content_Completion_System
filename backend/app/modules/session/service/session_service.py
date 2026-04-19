from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile, status

from app.common.exception.code import StatusCode
from app.common.exception.exception import BusinessException
from app.common.model.entity.session import Session, SessionStage, SessionType
from app.common.result.result import Result

from app.modules.session.dto.response import (
    StartSessionResponse,
)

router = APIRouter(prefix="/sessions", tags=["会话管理"])

class SessionService:
    def __init__(
        self,
        session_repo: SessionRepository,
        outline_repo: OutlineRepository,
        slide_repo: SlideRepository,
        task_service: TaskService,
        llm_service: LLMService,
        rag_service: RAGService,
        deep_search_service: DeepSearchService,
    ) -> None:
        self._repo = session_repo
        self._outline_repo = outline_repo
        self._slide_repo = slide_repo
        self._task_svc = task_service
        self._llm = llm_service
        self._rag = rag_service
        self._deep_search = deep_search_service

    async def start_session(
            self,
            user_id: int,
            llm_config_id: int,
            search_config_id: int,
            title: str,
            content: str,
            file: UploadFile | None = None,
            rag_enabled: bool | None = None,
            deep_search_enabled: bool | None = None,
    ) -> StartSessionResponse:
        pass

    async def handle_message(
        self, session: Session, user_msg, content: str, judgeMeaning: bool = True
    ) -> dict:
        pass
        


    async def _handle_requirement_collection(
        self, session: Session, user_msg, content: str
    ) -> dict:
        pass

    async def _handle_outline_generation(
        self, session: Session, user_msg, content: str
    ) -> dict:
        pass

    async def _handle_outline_modification(
        self, session: Session, user_msg, content: str
    ) -> dict:
        pass

    async def _handle_slide_generation(
        self, session: Session, user_msg, content: str
    ) -> dict:
        pass

    async def _handle_slide_modification(
        self, session: Session, user_msg, content: str
    ) -> dict:
        pass

    async def _determine_the_semantic(self, content: str) -> str:
        pass

    async def _determine_the_semantic(self, message: str) -> str:
        pass


        

