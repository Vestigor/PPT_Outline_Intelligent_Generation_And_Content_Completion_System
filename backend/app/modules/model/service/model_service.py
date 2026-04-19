from __future__ import annotations

from app.common.exception.code import StatusCode
from app.common.exception.exception import BusinessException
from app.infrastructure.security.security import encrypt_api_key, decrypt_api_key
from app.modules.model.dto.response import (
    AdminLLMModelResponse,
    AdminLLMProviderResponse,
    AdminLLMProviderWithModelsResponse,
    AdminSearchProviderResponse,
    UserLLMConfigResponse,
    UserLLMModelBrowseResponse,
    UserLLMProviderBrowseResponse,
    UserRagConfigResponse,
    UserSearchConfigResponse,
    UserSearchProviderBrowseResponse,
)
from app.modules.model.repository.model_repository import (
    LLMProviderModelRepository,
    LLMProviderRepository,
    SearchProviderRepository,
    UserLLMConfigRepository,
    UserRagConfigRepository,
    UserSearchConfigRepository,
)


class ModelService:
    def __init__(
        self,
        provider_repo: LLMProviderRepository,
        model_repo: LLMProviderModelRepository,
        user_llm_repo: UserLLMConfigRepository,
        rag_repo: UserRagConfigRepository,
        search_provider_repo: SearchProviderRepository,
        user_search_repo: UserSearchConfigRepository,
    ) -> None:
        self._provider_repo = provider_repo
        self._model_repo = model_repo
        self._user_llm_repo = user_llm_repo
        self._rag_repo = rag_repo
        self._search_provider_repo = search_provider_repo
        self._user_search_repo = user_search_repo

    # ══════════════════════════════════════════════
    # 用户：浏览可用提供商 / 搜索服务
    # ══════════════════════════════════════════════

    async def list_available_providers(self, user_id: int) -> list[UserLLMProviderBrowseResponse]:
        """返回所有启用的提供商及其启用的模型"""
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

    async def list_available_search_providers(self) -> list[UserSearchProviderBrowseResponse]:
        """返回所有启用的搜索服务提供商"""
        providers = await self._search_provider_repo.find_active()
        return [
            UserSearchProviderBrowseResponse(
                id=p.id,
                name=p.name,
                description=p.description,
                created_at=p.created_at,
                updated_at=p.updated_at,
            )
            for p in providers
        ]

    # ══════════════════════════════════════════════
    # 用户 LLM 配置管理
    # ══════════════════════════════════════════════

    async def list_user_llm_configs(self, user_id: int) -> list[UserLLMConfigResponse]:
        configs = await self._user_llm_repo.find_by_user(user_id)
        result = []
        for cfg in configs:
            model = await self._model_repo.find_by_id(cfg.provider_model_id)
            provider = await self._provider_repo.find_by_id(model.provider_id) if model else None
            result.append(UserLLMConfigResponse(
                id=cfg.id,
                provider_model_id=cfg.provider_model_id,
                provider_name=provider.name if provider else "已删除",
                model_name=model.model_name if model else "已删除",
                alias=cfg.alias,
                is_default=cfg.is_default,
                is_active=(provider.is_active and model.is_active) if (provider and model) else False,
                created_at=cfg.created_at,
                updated_at=cfg.updated_at,
            ))
        return result

    async def create_user_llm_config(
        self,
        user_id: int,
        provider_model_id: int,
        api_key: str,
        alias: str | None,
        is_default: bool,
    ) -> UserLLMConfigResponse:
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

        if is_default:
            await self._user_llm_repo.clear_defaults(user_id)

        encrypted = encrypt_api_key(api_key)
        cfg = await self._user_llm_repo.create(user_id, provider_model_id, encrypted, alias, is_default)
        return UserLLMConfigResponse(
            id=cfg.id,
            provider_model_id=cfg.provider_model_id,
            provider_name=provider.name,
            model_name=model.model_name,
            alias=cfg.alias,
            is_default=cfg.is_default,
            is_active=provider.is_active and model.is_active,
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
        if not model or not provider or not (provider.is_active and model.is_active):
            raise BusinessException.exc(StatusCode.USER_LLM_CONFIG_NOT_ACTIVE.value)

        if api_key is not None:
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
            provider_name=provider.name,
            model_name=model.model_name,
            alias=cfg.alias,
            is_default=cfg.is_default,
            is_active=True,
            created_at=cfg.created_at,
            updated_at=cfg.updated_at,
        )

    async def delete_user_llm_config(self, user_id: int, config_id: int) -> None:
        cfg = await self._user_llm_repo.find_by_id_and_user(config_id, user_id)
        if not cfg:
            raise BusinessException.exc(StatusCode.USER_LLM_CONFIG_NOT_FOUND.value)
        was_default = cfg.is_default
        await self._user_llm_repo.delete_by_id_and_user(config_id, user_id)
        # 删除默认配置时，将 id 最大的其余配置置为默认
        if was_default:
            remaining = await self._user_llm_repo.find_by_user(user_id)
            if remaining:
                latest = max(remaining, key=lambda c: c.id)
                await self._user_llm_repo.clear_defaults(user_id)
                latest.is_default = True
                await self._user_llm_repo.update(latest)

    async def set_default_llm_config(self, user_id: int, config_id: int) -> None:
        cfg = await self._user_llm_repo.find_by_id_and_user(config_id, user_id)
        if cfg is None:
            raise BusinessException.exc(StatusCode.USER_LLM_CONFIG_NOT_FOUND.value)
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
        if await self._rag_repo.find_by_user(user_id):
            raise BusinessException.exc(StatusCode.USER_RAG_CONFIG_ALREADY_EXIST.value)
        encrypted = encrypt_api_key(api_key)
        cfg = await self._rag_repo.create(user_id, encrypted)
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
    # 用户 搜索配置管理
    # ══════════════════════════════════════════════

    async def list_user_search_configs(self, user_id: int) -> list[UserSearchConfigResponse]:
        configs = await self._user_search_repo.find_by_user(user_id)
        result = []
        for cfg in configs:
            provider = await self._search_provider_repo.find_by_id(cfg.provider_id)
            result.append(UserSearchConfigResponse(
                id=cfg.id,
                provider_id=cfg.provider_id,
                provider_name=provider.name if provider else "已删除",
                alias=cfg.alias,
                is_default=cfg.is_default,
                is_active=provider.is_active if provider else False,
                created_at=cfg.created_at,
                updated_at=cfg.updated_at,
            ))
        return result

    async def create_user_search_config(
        self,
        user_id: int,
        provider_id: int,
        api_key: str,
        alias: str | None,
        is_default: bool,
    ) -> UserSearchConfigResponse:
        provider = await self._search_provider_repo.find_by_id(provider_id)
        if provider is None:
            raise BusinessException.exc(StatusCode.SEARCH_PROVIDER_NOT_FOUND.value)
        if not provider.is_active:
            raise BusinessException.exc(StatusCode.SEARCH_PROVIDER_DISABLED.value)
        if await self._user_search_repo.find_by_user_and_provider(user_id, provider_id):
            raise BusinessException.exc(StatusCode.USER_SEARCH_CONFIG_DUPLICATE.value)

        if is_default:
            await self._user_search_repo.clear_defaults(user_id)

        encrypted = encrypt_api_key(api_key)
        cfg = await self._user_search_repo.create(user_id, provider_id, encrypted, alias, is_default)
        return UserSearchConfigResponse(
            id=cfg.id,
            provider_id=cfg.provider_id,
            provider_name=provider.name,
            alias=cfg.alias,
            is_default=cfg.is_default,
            is_active=provider.is_active,
            created_at=cfg.created_at,
            updated_at=cfg.updated_at,
        )

    async def update_user_search_config(
        self,
        user_id: int,
        config_id: int,
        api_key: str | None,
        alias: str | None,
        is_default: bool | None,
    ) -> UserSearchConfigResponse:
        cfg = await self._user_search_repo.find_by_id_and_user(config_id, user_id)
        if cfg is None:
            raise BusinessException.exc(StatusCode.USER_SEARCH_CONFIG_NOT_FOUND.value)

        # 已停用（服务商被禁用/删除）的配置不可修改
        provider = await self._search_provider_repo.find_by_id(cfg.provider_id)
        if not provider or not provider.is_active:
            raise BusinessException.exc(StatusCode.USER_SEARCH_CONFIG_NOT_ACTIVE.value)

        if api_key is not None:
            cfg.api_key = encrypt_api_key(api_key)
        if alias is not None:
            cfg.alias = alias
        if is_default is True:
            await self._user_search_repo.clear_defaults(user_id)
            cfg.is_default = True
        elif is_default is False:
            cfg.is_default = False
        await self._user_search_repo.update(cfg)

        return UserSearchConfigResponse(
            id=cfg.id,
            provider_id=cfg.provider_id,
            provider_name=provider.name,
            alias=cfg.alias,
            is_default=cfg.is_default,
            is_active=True,
            created_at=cfg.created_at,
            updated_at=cfg.updated_at,
        )

    async def delete_user_search_config(self, user_id: int, config_id: int) -> None:
        cfg = await self._user_search_repo.find_by_id_and_user(config_id, user_id)
        if not cfg:
            raise BusinessException.exc(StatusCode.USER_SEARCH_CONFIG_NOT_FOUND.value)
        was_default = cfg.is_default
        await self._user_search_repo.delete_by_id_and_user(config_id, user_id)
        # 删除默认配置时，将 id 最大（最新）的其余配置置为默认
        if was_default:
            remaining = await self._user_search_repo.find_by_user(user_id)
            if remaining:
                latest = max(remaining, key=lambda c: c.id)
                await self._user_search_repo.clear_defaults(user_id)
                latest.is_default = True
                await self._user_search_repo.update(latest)

    async def set_default_search_config(self, user_id: int, config_id: int) -> None:
        cfg = await self._user_search_repo.find_by_id_and_user(config_id, user_id)
        if cfg is None:
            raise BusinessException.exc(StatusCode.USER_SEARCH_CONFIG_NOT_FOUND.value)
        await self._user_search_repo.clear_defaults(user_id)
        cfg.is_default = True
        await self._user_search_repo.update(cfg)

    # ══════════════════════════════════════════════
    # 管理员：LLM 提供商管理
    # ══════════════════════════════════════════════

    async def admin_list_providers(self) -> list[AdminLLMProviderWithModelsResponse]:
        """返回所有提供商（含各自模型列表、base_url 和 effective_is_active）。"""
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
        if await self._provider_repo.find_by_name(name):
            raise BusinessException.exc(StatusCode.LLM_PROVIDER_DUPLICATE.value)
        provider = await self._provider_repo.create(name, base_url, description, is_active)
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
            provider.is_active = is_active
        await self._provider_repo.update(provider)
        return AdminLLMProviderResponse.model_validate(provider)

    async def admin_delete_provider(self, provider_id: int) -> None:
        if not await self._provider_repo.find_by_id(provider_id):
            raise BusinessException.exc(StatusCode.LLM_PROVIDER_NOT_FOUND.value)
        deleted = await self._provider_repo.delete_by_id(provider_id)
        if not deleted:
            raise BusinessException.exc(StatusCode.LLM_PROVIDER_DELETE_FAILED.value)

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
        provider = await self._provider_repo.find_by_id(provider_id)
        if not provider:
            raise BusinessException.exc(StatusCode.LLM_PROVIDER_NOT_FOUND.value)
        if await self._model_repo.find_by_provider_and_name(provider_id, model_name):
            raise BusinessException.exc(StatusCode.LLM_MODEL_DUPLICATE.value)
        model = await self._model_repo.create(provider_id, model_name, description, is_active)
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

        # 尝试启用模型但服务商已禁用时，提示先解禁服务商
        if is_active is True and not provider.is_active:
            raise BusinessException.exc(StatusCode.LLM_MODEL_ENABLE_BLOCKED_BY_PROVIDER.value)

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
        model = await self._model_repo.find_by_id(model_id)
        if model is None or model.provider_id != provider_id:
            raise BusinessException.exc(StatusCode.LLM_MODEL_NOT_FOUND.value)
        deleted = await self._model_repo.delete_by_id(model_id)
        if not deleted:
            raise BusinessException.exc(StatusCode.LLM_MODEL_DELETE_FAILED.value)

    # ══════════════════════════════════════════════
    # 管理员：搜索服务提供商管理
    # ══════════════════════════════════════════════

    async def admin_list_search_providers(self) -> list[AdminSearchProviderResponse]:
        providers = await self._search_provider_repo.find_all()
        return [AdminSearchProviderResponse.model_validate(p) for p in providers]

    async def admin_create_search_provider(
        self, name: str, api_endpoint: str | None, description: str | None, is_active: bool
    ) -> AdminSearchProviderResponse:
        if await self._search_provider_repo.find_by_name(name):
            raise BusinessException.exc(StatusCode.SEARCH_PROVIDER_DUPLICATE.value)
        provider = await self._search_provider_repo.create(name, api_endpoint, description, is_active)
        return AdminSearchProviderResponse.model_validate(provider)

    async def admin_update_search_provider(
        self,
        provider_id: int,
        name: str | None,
        api_endpoint: str | None,
        description: str | None,
        is_active: bool | None,
    ) -> AdminSearchProviderResponse:
        provider = await self._search_provider_repo.find_by_id(provider_id)
        if provider is None:
            raise BusinessException.exc(StatusCode.SEARCH_PROVIDER_NOT_FOUND.value)
        if name is not None:
            dup = await self._search_provider_repo.find_by_name(name)
            if dup and dup.id != provider_id:
                raise BusinessException.exc(StatusCode.SEARCH_PROVIDER_DUPLICATE.value)
            provider.name = name
        if api_endpoint is not None:
            provider.api_endpoint = api_endpoint
        if description is not None:
            provider.description = description
        if is_active is not None:
            provider.is_active = is_active
        await self._search_provider_repo.update(provider)
        return AdminSearchProviderResponse.model_validate(provider)

    async def admin_delete_search_provider(self, provider_id: int) -> None:
        if not await self._search_provider_repo.find_by_id(provider_id):
            raise BusinessException.exc(StatusCode.SEARCH_PROVIDER_NOT_FOUND.value)
        deleted = await self._search_provider_repo.delete_by_id(provider_id)
        if not deleted:
            raise BusinessException.exc(StatusCode.SEARCH_PROVIDER_DELETE_FAILED.value)

    # ══════════════════════════════════════════════
    # 供其他模块调用：获取解密后的 API Key
    # ══════════════════════════════════════════════

    async def get_default_llm_api_key(self, user_id: int) -> tuple[str, str, str]:
        """返回 (api_key_plain, base_url, model_name)，供 LLM 调用使用。"""
        cfg = await self._user_llm_repo.find_default(user_id)
        if cfg is None:
            raise BusinessException.exc(StatusCode.USER_LLM_CONFIG_NO_DEFAULT.value)
        model = await self._model_repo.find_by_id(cfg.provider_model_id)
        if model is None:
            raise BusinessException.exc(StatusCode.LLM_MODEL_NOT_FOUND.value)
        provider = await self._provider_repo.find_by_id(model.provider_id)
        if provider is None:
            raise BusinessException.exc(StatusCode.LLM_PROVIDER_NOT_FOUND.value)
        return decrypt_api_key(cfg.api_key), provider.base_url, model.model_name

    async def get_rag_api_key(self, user_id: int) -> str:
        """返回解密后的 RAG API Key，供 Embedding 调用使用。"""
        cfg = await self._rag_repo.find_by_user(user_id)
        if cfg is None:
            raise BusinessException.exc(StatusCode.USER_RAG_CONFIG_NOT_FOUND.value)
        return decrypt_api_key(cfg.api_key)
