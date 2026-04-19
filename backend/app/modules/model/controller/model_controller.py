from __future__ import annotations

from fastapi import APIRouter

from app.dependencies import CurrentUser, ModelServiceDepend
from app.common.result.result import Result
from app.common.exception.code import StatusCode
from app.common.exception.exception import BusinessException
from app.modules.model.dto.request import (
    CreateLLMProviderRequest,
    UpdateLLMProviderRequest,
    CreateLLMProviderModelRequest,
    UpdateLLMProviderModelRequest,
    CreateSearchProviderRequest,
    UpdateSearchProviderRequest,
    CreateUserLLMConfigRequest,
    UpdateUserLLMConfigRequest,
    CreateUserRagConfigRequest,
    UpdateUserRagConfigRequest,
    CreateUserSearchConfigRequest,
    UpdateUserSearchConfigRequest,
)
from app.modules.model.dto.response import (
    AdminLLMModelResponse,
    AdminLLMProviderResponse,
    AdminLLMProviderWithModelsResponse,
    AdminSearchProviderResponse,
    UserLLMConfigResponse,
    UserLLMProviderBrowseResponse,
    UserRagConfigResponse,
    UserSearchConfigResponse,
    UserSearchProviderBrowseResponse,
)

router = APIRouter(prefix="/model", tags=["模型管理"])


# ══════════════════════════════════════════════
# 用户浏览可用模型
# ══════════════════════════════════════════════

@router.get(
    "/providers",
    response_model=Result[list[UserLLMProviderBrowseResponse]],
    summary="获取可用的 LLM 提供商及模型列表",
    description="展示所有启用的提供商和模型，供用户选择添加配置。不含 base_url。",
)
async def list_available_providers(
    current_user: CurrentUser,
    svc: ModelServiceDepend,
) -> Result[list[UserLLMProviderBrowseResponse]]:
    return Result.success(await svc.list_available_providers(current_user.id))


@router.get(
    "/search-providers",
    response_model=Result[list[UserSearchProviderBrowseResponse]],
    summary="获取可用的搜索服务提供商列表",
    description="不含 api_endpoint。",
)
async def list_available_search_providers(
    current_user: CurrentUser,
    svc: ModelServiceDepend,
) -> Result[list[UserSearchProviderBrowseResponse]]:
    return Result.success(await svc.list_available_search_providers())


# ══════════════════════════════════════════════
# 用户 LLM 配置管理
# ══════════════════════════════════════════════

@router.get(
    "/configs/llm",
    response_model=Result[list[UserLLMConfigResponse]],
    summary="获取用户的 LLM 配置列表",
    description="包含已停用（服务商或模型被禁用）的配置，is_active=false 时前端应展示为不可修改。",
)
async def list_user_llm_configs(
    current_user: CurrentUser,
    svc: ModelServiceDepend,
) -> Result[list[UserLLMConfigResponse]]:
    return Result.success(await svc.list_user_llm_configs(current_user.id))


@router.post(
    "/configs/llm",
    response_model=Result[UserLLMConfigResponse],
    summary="添加 LLM 配置",
    description="为选定的模型填写 API Key，已配置的模型不可重复添加。",
)
async def create_user_llm_config(
    body: CreateUserLLMConfigRequest,
    current_user: CurrentUser,
    svc: ModelServiceDepend,
) -> Result[UserLLMConfigResponse]:
    result = await svc.create_user_llm_config(
        current_user.id, body.provider_model_id, body.api_key, body.alias, body.is_default
    )
    return Result.success(result)


@router.put(
    "/configs/llm/{config_id}",
    response_model=Result[UserLLMConfigResponse],
    summary="修改 LLM 配置",
    description="已停用的配置不可修改，可删除。",
)
async def update_user_llm_config(
    config_id: int,
    body: UpdateUserLLMConfigRequest,
    current_user: CurrentUser,
    svc: ModelServiceDepend,
) -> Result[UserLLMConfigResponse]:
    result = await svc.update_user_llm_config(
        current_user.id, config_id, body.api_key, body.alias, body.is_default
    )
    return Result.success(result)


