from __future__ import annotations

import asyncio

from app.common.exception.code import StatusCode
from app.common.exception.exception import BusinessException
from app.infrastructure.log.logging_config import get_logger
from app.infrastructure.security.security import encrypt_api_key, decrypt_api_key
from app.modules.model.dto.response import (
    AdminLLMModelResponse,
    AdminLLMProviderResponse,
    AdminLLMProviderWithModelsResponse,
    UserDefaultsResponse,
    UserLLMConfigResponse,
    UserLLMModelBrowseResponse,
    UserLLMProviderBrowseResponse,
    UserRagConfigResponse,
    UserSearchConfigResponse,
)
from app.modules.model.repository.model_repository import (
    LLMProviderModelRepository,
    LLMProviderRepository,
    UserLLMConfigRepository,
    UserRagConfigRepository,
    UserSearchConfigRepository,
    resolve_active_llm_config,
)

logger = get_logger(__name__)


class ModelService:
    def __init__(
        self,
        provider_repo: LLMProviderRepository,
        model_repo: LLMProviderModelRepository,
        user_llm_repo: UserLLMConfigRepository,
        rag_repo: UserRagConfigRepository,
        user_search_repo: UserSearchConfigRepository,
    ) -> None:
        self._provider_repo = provider_repo
        self._model_repo = model_repo
        self._user_llm_repo = user_llm_repo
        self._rag_repo = rag_repo
        self._user_search_repo = user_search_repo

    # ══════════════════════════════════════════════
    # 用户：浏览可用提供商
    # ══════════════════════════════════════════════

    async def list_available_providers(self, user_id: int) -> list[UserLLMProviderBrowseResponse]:
        """返回所有启用的提供商及其启用的模型（已配置过的模型不再展示）。"""
        providers = await self._provider_repo.find_active()
        user_configs = await self._user_llm_repo.find_by_user(user_id)
        configured_model_ids = {c.provider_model_id for c in user_configs}

        result = []
        for p in providers:
            models = await self._model_repo.find_active_by_provider(p.id)
            model_resps = [
                UserLLMModelBrowseResponse(
                    id=m.id,
                    model_name=m.model_name,
                    description=m.description,
                    created_at=m.created_at,
                    updated_at=m.updated_at,
                )
                for m in models
                if m.id not in configured_model_ids
            ]
            result.append(
                UserLLMProviderBrowseResponse(
                    id=p.id,
                    name=p.name,
                    description=p.description,
                    models=model_resps,
                    created_at=p.created_at,
                    updated_at=p.updated_at,
                )
            )
        return result

    # ══════════════════════════════════════════════
    # 用户 LLM 配置管理
    # ══════════════════════════════════════════════

    async def list_user_llm_configs(self, user_id: int) -> list[UserLLMConfigResponse]:
        rows = await self._user_llm_repo.find_by_user_with_active_status(user_id)
        return [
            UserLLMConfigResponse(
                id=cfg.id,
                provider_model_id=cfg.provider_model_id,
                provider_name=cfg.provider_name,
                model_name=cfg.model_name,
                alias=cfg.alias,
                is_default=cfg.is_default,
                is_active=is_active,
                created_at=cfg.created_at,
                updated_at=cfg.updated_at,
            )
            for cfg, is_active in rows
        ]

    async def create_user_llm_config(
        self,
        user_id: int,
        provider_model_id: int,
        api_key: str,
        alias: str | None,
        is_default: bool,
    ) -> UserLLMConfigResponse:
        logger.info("Creating LLM config: user_id=%d model_id=%d", user_id, provider_model_id)
        model = await self._model_repo.find_by_id(provider_model_id)
        if model is None:
            raise BusinessException.exc(StatusCode.LLM_MODEL_NOT_FOUND.value)
        if not model.is_active:
            raise BusinessException.exc(StatusCode.LLM_MODEL_DISABLED.value)
        provider = await self._provider_repo.find_by_id(model.provider_id)
        if provider is None or not provider.is_active:
            raise BusinessException.exc(StatusCode.LLM_PROVIDER_DISABLED.value)
        if await self._user_llm_repo.find_by_user_and_model(user_id, provider_model_id):
            raise BusinessException.exc(StatusCode.USER_LLM_CONFIG_DUPLICATE.value)

        # 验证 API Key 有效性（真实调用）
        await self._validate_llm_api_key(api_key, provider.base_url, model.model_name)

        if is_default:
            await self._user_llm_repo.clear_defaults(user_id)

        encrypted = encrypt_api_key(api_key)
        cfg = await self._user_llm_repo.create(
            user_id=user_id,
            provider_model_id=provider_model_id,
            api_key_encrypted=encrypted,
            provider_name=provider.name,
            model_name=model.model_name,
            base_url=provider.base_url,
            alias=alias,
            is_default=is_default,
        )
        logger.info("LLM config created: config_id=%d user_id=%d", cfg.id, user_id)
        return UserLLMConfigResponse(
            id=cfg.id,
            provider_model_id=cfg.provider_model_id,
            provider_name=cfg.provider_name,
            model_name=cfg.model_name,
            alias=cfg.alias,
            is_default=cfg.is_default,
            is_active=True,
            created_at=cfg.created_at,
            updated_at=cfg.updated_at,
        )

    async def update_user_llm_config(
        self,
        user_id: int,
        config_id: int,
        api_key: str | None,
        alias: str | None,
        is_default: bool | None,
    ) -> UserLLMConfigResponse:
        cfg = await self._user_llm_repo.find_by_id_and_user(config_id, user_id)
        if cfg is None:
            raise BusinessException.exc(StatusCode.USER_LLM_CONFIG_NOT_FOUND.value)

        # 已停用的配置不可修改
        model = await self._model_repo.find_by_id(cfg.provider_model_id)
        provider = await self._provider_repo.find_by_id(model.provider_id) if model else None
        is_active = bool(model and provider and provider.is_active and model.is_active)
        if not is_active:
            raise BusinessException.exc(StatusCode.USER_LLM_CONFIG_NOT_ACTIVE.value)

        if api_key is not None:
            await self._validate_llm_api_key(api_key, cfg.base_url, cfg.model_name)
            cfg.api_key = encrypt_api_key(api_key)
        if alias is not None:
            cfg.alias = alias
        if is_default is True:
            await self._user_llm_repo.clear_defaults(user_id)
            cfg.is_default = True
        elif is_default is False:
            cfg.is_default = False
        await self._user_llm_repo.update(cfg)

        return UserLLMConfigResponse(
            id=cfg.id,
            provider_model_id=cfg.provider_model_id,
            provider_name=cfg.provider_name,
            model_name=cfg.model_name,
            alias=cfg.alias,
            is_default=cfg.is_default,
            is_active=True,
            created_at=cfg.created_at,
            updated_at=cfg.updated_at,
        )

    async def delete_user_llm_config(self, user_id: int, config_id: int) -> None:
        logger.info("Deleting LLM config: config_id=%d user_id=%d", config_id, user_id)
        cfg = await self._user_llm_repo.find_by_id_and_user(config_id, user_id)
        if not cfg:
            raise BusinessException.exc(StatusCode.USER_LLM_CONFIG_NOT_FOUND.value)
        was_default = cfg.is_default
        await self._user_llm_repo.delete_by_id_and_user(config_id, user_id)
        logger.info("LLM config deleted: config_id=%d was_default=%s", config_id, was_default)
        # 删除默认配置时，将最新的其余有效配置升为默认（懒更新将在下次实际使用时触发）

    async def set_default_llm_config(self, user_id: int, config_id: int) -> None:
        cfg = await self._user_llm_repo.find_by_id_and_user(config_id, user_id)
        if cfg is None:
            raise BusinessException.exc(StatusCode.USER_LLM_CONFIG_NOT_FOUND.value)
        # 禁止将已停用配置设为默认
        model = await self._model_repo.find_by_id(cfg.provider_model_id)
        provider = await self._provider_repo.find_by_id(model.provider_id) if model else None
        if not (model and provider and provider.is_active and model.is_active):
            raise BusinessException.exc(StatusCode.USER_LLM_CONFIG_NOT_ACTIVE.value)
        await self._user_llm_repo.clear_defaults(user_id)
        cfg.is_default = True
        await self._user_llm_repo.update(cfg)

    # ══════════════════════════════════════════════
    # 用户 RAG 配置管理
    # ══════════════════════════════════════════════

    async def get_user_rag_config(self, user_id: int) -> UserRagConfigResponse | None:
        cfg = await self._rag_repo.find_by_user(user_id)
        if cfg is None:
            return None
        return UserRagConfigResponse(
            id=cfg.id,
            base_url=cfg.base_url,
            model=cfg.model,
            created_at=cfg.created_at,
            updated_at=cfg.updated_at,
        )

    async def create_user_rag_config(self, user_id: int, api_key: str) -> UserRagConfigResponse:
        logger.info("Creating RAG config: user_id=%d", user_id)
        if await self._rag_repo.find_by_user(user_id):
            raise BusinessException.exc(StatusCode.USER_RAG_CONFIG_ALREADY_EXIST.value)
        await self._validate_rag_api_key(api_key)
        encrypted = encrypt_api_key(api_key)
        cfg = await self._rag_repo.create(user_id, encrypted)
        logger.info("RAG config created: config_id=%d user_id=%d", cfg.id, user_id)
        return UserRagConfigResponse(
            id=cfg.id,
            base_url=cfg.base_url,
            model=cfg.model,
            created_at=cfg.created_at,
            updated_at=cfg.updated_at,
        )

    async def update_user_rag_config(self, user_id: int, api_key: str) -> UserRagConfigResponse:
        cfg = await self._rag_repo.find_by_user(user_id)
        if cfg is None:
            raise BusinessException.exc(StatusCode.USER_RAG_CONFIG_NOT_FOUND.value)
        await self._validate_rag_api_key(api_key)
        cfg.api_key = encrypt_api_key(api_key)
        await self._rag_repo.update(cfg)
        return UserRagConfigResponse(
            id=cfg.id,
            base_url=cfg.base_url,
            model=cfg.model,
            created_at=cfg.created_at,
            updated_at=cfg.updated_at,
        )

    async def delete_user_rag_config(self, user_id: int) -> None:
        if not await self._rag_repo.find_by_user(user_id):
            raise BusinessException.exc(StatusCode.USER_RAG_CONFIG_NOT_FOUND.value)
        await self._rag_repo.delete_by_user(user_id)

    # ══════════════════════════════════════════════
    # 用户搜索配置管理（固定 Tavily，每用户一条）
    # ══════════════════════════════════════════════

    async def get_user_search_config(self, user_id: int) -> UserSearchConfigResponse | None:
        cfg = await self._user_search_repo.find_by_user(user_id)
        if cfg is None:
            return None
        return UserSearchConfigResponse(
            id=cfg.id,
            provider=cfg.provider,
            created_at=cfg.created_at,
            updated_at=cfg.updated_at,
        )

    async def create_user_search_config(self, user_id: int, api_key: str) -> UserSearchConfigResponse:
        logger.info("Creating search config: user_id=%d", user_id)
        if await self._user_search_repo.find_by_user(user_id):
            raise BusinessException.exc(StatusCode.USER_SEARCH_CONFIG_ALREADY_EXIST.value)
        await self._validate_search_api_key(api_key)
        encrypted = encrypt_api_key(api_key)
        cfg = await self._user_search_repo.create(user_id, encrypted)
        logger.info("Search config created: config_id=%d user_id=%d", cfg.id, user_id)
        return UserSearchConfigResponse(
            id=cfg.id,
            provider=cfg.provider,
            created_at=cfg.created_at,
            updated_at=cfg.updated_at,
        )

    async def update_user_search_config(self, user_id: int, api_key: str) -> UserSearchConfigResponse:
        cfg = await self._user_search_repo.find_by_user(user_id)
        if cfg is None:
            raise BusinessException.exc(StatusCode.USER_SEARCH_CONFIG_NOT_FOUND.value)
        await self._validate_search_api_key(api_key)
        cfg.api_key = encrypt_api_key(api_key)
        await self._user_search_repo.update(cfg)
        return UserSearchConfigResponse(
            id=cfg.id,
            provider=cfg.provider,
            created_at=cfg.created_at,
            updated_at=cfg.updated_at,
        )

    async def delete_user_search_config(self, user_id: int) -> None:
        if not await self._user_search_repo.find_by_user(user_id):
            raise BusinessException.exc(StatusCode.USER_SEARCH_CONFIG_NOT_FOUND.value)
        await self._user_search_repo.delete_by_user(user_id)

    # ══════════════════════════════════════════════
    # 管理员：LLM 提供商管理
    # ══════════════════════════════════════════════

    async def admin_list_providers(self) -> list[AdminLLMProviderWithModelsResponse]:
        providers = await self._provider_repo.find_all()
        result = []
        for p in providers:
            models = await self._model_repo.find_by_provider(p.id)
            model_resps = [
                AdminLLMModelResponse(
                    id=m.id,
                    provider_id=m.provider_id,
                    model_name=m.model_name,
                    description=m.description,
                    is_active=m.is_active,
                    effective_is_active=p.is_active and m.is_active,
                    created_at=m.created_at,
                    updated_at=m.updated_at,
                )
                for m in models
            ]
            result.append(
                AdminLLMProviderWithModelsResponse(
                    id=p.id,
                    name=p.name,
                    base_url=p.base_url,
                    description=p.description,
                    is_active=p.is_active,
                    models=model_resps,
                    created_at=p.created_at,
                    updated_at=p.updated_at,
                )
            )
        return result

    async def admin_get_provider(self, provider_id: int) -> AdminLLMProviderResponse:
        provider = await self._provider_repo.find_by_id(provider_id)
        if provider is None:
            raise BusinessException.exc(StatusCode.LLM_PROVIDER_NOT_FOUND.value)
        return AdminLLMProviderResponse.model_validate(provider)

    async def admin_create_provider(
        self, name: str, base_url: str, description: str | None, is_active: bool
    ) -> AdminLLMProviderResponse:
        logger.info("Admin creating LLM provider: name=%s", name)
        if await self._provider_repo.find_by_name(name):
            raise BusinessException.exc(StatusCode.LLM_PROVIDER_DUPLICATE.value)
        provider = await self._provider_repo.create(name, base_url, description, is_active)
        logger.info("LLM provider created: id=%d name=%s", provider.id, name)
        return AdminLLMProviderResponse.model_validate(provider)

    async def admin_update_provider(
        self,
        provider_id: int,
        name: str | None,
        base_url: str | None,
        description: str | None,
        is_active: bool | None,
    ) -> AdminLLMProviderResponse:
        provider = await self._provider_repo.find_by_id(provider_id)
        if provider is None:
            raise BusinessException.exc(StatusCode.LLM_PROVIDER_NOT_FOUND.value)
        if name is not None:
            existing = await self._provider_repo.find_by_name(name)
            if existing and existing.id != provider_id:
                raise BusinessException.exc(StatusCode.LLM_PROVIDER_DUPLICATE.value)
            provider.name = name
        if base_url is not None:
            provider.base_url = base_url
        if description is not None:
            provider.description = description
        if is_active is not None:
            if not is_active:
                # 禁用服务商时，清除该服务商下所有用户 LLM 配置的默认标记
                models = await self._model_repo.find_by_provider(provider_id)
                model_ids = [m.id for m in models]
                if model_ids:
                    await self._clear_defaults_for_models(model_ids)
            provider.is_active = is_active
        await self._provider_repo.update(provider)
        return AdminLLMProviderResponse.model_validate(provider)

    async def admin_delete_provider(self, provider_id: int) -> None:
        logger.info("Admin deleting LLM provider: provider_id=%d", provider_id)
        if not await self._provider_repo.find_by_id(provider_id):
            raise BusinessException.exc(StatusCode.LLM_PROVIDER_NOT_FOUND.value)
        deleted = await self._provider_repo.delete_by_id(provider_id)
        if not deleted:
            raise BusinessException.exc(StatusCode.LLM_PROVIDER_DELETE_FAILED.value)
        logger.info("LLM provider deleted: provider_id=%d", provider_id)

    # ══════════════════════════════════════════════
    # 管理员：LLM 模型管理
    # ══════════════════════════════════════════════

    async def admin_list_models(self, provider_id: int) -> list[AdminLLMModelResponse]:
        provider = await self._provider_repo.find_by_id(provider_id)
        if not provider:
            raise BusinessException.exc(StatusCode.LLM_PROVIDER_NOT_FOUND.value)
        models = await self._model_repo.find_by_provider(provider_id)
        return [
            AdminLLMModelResponse(
                id=m.id,
                provider_id=m.provider_id,
                model_name=m.model_name,
                description=m.description,
                is_active=m.is_active,
                effective_is_active=provider.is_active and m.is_active,
                created_at=m.created_at,
                updated_at=m.updated_at,
            )
            for m in models
        ]

    async def admin_create_model(
        self, provider_id: int, model_name: str, description: str | None, is_active: bool
    ) -> AdminLLMModelResponse:
        logger.info("Admin creating model: provider_id=%d model_name=%s", provider_id, model_name)
        provider = await self._provider_repo.find_by_id(provider_id)
        if not provider:
            raise BusinessException.exc(StatusCode.LLM_PROVIDER_NOT_FOUND.value)
        if await self._model_repo.find_by_provider_and_name(provider_id, model_name):
            raise BusinessException.exc(StatusCode.LLM_MODEL_DUPLICATE.value)
        model = await self._model_repo.create(provider_id, model_name, description, is_active)
        logger.info("LLM model created: model_id=%d name=%s", model.id, model_name)
        return AdminLLMModelResponse(
            id=model.id,
            provider_id=model.provider_id,
            model_name=model.model_name,
            description=model.description,
            is_active=model.is_active,
            effective_is_active=provider.is_active and model.is_active,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def admin_update_model(
        self,
        provider_id: int,
        model_id: int,
        model_name: str | None,
        description: str | None,
        is_active: bool | None,
    ) -> AdminLLMModelResponse:
        model = await self._model_repo.find_by_id(model_id)
        if model is None or model.provider_id != provider_id:
            raise BusinessException.exc(StatusCode.LLM_MODEL_NOT_FOUND.value)
        provider = await self._provider_repo.find_by_id(provider_id)
        if not provider:
            raise BusinessException.exc(StatusCode.LLM_PROVIDER_NOT_FOUND.value)

        if is_active is True and not provider.is_active:
            raise BusinessException.exc(StatusCode.LLM_MODEL_ENABLE_BLOCKED_BY_PROVIDER.value)

        if is_active is False:
            # 禁用模型时清除该模型的所有用户默认标记
            await self._clear_defaults_for_models([model_id])

        if model_name is not None:
            dup = await self._model_repo.find_by_provider_and_name(provider_id, model_name)
            if dup and dup.id != model_id:
                raise BusinessException.exc(StatusCode.LLM_MODEL_DUPLICATE.value)
            model.model_name = model_name
        if description is not None:
            model.description = description
        if is_active is not None:
            model.is_active = is_active
        await self._model_repo.update(model)
        await self._model_repo._db.refresh(model)
        return AdminLLMModelResponse(
            id=model.id,
            provider_id=model.provider_id,
            model_name=model.model_name,
            description=model.description,
            is_active=model.is_active,
            effective_is_active=provider.is_active and model.is_active,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def admin_delete_model(self, provider_id: int, model_id: int) -> None:
        logger.info("Admin deleting model: model_id=%d provider_id=%d", model_id, provider_id)
        model = await self._model_repo.find_by_id(model_id)
        if model is None or model.provider_id != provider_id:
            raise BusinessException.exc(StatusCode.LLM_MODEL_NOT_FOUND.value)
        deleted = await self._model_repo.delete_by_id(model_id)
        if not deleted:
            raise BusinessException.exc(StatusCode.LLM_MODEL_DELETE_FAILED.value)
        logger.info("LLM model deleted: model_id=%d", model_id)

    # ══════════════════════════════════════════════
    # 供其他模块调用：获取解密后的 API Key
    # ══════════════════════════════════════════════

    async def get_default_llm_api_key(self, user_id: int) -> tuple[str, str, str]:
        """返回 (api_key_plain, base_url, model_name)，供 LLM 调用使用（懒更新默认）。"""
        cfg = await resolve_active_llm_config(self._user_llm_repo._db, user_id)
        return decrypt_api_key(cfg.api_key), cfg.base_url, cfg.model_name

    async def get_rag_api_key(self, user_id: int) -> str:
        """返回解密后的 RAG API Key，供 Embedding 调用使用。"""
        cfg = await self._rag_repo.find_by_user(user_id)
        if cfg is None:
            raise BusinessException.exc(StatusCode.USER_RAG_CONFIG_NOT_FOUND.value)
        return decrypt_api_key(cfg.api_key)

    async def get_user_defaults(self, user_id: int) -> UserDefaultsResponse:
        """返回用户当前默认 LLM 配置和搜索配置摘要，供前端在创建会话前展示。"""
        llm_resp: UserLLMConfigResponse | None = None
        try:
            cfg = await resolve_active_llm_config(self._user_llm_repo._db, user_id)
            llm_resp = UserLLMConfigResponse(
                id=cfg.id,
                provider_model_id=cfg.provider_model_id,
                provider_name=cfg.provider_name,
                model_name=cfg.model_name,
                alias=cfg.alias,
                is_default=cfg.is_default,
                is_active=True,
                created_at=cfg.created_at,
                updated_at=cfg.updated_at,
            )
        except BusinessException:
            pass

        search_resp: UserSearchConfigResponse | None = await self.get_user_search_config(user_id)

        return UserDefaultsResponse(
            default_llm_config=llm_resp,
            search_config=search_resp,
            rag_enabled=False,
            deep_search_enabled=False,
        )

    # ══════════════════════════════════════════════
    # 私有工具
    # ══════════════════════════════════════════════

    async def _clear_defaults_for_models(self, model_ids: list[int]) -> None:
        """
        清除指定模型 ID 列表对应的所有用户 LLM 配置的默认标记。
        admin 禁用模型或服务商时调用，使懒更新策略在下次实际使用时生效。
        """
        from sqlalchemy import select, update
        from app.common.model.entity.user_llm_config import UserLLMConfig
        db = self._user_llm_repo._db
        await db.execute(
            update(UserLLMConfig)
            .where(
                UserLLMConfig.provider_model_id.in_(model_ids),
                UserLLMConfig.is_default == True,
            )
            .values(is_default=False)
        )
        await db.flush()
        logger.info("Cleared defaults for configs with model_ids=%s", model_ids)

    async def _validate_llm_api_key(self, api_key: str, base_url: str, model_name: str) -> None:
        """发送最小化请求验证 LLM API Key 有效性。"""
        from app.common.ai.llm_client import LLMClient
        logger.debug("Validating LLM API key: base_url=%s model=%s", base_url, model_name)
        client = LLMClient(api_key=api_key, base_url=base_url, model=model_name)
        try:
            await client.chat([{"role": "user", "content": "hi"}], max_tokens=1)
        except Exception as e:
            logger.warning("LLM API key validation failed: %s", e)
            raise BusinessException.exc(StatusCode.LLM_API_KEY_INVALID.value)

    async def _validate_rag_api_key(self, api_key: str) -> None:
        """调用 DashScope embedding 验证 RAG API Key 有效性。"""
        from http import HTTPStatus
        logger.debug("Validating RAG (DashScope) API key")
        try:
            from dashscope import TextEmbedding
            loop = asyncio.get_event_loop()
            resp = await loop.run_in_executor(
                None,
                lambda: TextEmbedding.call(
                    model=TextEmbedding.Models.text_embedding_v3,
                    input="test",
                    api_key=api_key,
                ),
            )
            if resp.status_code != HTTPStatus.OK:
                raise ValueError(f"DashScope returned status {resp.status_code}: {resp.message}")
        except BusinessException:
            raise
        except Exception as e:
            logger.warning("RAG API key validation failed: %s", e)
            raise BusinessException.exc(StatusCode.RAG_API_KEY_INVALID.value)

    async def _validate_search_api_key(self, api_key: str) -> None:
        """调用 Tavily 验证 Search API Key 有效性。"""
        logger.debug("Validating Tavily search API key")
        try:
            from tavily import TavilyClient
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: TavilyClient(api_key=api_key).search("test", max_results=1),
            )
        except BusinessException:
            raise
        except Exception as e:
            logger.warning("Search API key validation failed: %s", e)
            raise BusinessException.exc(StatusCode.SEARCH_API_KEY_INVALID.value)
