from __future__ import annotations

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# 导入 Base（所有实体类的声明式基类）
from app.common.model.base_entity.base_entity import BaseEntity

# 导入全部实体，确保它们的元数据注册到 Base.metadata
from app.common.model.entity.user import User  # noqa: F401
from app.common.model.entity.session import Session  # noqa: F401
from app.common.model.entity.message import Message  # noqa: F401
from app.common.model.entity.task import Task  # noqa: F401
from app.common.model.entity.report import SessionReport  # noqa: F401
from app.common.model.entity.outline import Outline  # noqa: F401
from app.common.model.entity.slide import Slide  # noqa: F401
from app.common.model.entity.document import DocumentFile  # noqa: F401
from app.common.model.entity.document_chunk import DocumentChunk  # noqa: F401
from app.common.model.entity.session_knowledge_ref import SessionKnowledgeRef  # noqa: F401
from app.common.model.entity.llm_provider import LLMProvider  # noqa: F401
from app.common.model.entity.llm_provider_model import LLMProviderModel  # noqa: F401
from app.common.model.entity.user_llm_config import UserLLMConfig  # noqa: F401
from app.common.model.entity.user_rag_config import UserRagConfig  # noqa: F401
from app.common.model.entity.user_search_config import UserSearchConfig  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = BaseEntity.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
