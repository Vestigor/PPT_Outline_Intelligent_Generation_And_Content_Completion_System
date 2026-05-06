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
    UserDefaultsResponse,
    UserLLMConfigResponse,
    UserLLMProviderBrowseResponse,
    UserRagConfigResponse,
    UserSearchConfigResponse,
)

router = APIRouter(prefix="/model", tags=["模型管理"])


# ══════════════════════════════════════════════
# 会话创建前默认配置预览
# ══════════════════════════════════════════════

@router.get(
    "/defaults",
    response_model=Result[UserDefaultsResponse],
    summary="获取用户当前默认配置（创建会话前调用）",
    description="返回默认 LLM 配置和搜索配置摘要，纯只读，不触发任何 DB 写操作。",
)
async def get_user_defaults(
    current_user: CurrentUser,
    svc: ModelServiceDepend,
) -> Result[UserDefaultsResponse]:
    return Result.success(await svc.get_user_defaults(current_user.id))


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
    description="为选定的模型填写 API Key，会验证 Key 有效性，已配置的模型不可重复添加。",
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
    description="已停用的配置不可修改，可删除。修改 API Key 时会重新验证有效性。",
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
    description="不可将已停用配置设为默认。",
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
    description="会验证 API Key 有效性（调用真实 Embedding 接口）。",
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
    description="会重新验证新 API Key 有效性。",
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
    response_model=Result[UserSearchConfigResponse | None],
    summary="获取 DeepSearch（Tavily）配置",
)
async def get_user_search_config(
    current_user: CurrentUser,
    svc: ModelServiceDepend,
) -> Result[UserSearchConfigResponse | None]:
    return Result.success(await svc.get_user_search_config(current_user.id))


@router.post(
    "/configs/search",
    response_model=Result[UserSearchConfigResponse],
    summary="添加 DeepSearch 配置（Tavily API Key）",
    description="固定使用 Tavily，每用户只能配置一条。会验证 API Key 有效性。",
)
async def create_user_search_config(
    body: CreateUserSearchConfigRequest,
    current_user: CurrentUser,
    svc: ModelServiceDepend,
) -> Result[UserSearchConfigResponse]:
    return Result.success(await svc.create_user_search_config(current_user.id, body.api_key))


@router.put(
    "/configs/search",
    response_model=Result[UserSearchConfigResponse],
    summary="修改 DeepSearch 配置",
    description="会重新验证新 API Key 有效性。",
)
async def update_user_search_config(
    body: UpdateUserSearchConfigRequest,
    current_user: CurrentUser,
    svc: ModelServiceDepend,
) -> Result[UserSearchConfigResponse]:
    return Result.success(await svc.update_user_search_config(current_user.id, body.api_key))


@router.delete(
    "/configs/search",
    response_model=Result[None],
    summary="删除 DeepSearch 配置",
)
async def delete_user_search_config(
    current_user: CurrentUser,
    svc: ModelServiceDepend,
) -> Result[None]:
    await svc.delete_user_search_config(current_user.id)
    return Result.success()


# ══════════════════════════════════════════════
# 身份校验
# ══════════════════════════════════════════════

def _require_admin(current_user: CurrentUser) -> None:
    if current_user.role not in ("admin", "super_admin"):
        raise BusinessException.exc(StatusCode.DONT_HAVE_PERMISSION.value)


# ══════════════════════════════════════════════
# 管理员 LLM 提供商管理
# ══════════════════════════════════════════════

@router.get(
    "/admin/providers",
    response_model=Result[list[AdminLLMProviderWithModelsResponse]],
    summary="[管理员] 获取所有 LLM 提供商（含模型列表）",
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
    return Result.success(
        await svc.admin_create_provider(body.name, body.base_url, body.description, body.is_active)
    )


@router.put(
    "/admin/providers/{provider_id}",
    response_model=Result[AdminLLMProviderResponse],
    summary="[管理员] 修改 LLM 提供商",
    description="禁用服务商时自动清除旗下所有用户配置的默认标记（懒更新策略）。",
)
async def admin_update_provider(
    provider_id: int,
    body: UpdateLLMProviderRequest,
    current_user: CurrentUser,
    svc: ModelServiceDepend,
) -> Result[AdminLLMProviderResponse]:
    _require_admin(current_user)
    return Result.success(
        await svc.admin_update_provider(
            provider_id, body.name, body.base_url, body.description, body.is_active
        )
    )


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
    return Result.success(
        await svc.admin_create_model(provider_id, body.model_name, body.description, body.is_active)
    )


@router.put(
    "/admin/providers/{provider_id}/models/{model_id}",
    response_model=Result[AdminLLMModelResponse],
    summary="[管理员] 修改模型",
    description="服务商已禁用时不可启用模型。禁用模型时自动清除用户默认标记（懒更新策略）。",
)
async def admin_update_model(
    provider_id: int,
    model_id: int,
    body: UpdateLLMProviderModelRequest,
    current_user: CurrentUser,
    svc: ModelServiceDepend,
) -> Result[AdminLLMModelResponse]:
    _require_admin(current_user)
    return Result.success(
        await svc.admin_update_model(
            provider_id, model_id, body.model_name, body.description, body.is_active
        )
    )


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