@router.delete(
    "/configs/llm/{config_id}",
    response_model=Result[None],
    summary="删除 LLM 配置",
    description="删除默认配置时，最新的其余配置将自动升为默认。",
)
async def delete_user_llm_config(
    config_id: int,
    current_user: CurrentUser,
    svc: ModelServiceDepend,
) -> Result[None]:
    await svc.delete_user_llm_config(current_user.id, config_id)
    return Result.success()


@router.put(
    "/configs/llm/{config_id}/default",
    response_model=Result[None],
    summary="设置默认 LLM 配置",
)
async def set_default_llm_config(
    config_id: int,
    current_user: CurrentUser,
    svc: ModelServiceDepend,
) -> Result[None]:
    await svc.set_default_llm_config(current_user.id, config_id)
    return Result.success()


# ══════════════════════════════════════════════
# 用户 RAG（Embedding）配置管理
# ══════════════════════════════════════════════

@router.get(
    "/configs/rag",
    response_model=Result[UserRagConfigResponse | None],
    summary="获取 RAG（阿里云 Embedding）配置",
)
async def get_user_rag_config(
    current_user: CurrentUser,
    svc: ModelServiceDepend,
) -> Result[UserRagConfigResponse | None]:
    return Result.success(await svc.get_user_rag_config(current_user.id))


@router.post(
    "/configs/rag",
    response_model=Result[UserRagConfigResponse],
    summary="添加 RAG 配置（阿里云 DashScope API Key）",
)
async def create_user_rag_config(
    body: CreateUserRagConfigRequest,
    current_user: CurrentUser,
    svc: ModelServiceDepend,
) -> Result[UserRagConfigResponse]:
    return Result.success(await svc.create_user_rag_config(current_user.id, body.api_key))


@router.put(
    "/configs/rag",
    response_model=Result[UserRagConfigResponse],
    summary="修改 RAG 配置",
)
async def update_user_rag_config(
    body: UpdateUserRagConfigRequest,
    current_user: CurrentUser,
    svc: ModelServiceDepend,
) -> Result[UserRagConfigResponse]:
    return Result.success(await svc.update_user_rag_config(current_user.id, body.api_key))


@router.delete(
    "/configs/rag",
    response_model=Result[None],
    summary="删除 RAG 配置",
)
async def delete_user_rag_config(
    current_user: CurrentUser,
    svc: ModelServiceDepend,
) -> Result[None]:
    await svc.delete_user_rag_config(current_user.id)
    return Result.success()


# ══════════════════════════════════════════════
# 用户搜索配置管理
# ══════════════════════════════════════════════

@router.get(
    "/configs/search",
    response_model=Result[list[UserSearchConfigResponse]],
    summary="获取用户的搜索服务配置列表",
    description="包含已停用（服务商被禁用）的配置，is_active=false 时前端应展示为不可修改。",
)
async def list_user_search_configs(
    current_user: CurrentUser,
    svc: ModelServiceDepend,
) -> Result[list[UserSearchConfigResponse]]:
    return Result.success(await svc.list_user_search_configs(current_user.id))


@router.post(
    "/configs/search",
    response_model=Result[UserSearchConfigResponse],
    summary="添加搜索服务配置",
)
async def create_user_search_config(
    body: CreateUserSearchConfigRequest,
    current_user: CurrentUser,
    svc: ModelServiceDepend,
) -> Result[UserSearchConfigResponse]:
    result = await svc.create_user_search_config(
        current_user.id, body.provider_id, body.api_key, body.alias, body.is_default
    )
    return Result.success(result)


