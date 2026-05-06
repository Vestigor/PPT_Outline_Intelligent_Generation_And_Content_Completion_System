from __future__ import annotations

from fastapi import APIRouter, Query
from typing import Optional

from app.dependencies import Token, CurrentUser, UserServiceDepend
from app.common.result.result import Result, PageResult
from app.common.exception.code import StatusCode
from app.common.exception.exception import BusinessException
from app.infrastructure.log.logging_config import get_logger
from app.modules.user.dto.request import (
    SendEmailCodeRequest,
    UserRegisterRequest,
    UserLoginRequest,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    RefreshTokenRequest,
    UpdateEmailRequest,
    AdminCreateUserRequest,
    AdminChangePasswordRequest,
    AdminSetEmailRequest,
)
from app.modules.user.dto.response import UserResponse, TokenResponse

logger = get_logger(__name__)

router = APIRouter(prefix="/users", tags=["用户管理"])


# ------------------------------------------------------------------
# 邮箱验证码
# ------------------------------------------------------------------

@router.post(
    "/send-email-code",
    response_model=Result[None],
    summary="发送邮箱验证码",
    description="purpose=register 时检查邮箱未注册；purpose=reset_password 时检查邮箱已注册。",
)
async def send_email_code(body: SendEmailCodeRequest, svc: UserServiceDepend) -> Result[None]:
    await svc.send_email_code(email=body.email, purpose=body.purpose)
    return Result.success()


# ------------------------------------------------------------------
# 用户端接口
# ------------------------------------------------------------------

@router.post("/register", response_model=Result[None], summary="注册新用户（需邮箱验证码）")
async def register(body: UserRegisterRequest, svc: UserServiceDepend) -> Result[None]:
    await svc.register(
        username=body.username,
        password=body.password,
        email=body.email,
        code=body.code,
    )
    return Result.success()


@router.post("/login", response_model=Result[TokenResponse], summary="用户登录")
async def login(body: UserLoginRequest, svc: UserServiceDepend) -> Result[TokenResponse]:
    return Result.success(await svc.login(body.username, body.password))


@router.post("/forgot-password", response_model=Result[None], summary="忘记密码（邮箱验证码重置）")
async def forgot_password(body: ForgotPasswordRequest, svc: UserServiceDepend) -> Result[None]:
    await svc.forgot_password(email=body.email, code=body.code, new_password=body.new_password)
    return Result.success()


@router.put("/me/email", response_model=Result[None], summary="绑定/修改邮箱（需密码验证和邮箱验证码）")
async def update_email(
    body: UpdateEmailRequest,
    current_user: CurrentUser,
    svc: UserServiceDepend,
) -> Result[None]:
    await svc.update_email(current_user.id, str(body.new_email), body.code, body.password)
    return Result.success()


@router.put("/me/password", response_model=Result[None], summary="修改密码（需旧密码）")
async def change_password(
    body: ChangePasswordRequest,
    current_user: CurrentUser,
    svc: UserServiceDepend,
) -> Result[None]:
    await svc.change_password(current_user.id, body.old_password, body.new_password)
    return Result.success()


@router.post("/logout", response_model=Result[None], summary="退出登录")
async def logout(token: Token, svc: UserServiceDepend) -> Result[None]:
    await svc.logout(token)
    return Result.success()


@router.delete("", response_model=Result[None], summary="注销账户")
async def delete_account(current_user: CurrentUser, svc: UserServiceDepend) -> Result[None]:
    await svc.delete_account(current_user.id)
    return Result.success()


@router.get("/me", response_model=Result[UserResponse], summary="获取当前用户信息")
async def get_me(current_user: CurrentUser, svc: UserServiceDepend) -> Result[UserResponse]:
    return Result.success(await svc.get_user_by_id(current_user.id))


