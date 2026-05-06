from __future__ import annotations

from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exception.code import StatusCode
from app.common.exception.exception import BusinessException
from app.common.model.entity.llm_provider import LLMProvider
from app.common.model.entity.llm_provider_model import LLMProviderModel
from app.common.model.entity.user_llm_config import UserLLMConfig
from app.common.model.entity.user_rag_config import UserRagConfig
from app.common.model.entity.user_search_config import UserSearchConfig
from app.infrastructure.log.logging_config import get_logger

logger = get_logger(__name__)


# ──────────────────────────────────────────────
# LLMProvider
# ──────────────────────────────────────────────

class LLMProviderRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def find_by_id(self, provider_id: int) -> Optional[LLMProvider]:
        result = await self._db.execute(
            select(LLMProvider).where(LLMProvider.id == provider_id)
        )
        return result.scalar_one_or_none()

    async def find_by_name(self, name: str) -> Optional[LLMProvider]:
        result = await self._db.execute(
            select(LLMProvider).where(LLMProvider.name == name)
        )
        return result.scalar_one_or_none()

    async def find_all(self) -> list[LLMProvider]:
        result = await self._db.execute(select(LLMProvider).order_by(LLMProvider.id))
        return list(result.scalars().all())

    async def find_active(self) -> list[LLMProvider]:
        result = await self._db.execute(
            select(LLMProvider).where(LLMProvider.is_active == True).order_by(LLMProvider.id)
        )
        return list(result.scalars().all())

    async def create(self, name: str, base_url: str, description: str | None, is_active: bool) -> LLMProvider:
        provider = LLMProvider(name=name, base_url=base_url, description=description, is_active=is_active)
        self._db.add(provider)
        await self._db.flush()
        await self._db.refresh(provider)
        return provider

    async def update(self, provider: LLMProvider) -> None:
        await self._db.flush()

    async def delete_by_id(self, provider_id: int) -> bool:
        result = await self._db.execute(
            delete(LLMProvider).where(LLMProvider.id == provider_id)
        )
        return result.rowcount > 0


# ──────────────────────────────────────────────
# LLMProviderModel
# ──────────────────────────────────────────────

class LLMProviderModelRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def find_by_id(self, model_id: int) -> Optional[LLMProviderModel]:
        result = await self._db.execute(
            select(LLMProviderModel).where(LLMProviderModel.id == model_id)
        )
        return result.scalar_one_or_none()

    async def find_by_provider(self, provider_id: int) -> list[LLMProviderModel]:
        result = await self._db.execute(
            select(LLMProviderModel)
            .where(LLMProviderModel.provider_id == provider_id)
            .order_by(LLMProviderModel.id)
        )
        return list(result.scalars().all())

    async def find_active_by_provider(self, provider_id: int) -> list[LLMProviderModel]:
        result = await self._db.execute(
            select(LLMProviderModel)
            .where(LLMProviderModel.provider_id == provider_id, LLMProviderModel.is_active == True)
            .order_by(LLMProviderModel.id)
        )
        return list(result.scalars().all())

    async def find_by_provider_and_name(self, provider_id: int, model_name: str) -> Optional[LLMProviderModel]:
        result = await self._db.execute(
            select(LLMProviderModel).where(
                LLMProviderModel.provider_id == provider_id,
                LLMProviderModel.model_name == model_name,
            )
        )
        return result.scalar_one_or_none()

    async def create(self, provider_id: int, model_name: str, description: str | None, is_active: bool) -> LLMProviderModel:
        model = LLMProviderModel(
            provider_id=provider_id,
            model_name=model_name,
            description=description,
            is_active=is_active,
        )
        self._db.add(model)
        await self._db.flush()
        await self._db.refresh(model)
        return model

    async def update(self, model: LLMProviderModel) -> None:
        await self._db.flush()

    async def delete_by_id(self, model_id: int) -> bool:
        result = await self._db.execute(
            delete(LLMProviderModel).where(LLMProviderModel.id == model_id)
        )
        return result.rowcount > 0


# ──────────────────────────────────────────────
# UserLLMConfig
# ──────────────────────────────────────────────

class UserLLMConfigRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def find_by_id(self, config_id: int) -> Optional[UserLLMConfig]:
        result = await self._db.execute(
            select(UserLLMConfig).where(UserLLMConfig.id == config_id)
        )
        return result.scalar_one_or_none()

    async def find_by_id_and_user(self, config_id: int, user_id: int) -> Optional[UserLLMConfig]:
        result = await self._db.execute(
            select(UserLLMConfig).where(
                UserLLMConfig.id == config_id,
                UserLLMConfig.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def find_by_user(self, user_id: int) -> list[UserLLMConfig]:
        result = await self._db.execute(
            select(UserLLMConfig)
            .where(UserLLMConfig.user_id == user_id)
            .order_by(UserLLMConfig.id)
        )
        return list(result.scalars().all())

    async def find_by_user_with_active_status(self, user_id: int) -> list[tuple[UserLLMConfig, bool]]:
        """返回用户所有配置，同时携带 is_active 标志（provider+model 均 active）。"""
        result = await self._db.execute(
            select(UserLLMConfig, LLMProviderModel.is_active, LLMProvider.is_active)
            .outerjoin(LLMProviderModel, LLMProviderModel.id == UserLLMConfig.provider_model_id)
            .outerjoin(LLMProvider, LLMProvider.id == LLMProviderModel.provider_id)
            .where(UserLLMConfig.user_id == user_id)
            .order_by(UserLLMConfig.id)
        )
        return [(row[0], bool(row[1]) and bool(row[2])) for row in result.all()]

    async def find_by_user_and_model(self, user_id: int, provider_model_id: int) -> Optional[UserLLMConfig]:
        result = await self._db.execute(
            select(UserLLMConfig).where(
                UserLLMConfig.user_id == user_id,
                UserLLMConfig.provider_model_id == provider_model_id,
            )
        )
        return result.scalar_one_or_none()

    async def find_default_with_active_check(self, user_id: int) -> Optional[UserLLMConfig]:
        """找到 is_default=True 且 provider+model 均 active 的配置。"""
        result = await self._db.execute(
            select(UserLLMConfig)
            .join(LLMProviderModel, LLMProviderModel.id == UserLLMConfig.provider_model_id)
            .join(LLMProvider, LLMProvider.id == LLMProviderModel.provider_id)
            .where(
                UserLLMConfig.user_id == user_id,
                UserLLMConfig.is_default == True,
                LLMProviderModel.is_active == True,
                LLMProvider.is_active == True,
            )
        )
        return result.scalar_one_or_none()

    async def find_active_for_user(self, user_id: int) -> list[UserLLMConfig]:
        """返回该用户所有 provider+model 均 active 的配置，按 id 降序。"""
        result = await self._db.execute(
            select(UserLLMConfig)
            .join(LLMProviderModel, LLMProviderModel.id == UserLLMConfig.provider_model_id)
            .join(LLMProvider, LLMProvider.id == LLMProviderModel.provider_id)
            .where(
                UserLLMConfig.user_id == user_id,
                LLMProviderModel.is_active == True,
                LLMProvider.is_active == True,
            )
            .order_by(UserLLMConfig.id.desc())
        )
        return list(result.scalars().all())

    async def create(
        self,
        user_id: int,
        provider_model_id: int,
        api_key_encrypted: str,
        provider_name: str,
        model_name: str,
        base_url: str,
        alias: str | None,
        is_default: bool,
    ) -> UserLLMConfig:
        config = UserLLMConfig(
            user_id=user_id,
            provider_model_id=provider_model_id,
            api_key=api_key_encrypted,
            provider_name=provider_name,
            model_name=model_name,
            base_url=base_url,
            alias=alias,
            is_default=is_default,
        )
        self._db.add(config)
        await self._db.flush()
        await self._db.refresh(config)
        return config

    async def clear_defaults(self, user_id: int) -> None:
        """将该用户所有 LLM 配置的 is_default 置为 False。"""
        configs = await self.find_by_user(user_id)
        for cfg in configs:
            cfg.is_default = False
        await self._db.flush()

    async def update(self, config: UserLLMConfig) -> None:
        await self._db.flush()

    async def delete_by_id_and_user(self, config_id: int, user_id: int) -> bool:
        result = await self._db.execute(
            delete(UserLLMConfig).where(
                UserLLMConfig.id == config_id,
                UserLLMConfig.user_id == user_id,
            )
        )
        return result.rowcount > 0


# ──────────────────────────────────────────────
# UserRagConfig
# ──────────────────────────────────────────────

class UserRagConfigRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def find_by_user(self, user_id: int) -> Optional[UserRagConfig]:
        result = await self._db.execute(
            select(UserRagConfig).where(UserRagConfig.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def create(self, user_id: int, api_key_encrypted: str) -> UserRagConfig:
        config = UserRagConfig(user_id=user_id, api_key=api_key_encrypted)
        self._db.add(config)
        await self._db.flush()
        await self._db.refresh(config)
        return config

    async def update(self, config: UserRagConfig) -> None:
        await self._db.flush()

    async def delete_by_user(self, user_id: int) -> bool:
        result = await self._db.execute(
            delete(UserRagConfig).where(UserRagConfig.user_id == user_id)
        )
        return result.rowcount > 0


# ──────────────────────────────────────────────
# UserSearchConfig（固定 Tavily，每用户一条）
# ──────────────────────────────────────────────

class UserSearchConfigRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def find_by_user(self, user_id: int) -> Optional[UserSearchConfig]:
        result = await self._db.execute(
            select(UserSearchConfig).where(UserSearchConfig.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def create(self, user_id: int, api_key_encrypted: str) -> UserSearchConfig:
        config = UserSearchConfig(user_id=user_id, api_key=api_key_encrypted)
        self._db.add(config)
        await self._db.flush()
        await self._db.refresh(config)
        return config

    async def update(self, config: UserSearchConfig) -> None:
        await self._db.flush()

    async def delete_by_user(self, user_id: int) -> bool:
        result = await self._db.execute(
            delete(UserSearchConfig).where(UserSearchConfig.user_id == user_id)
        )
        return result.rowcount > 0


# ──────────────────────────────────────────────
# 懒更新默认 LLM 配置解析（跨模块共享工具函数）
# ──────────────────────────────────────────────

async def resolve_active_llm_config(db: AsyncSession, user_id: int) -> UserLLMConfig:
    """
    懒更新策略获取用户有效 LLM 配置：
    1. 优先返回 is_default=True 且 provider+model 均 active 的配置
    2. 若当前默认被禁用，从 active 配置中选 id 最大者升为默认
    3. 若无任何 active 配置，抛出 USER_LLM_CONFIG_NO_DEFAULT
    """
    repo = UserLLMConfigRepository(db)
    default_cfg = await repo.find_default_with_active_check(user_id)
    if default_cfg:
        return default_cfg

    active_cfgs = await repo.find_active_for_user(user_id)
    if not active_cfgs:
        raise BusinessException.exc(StatusCode.USER_LLM_CONFIG_NO_DEFAULT.value)

    # id 已按降序排列，第一个即最新
    latest = active_cfgs[0]
    await repo.clear_defaults(user_id)
    latest.is_default = True
    await repo.update(latest)
    logger.info(
        "Lazily promoted LLM config id=%d as default for user_id=%d",
        latest.id, user_id,
    )
    return latest
