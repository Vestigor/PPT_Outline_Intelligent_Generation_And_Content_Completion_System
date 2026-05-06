from __future__ import annotations

from typing import Annotated, AsyncGenerator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.user_context.user_context import UserContext
from app.infrastructure.log.logging_config import get_logger
from app.infrastructure.security.security import decode_access_token
from app.infrastructure.database.postgre_sql import AsyncSessionLocal
from app.modules.user.repository.user_repository import UserRepository
from app.modules.user.service.user_service import UserService
from app.modules.knowledge_base.repository.knowledge_repository import (
    DocumentFileRepository,
    SessionKnowledgeRefRepository,
)
from app.modules.knowledge_base.service.knowledge_base_service import KnowledgeBaseService
from app.modules.model.repository.model_repository import (
    LLMProviderRepository,
    LLMProviderModelRepository,
    UserLLMConfigRepository,
    UserRagConfigRepository,
    UserSearchConfigRepository,
)
from app.modules.model.service.model_service import ModelService
from app.modules.session.repository.session_repository import (
    MessageRepository,
    OutlineRepository,
    ReportRepository,
    SessionRepository,
    SlideRepository,
)
from app.modules.session.service.session_service import SessionService
from app.modules.task.repository.task_repository import TaskRepository
from app.modules.task.service.task_service import TaskService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/users/login")
Token = Annotated[str, Depends(oauth2_scheme)]
logger = get_logger(__name__)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """生成每个请求独立的异步数据库会话，自动提交/回滚。"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


DBSession = Annotated[AsyncSession, Depends(get_db)]


# ──────────────────────────────────────────────
# User
# ──────────────────────────────────────────────

async def get_user_repository(db: DBSession) -> UserRepository:
    return UserRepository(db)

UserRepoDepend = Annotated[UserRepository, Depends(get_user_repository)]


async def get_user_service(repo: UserRepoDepend) -> UserService:
    return UserService(repo)

UserServiceDepend = Annotated[UserService, Depends(get_user_service)]


async def get_current_user(token: Token):
    try:
        payload = await decode_access_token(token)
        return UserContext.from_payload(payload)
    except ValueError as e:
        logger.error(e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )

CurrentUser = Annotated[UserContext, Depends(get_current_user)]


# ──────────────────────────────────────────────
# Knowledge Base
# ──────────────────────────────────────────────

async def get_document_file_repository(db: DBSession) -> DocumentFileRepository:
    return DocumentFileRepository(db)

DocumentFileRepoDepend = Annotated[DocumentFileRepository, Depends(get_document_file_repository)]

async def get_session_knowledge_ref_repository(db: DBSession) -> SessionKnowledgeRefRepository:
    return SessionKnowledgeRefRepository(db)

SessionKnowledgeRefRepoDepend = Annotated[SessionKnowledgeRefRepository, Depends(get_session_knowledge_ref_repository)]

async def get_knowledge_service(
    doc_repo: DocumentFileRepoDepend,
    ref_repo: SessionKnowledgeRefRepoDepend,
) -> KnowledgeBaseService:
    return KnowledgeBaseService(doc_repo, ref_repo)

KnowledgeServiceDepend = Annotated[KnowledgeBaseService, Depends(get_knowledge_service)]


# ──────────────────────────────────────────────
# Model
# ──────────────────────────────────────────────

async def get_llm_provider_repository(db: DBSession) -> LLMProviderRepository:
    return LLMProviderRepository(db)

LLMProviderRepoDepend = Annotated[LLMProviderRepository, Depends(get_llm_provider_repository)]

async def get_llm_provider_model_repository(db: DBSession) -> LLMProviderModelRepository:
    return LLMProviderModelRepository(db)

LLMProviderModelRepoDepend = Annotated[LLMProviderModelRepository, Depends(get_llm_provider_model_repository)]

async def get_user_llm_config_repository(db: DBSession) -> UserLLMConfigRepository:
    return UserLLMConfigRepository(db)

UserLLMConfigRepoDepend = Annotated[UserLLMConfigRepository, Depends(get_user_llm_config_repository)]

async def get_user_rag_config_repository(db: DBSession) -> UserRagConfigRepository:
    return UserRagConfigRepository(db)

UserRagConfigRepoDepend = Annotated[UserRagConfigRepository, Depends(get_user_rag_config_repository)]

async def get_user_search_config_repository(db: DBSession) -> UserSearchConfigRepository:
    return UserSearchConfigRepository(db)

UserSearchConfigRepoDepend = Annotated[UserSearchConfigRepository, Depends(get_user_search_config_repository)]

async def get_model_service(
    provider_repo: LLMProviderRepoDepend,
    model_repo: LLMProviderModelRepoDepend,
    user_llm_repo: UserLLMConfigRepoDepend,
    rag_repo: UserRagConfigRepoDepend,
    user_search_repo: UserSearchConfigRepoDepend,
) -> ModelService:
    return ModelService(
        provider_repo,
        model_repo,
        user_llm_repo,
        rag_repo,
        user_search_repo,
    )

ModelServiceDepend = Annotated[ModelService, Depends(get_model_service)]


# ──────────────────────────────────────────────
# Session
# ──────────────────────────────────────────────

async def get_session_repository(db: DBSession) -> SessionRepository:
    return SessionRepository(db)

SessionRepoDepend = Annotated[SessionRepository, Depends(get_session_repository)]


async def get_message_repository(db: DBSession) -> MessageRepository:
    return MessageRepository(db)

MessageRepoDepend = Annotated[MessageRepository, Depends(get_message_repository)]


async def get_outline_repository(db: DBSession) -> OutlineRepository:
    return OutlineRepository(db)

OutlineRepoDepend = Annotated[OutlineRepository, Depends(get_outline_repository)]


async def get_slide_repository(db: DBSession) -> SlideRepository:
    return SlideRepository(db)

SlideRepoDepend = Annotated[SlideRepository, Depends(get_slide_repository)]


async def get_report_repository(db: DBSession) -> ReportRepository:
    return ReportRepository(db)

ReportRepoDepend = Annotated[ReportRepository, Depends(get_report_repository)]


async def get_session_service(
    session_repo: SessionRepoDepend,
    message_repo: MessageRepoDepend,
    outline_repo: OutlineRepoDepend,
    slide_repo: SlideRepoDepend,
    report_repo: ReportRepoDepend,
    task_repo: TaskRepoDepend,
) -> SessionService:
    return SessionService(
        session_repo=session_repo,
        message_repo=message_repo,
        outline_repo=outline_repo,
        slide_repo=slide_repo,
        report_repo=report_repo,
        task_repo=task_repo,
    )

SessionServiceDepend = Annotated[SessionService, Depends(get_session_service)]


# ──────────────────────────────────────────────
# Task
# ──────────────────────────────────────────────

async def get_task_repository(db: DBSession) -> TaskRepository:
    return TaskRepository(db)

TaskRepoDepend = Annotated[TaskRepository, Depends(get_task_repository)]


async def get_task_service(task_repo: TaskRepoDepend) -> TaskService:
    return TaskService(task_repo)

TaskServiceDepend = Annotated[TaskService, Depends(get_task_service)]