@router.post("/refresh", response_model=Result[TokenResponse], summary="刷新访问令牌")
async def refresh_token(body: RefreshTokenRequest, svc: UserServiceDepend) -> Result[TokenResponse]:
    return Result.success(await svc.refresh_token(body.refresh_token))


# ------------------------------------------------------------------
# 管理员接口
# ------------------------------------------------------------------

def _require_admin(current_user: CurrentUser) -> None:
    if current_user.role not in ("admin", "super_admin"):
        raise BusinessException.exc(StatusCode.DONT_HAVE_PERMISSION.value)


@router.post(
    "/admin/create_user",
    response_model=Result[None],
    summary="[管理员] 创建用户",
)
async def admin_create_user(
    body: AdminCreateUserRequest,
    current_user: CurrentUser,
    svc: UserServiceDepend,
) -> Result[None]:
    _require_admin(current_user)
    await svc.create_user(
        requester_role=current_user.role,
        username=body.username,
        password=body.password,
        role=body.role,
    )
    return Result.success()


@router.post(
    "/admin/change_password",
    response_model=Result[None],
    summary="[管理员] 重置用户密码",
)
async def admin_change_password(
    body: AdminChangePasswordRequest,
    current_user: CurrentUser,
    svc: UserServiceDepend,
) -> Result[None]:
    _require_admin(current_user)
    await svc.admin_change_password(
        requester_role=current_user.role,
        user_id=body.user_id,
        new_password=body.new_password,
    )
    return Result.success()


@router.delete(
    "/admin/delete_user/{user_id}",
    response_model=Result[None],
    summary="[管理员] 删除用户",
)
async def admin_delete_user(
    user_id: int,
    current_user: CurrentUser,
    svc: UserServiceDepend,
) -> Result[None]:
    _require_admin(current_user)
    await svc.admin_delete_user(requester_role=current_user.role, user_id=user_id)
    return Result.success()


@router.get(
    "/admin/users",
    response_model=Result[PageResult[UserResponse]],
    summary="[管理员] 分页查询用户列表",
)
async def admin_list_users(
    current_user: CurrentUser,
    svc: UserServiceDepend,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    username: Optional[str] = Query(None),
) -> Result[PageResult[UserResponse]]:
    _require_admin(current_user)
    return Result.success(await svc.admin_get_users_page(page, page_size, username))


@router.get(
    "/admin/users/by-username/{username}",
    response_model=Result[UserResponse],
    summary="[管理员] 按用户名精确查询用户",
)
async def admin_get_user_by_username(
    username: str, current_user: CurrentUser, svc: UserServiceDepend,
) -> Result[UserResponse]:
    _require_admin(current_user)
    return Result.success(await svc.admin_get_user_by_username(username))


@router.get(
    "/admin/users/{user_id}",
    response_model=Result[UserResponse],
    summary="[管理员] 按 ID 查询用户",
)
async def admin_get_user_by_id(
    user_id: int, current_user: CurrentUser, svc: UserServiceDepend,
) -> Result[UserResponse]:
    _require_admin(current_user)
    return Result.success(await svc.admin_get_user_by_id(user_id))


@router.put(
    "/admin/users/{user_id}/email",
    response_model=Result[None],
    summary="[管理员] 设置用户邮箱",
)
async def admin_set_email(
    user_id: int,
    body: AdminSetEmailRequest,
    current_user: CurrentUser,
    svc: UserServiceDepend,
) -> Result[None]:
    _require_admin(current_user)
    await svc.admin_set_email(
        requester_role=current_user.role,
        user_id=user_id,
        email=str(body.email) if body.email else None,
    )
    return Result.success()


@router.put(
    "/admin/users/status/{user_id}",
    response_model=Result[None],
    summary="[管理员] 切换用户状态",
)
async def admin_set_user_status(
    user_id: int, current_user: CurrentUser, svc: UserServiceDepend,
) -> Result[None]:
    _require_admin(current_user)
    await svc.admin_set_user_status(requester_role=current_user.role, user_id=user_id)
    return Result.success()