@router.put(
    "/configs/search/{config_id}",
    response_model=Result[UserSearchConfigResponse],
    summary="修改搜索服务配置",
    description="已停用的配置不可修改，可删除。",
)
async def update_user_search_config(
    config_id: int,
    body: UpdateUserSearchConfigRequest,
    current_user: CurrentUser,
    svc: ModelServiceDepend,
) -> Result[UserSearchConfigResponse]:
    result = await svc.update_user_search_config(
        current_user.id, config_id, body.api_key, body.alias, body.is_default
    )
    return Result.success(result)


@router.delete(
    "/configs/search/{config_id}",
    response_model=Result[None],
    summary="删除搜索服务配置",
    description="删除默认配置时，最新的其余配置将自动升为默认。",
)
async def delete_user_search_config(
    config_id: int,
    current_user: CurrentUser,
    svc: ModelServiceDepend,
) -> Result[None]:
    await svc.delete_user_search_config(current_user.id, config_id)
    return Result.success()


@router.put(
    "/configs/search/{config_id}/default",
    response_model=Result[None],
    summary="设置默认搜索服务配置",
)
async def set_default_search_config(
    config_id: int,
    current_user: CurrentUser,
    svc: ModelServiceDepend,
) -> Result[None]:
    await svc.set_default_search_config(current_user.id, config_id)
    return Result.success()


# ══════════════════════════════════════════════
# 身份校验
# ══════════════════════════════════════════════

def _require_admin(current_user: CurrentUser) -> None:
    if current_user.role != "admin":
        raise BusinessException.exc(StatusCode.DONT_HAVE_PERMISSION.value)


# ══════════════════════════════════════════════
# 管理员 LLM 提供商管理
# ══════════════════════════════════════════════

@router.get(
    "/admin/providers",
    response_model=Result[list[AdminLLMProviderWithModelsResponse]],
    summary="[管理员] 获取所有 LLM 提供商（含模型列表）",
    description="返回所有提供商及各自的模型列表，含 base_url 和 effective_is_active。",
)
async def admin_list_providers(
    current_user: CurrentUser,
    svc: ModelServiceDepend,
) -> Result[list[AdminLLMProviderWithModelsResponse]]:
    _require_admin(current_user)
    return Result.success(await svc.admin_list_providers())


@router.post(
    "/admin/providers",
    response_model=Result[AdminLLMProviderResponse],
    summary="[管理员] 添加 LLM 提供商",
)
async def admin_create_provider(
    body: CreateLLMProviderRequest,
    current_user: CurrentUser,
    svc: ModelServiceDepend,
) -> Result[AdminLLMProviderResponse]:
    _require_admin(current_user)
    result = await svc.admin_create_provider(
        body.name, body.base_url, body.description, body.is_active
    )
    return Result.success(result)


@router.put(
    "/admin/providers/{provider_id}",
    response_model=Result[AdminLLMProviderResponse],
    summary="[管理员] 修改 LLM 提供商",
)
async def admin_update_provider(
    provider_id: int,
    body: UpdateLLMProviderRequest,
    current_user: CurrentUser,
    svc: ModelServiceDepend,
) -> Result[AdminLLMProviderResponse]:
    _require_admin(current_user)
    result = await svc.admin_update_provider(
        provider_id, body.name, body.base_url, body.description, body.is_active
    )
    return Result.success(result)


@router.delete(
    "/admin/providers/{provider_id}",
    response_model=Result[None],
    summary="[管理员] 删除 LLM 提供商（级联删除旗下模型）",
)
async def admin_delete_provider(
    provider_id: int,
    current_user: CurrentUser,
    svc: ModelServiceDepend,
) -> Result[None]:
    _require_admin(current_user)
    await svc.admin_delete_provider(provider_id)
    return Result.success()


# ══════════════════════════════════════════════
# 管理员 LLM 模型管理
# ══════════════════════════════════════════════

@router.get(
    "/admin/providers/{provider_id}/models",
    response_model=Result[list[AdminLLMModelResponse]],
    summary="[管理员] 获取提供商下所有模型",
    description="含模型自身状态和有效状态（服务商与模型 AND）。",
)
async def admin_list_models(
    provider_id: int,
    current_user: CurrentUser,
    svc: ModelServiceDepend,
) -> Result[list[AdminLLMModelResponse]]:
    _require_admin(current_user)
    return Result.success(await svc.admin_list_models(provider_id))


