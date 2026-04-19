from __future__ import annotations

from typing import Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.model.entity.llm_provider import LLMProvider
from app.common.model.entity.llm_provider_model import LLMProviderModel
from app.common.model.entity.user_llm_config import UserLLMConfig
from app.common.model.entity.user_rag_config import UserRagConfig
from app.common.model.entity.search_provider import SearchProvider
from app.common.model.entity.user_search_config import UserSearchConfig


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

    async def find_by_user_and_model(self, user_id: int, provider_model_id: int) -> Optional[UserLLMConfig]:
        result = await self._db.execute(
            select(UserLLMConfig).where(
                UserLLMConfig.user_id == user_id,
                UserLLMConfig.provider_model_id == provider_model_id,
            )
        )
        return result.scalar_one_or_none()

    async def find_default(self, user_id: int) -> Optional[UserLLMConfig]:
        result = await self._db.execute(
            select(UserLLMConfig).where(
                UserLLMConfig.user_id == user_id,
                UserLLMConfig.is_default == True,
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        user_id: int,
        provider_model_id: int,
        api_key_encrypted: str,
        alias: str | None,
        is_default: bool,
    ) -> UserLLMConfig:
        config = UserLLMConfig(
            user_id=user_id,
            provider_model_id=provider_model_id,
            api_key=api_key_encrypted,
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
# SearchProvider
# ──────────────────────────────────────────────

class SearchProviderRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def find_by_id(self, provider_id: int) -> Optional[SearchProvider]:
        result = await self._db.execute(
            select(SearchProvider).where(SearchProvider.id == provider_id)
        )
        return result.scalar_one_or_none()

    async def find_by_name(self, name: str) -> Optional[SearchProvider]:
        result = await self._db.execute(
            select(SearchProvider).where(SearchProvider.name == name)
        )
        return result.scalar_one_or_none()

    async def find_all(self) -> list[SearchProvider]:
        result = await self._db.execute(select(SearchProvider).order_by(SearchProvider.id))
        return list(result.scalars().all())

    async def find_active(self) -> list[SearchProvider]:
        result = await self._db.execute(
            select(SearchProvider).where(SearchProvider.is_active == True).order_by(SearchProvider.id)
        )
        return list(result.scalars().all())

    async def create(self, name: str, api_endpoint: str | None, description: str | None, is_active: bool) -> SearchProvider:
        provider = SearchProvider(
            name=name, api_endpoint=api_endpoint, description=description, is_active=is_active
        )
        self._db.add(provider)
        await self._db.flush()
        await self._db.refresh(provider)
        return provider

    async def update(self, provider: SearchProvider) -> None:
        await self._db.flush()

    async def delete_by_id(self, provider_id: int) -> bool:
        result = await self._db.execute(
            delete(SearchProvider).where(SearchProvider.id == provider_id)
        )
        return result.rowcount > 0


# ──────────────────────────────────────────────
# UserSearchConfig
# ──────────────────────────────────────────────

class UserSearchConfigRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def find_by_id(self, config_id: int) -> Optional[UserSearchConfig]:
        result = await self._db.execute(
            select(UserSearchConfig).where(UserSearchConfig.id == config_id)
        )
        return result.scalar_one_or_none()

    async def find_by_id_and_user(self, config_id: int, user_id: int) -> Optional[UserSearchConfig]:
        result = await self._db.execute(
            select(UserSearchConfig).where(
                UserSearchConfig.id == config_id,
                UserSearchConfig.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def find_by_user(self, user_id: int) -> list[UserSearchConfig]:
        result = await self._db.execute(
            select(UserSearchConfig)
            .where(UserSearchConfig.user_id == user_id)
            .order_by(UserSearchConfig.id)
        )
        return list(result.scalars().all())

    async def find_by_user_and_provider(self, user_id: int, provider_id: int) -> Optional[UserSearchConfig]:
        result = await self._db.execute(
            select(UserSearchConfig).where(
                UserSearchConfig.user_id == user_id,
                UserSearchConfig.provider_id == provider_id,
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        user_id: int,
        provider_id: int,
        api_key_encrypted: str,
        alias: str | None,
        is_default: bool,
    ) -> UserSearchConfig:
        config = UserSearchConfig(
            user_id=user_id,
            provider_id=provider_id,
            api_key=api_key_encrypted,
            alias=alias,
            is_default=is_default,
        )
        self._db.add(config)
        await self._db.flush()
        await self._db.refresh(config)
        return config

    async def clear_defaults(self, user_id: int) -> None:
        configs = await self.find_by_user(user_id)
        for cfg in configs:
            cfg.is_default = False
        await self._db.flush()

    async def update(self, config: UserSearchConfig) -> None:
        await self._db.flush()

    async def delete_by_id_and_user(self, config_id: int, user_id: int) -> bool:
        result = await self._db.execute(
            delete(UserSearchConfig).where(
                UserSearchConfig.id == config_id,
                UserSearchConfig.user_id == user_id,
            )
        )
        return result.rowcount > 0