@router.post(
    "/admin/providers/{provider_id}/models",
    response_model=Result[AdminLLMModelResponse],
    summary="[管理员] 为提供商添加模型",
)
async def admin_create_model(
    provider_id: int,
    body: CreateLLMProviderModelRequest,
    current_user: CurrentUser,
    svc: ModelServiceDepend,
) -> Result[AdminLLMModelResponse]:
    _require_admin(current_user)
    result = await svc.admin_create_model(
        provider_id, body.model_name, body.description, body.is_active
    )
    return Result.success(result)


@router.put(
    "/admin/providers/{provider_id}/models/{model_id}",
    response_model=Result[AdminLLMModelResponse],
    summary="[管理员] 修改模型",
    description="服务商已禁用时不可启用模型，需先解禁服务商。",
)
async def admin_update_model(
    provider_id: int,
    model_id: int,
    body: UpdateLLMProviderModelRequest,
    current_user: CurrentUser,
    svc: ModelServiceDepend,
) -> Result[AdminLLMModelResponse]:
    _require_admin(current_user)
    result = await svc.admin_update_model(
        provider_id, model_id, body.model_name, body.description, body.is_active
    )
    return Result.success(result)


@router.delete(
    "/admin/providers/{provider_id}/models/{model_id}",
    response_model=Result[None],
    summary="[管理员] 删除模型",
)
async def admin_delete_model(
    provider_id: int,
    model_id: int,
    current_user: CurrentUser,
    svc: ModelServiceDepend,
) -> Result[None]:
    _require_admin(current_user)
    await svc.admin_delete_model(provider_id, model_id)
    return Result.success()


# ══════════════════════════════════════════════
# 管理员搜索服务提供商管理
# ══════════════════════════════════════════════

@router.get(
    "/admin/search-providers",
    response_model=Result[list[AdminSearchProviderResponse]],
    summary="[管理员] 获取所有搜索服务提供商",
)
async def admin_list_search_providers(
    current_user: CurrentUser,
    svc: ModelServiceDepend,
) -> Result[list[AdminSearchProviderResponse]]:
    _require_admin(current_user)
    return Result.success(await svc.admin_list_search_providers())


@router.post(
    "/admin/search-providers",
    response_model=Result[AdminSearchProviderResponse],
    summary="[管理员] 添加搜索服务提供商",
)
async def admin_create_search_provider(
    body: CreateSearchProviderRequest,
    current_user: CurrentUser,
    svc: ModelServiceDepend,
) -> Result[AdminSearchProviderResponse]:
    _require_admin(current_user)
    result = await svc.admin_create_search_provider(
        body.name, body.api_endpoint, body.description, body.is_active
    )
    return Result.success(result)


@router.put(
    "/admin/search-providers/{provider_id}",
    response_model=Result[AdminSearchProviderResponse],
    summary="[管理员] 修改搜索服务提供商",
)
async def admin_update_search_provider(
    provider_id: int,
    body: UpdateSearchProviderRequest,
    current_user: CurrentUser,
    svc: ModelServiceDepend,
) -> Result[AdminSearchProviderResponse]:
    _require_admin(current_user)
    result = await svc.admin_update_search_provider(
        provider_id, body.name, body.api_endpoint, body.description, body.is_active
    )
    return Result.success(result)


@router.delete(
    "/admin/search-providers/{provider_id}",
    response_model=Result[None],
    summary="[管理员] 删除搜索服务提供商",
)
async def admin_delete_search_provider(
    provider_id: int,
    current_user: CurrentUser,
    svc: ModelServiceDepend,
) -> Result[None]:
    _require_admin(current_user)
    await svc.admin_delete_search_provider(provider_id)
    return Result.success()
