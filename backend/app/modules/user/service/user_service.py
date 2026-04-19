from __future__ import annotations

from app.common.exception.code import StatusCode
from app.common.exception.exception import BusinessException
from app.common.model.entity.user import UserRole
from app.config import settings
from app.infrastructure.redis.redis import redis_helper
from app.infrastructure.security.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from app.common.result.result import PageResult
from app.modules.user.dto.response import TokenResponse, UserResponse
from app.modules.user.repository.user_repository import UserRepository


class UserService:
    """用户业务逻辑层。"""

    def __init__(self, repo: UserRepository) -> None:
        self._repo = repo

    async def register(self, username: str, password: str, role: str = "user") -> None:
        """注册新用户。用户名重复时抛出 BusinessException。"""
        if await self._repo.exists_by_username(username):
            raise BusinessException.exc(StatusCode.DUPLICATE_USERNAME.value)

        try:
            user_role = UserRole(role)
        except ValueError:
            user_role = UserRole.USER

        password_hash = hash_password(password)
        await self._repo.create(username, password_hash, user_role)

    async def login(self, username: str, password: str) -> TokenResponse:
        """验证用户名密码，返回 access_token 和 refresh_token。"""
        user = await self._repo.find_by_username(username)
        if user is None or not verify_password(password, user.password_hash):
            raise BusinessException.exc(StatusCode.BAD_CREDENTIALS.value)

        if not user.is_active:
            raise BusinessException.exc(StatusCode.USER_NOT_ACTIVE.value)

        payload = {
            "sub": user.id,
            "username": user.username,
            "role": user.role.value,
        }
        access_token = create_access_token(payload)
        refresh_token = create_refresh_token(payload)
        return TokenResponse(
            username=user.username,
            access_token=access_token,
            refresh_token=refresh_token,
        )

    async def change_password(
        self, user_id: int, old_password: str, new_password: str
    ) -> None:
        """修改当前用户密码。旧密码错误时抛出 BusinessException。"""
        user = await self._repo.find_by_id(user_id)
        if user is None:
            raise BusinessException.exc(StatusCode.USER_NOT_FOUND.value)

        if not verify_password(old_password, user.password_hash):
            raise BusinessException.exc(StatusCode.INVALID_OLD_PASSWORD.value)

        await self._repo.update_password(user_id, hash_password(new_password))

    async def logout(self, token: str) -> None:
        """将 access_token 加入 Redis 黑名单，使其立即失效。"""
        if token:
            ttl = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
            await redis_helper.set(f"jwt_blacklist:{token}", "1", ttl=ttl)

    async def delete_account(self, user_id: int) -> None:
        """删除当前用户。"""
        deleted = await self._repo.delete_by_id(user_id)
        if not deleted:
            raise BusinessException.exc(StatusCode.USER_NOT_FOUND.value)

    async def get_user_by_id(self, user_id: int) -> UserResponse:
        """查询用户信息。用户不存在时抛出 BusinessException。"""
        user = await self._repo.find_by_id(user_id)
        if user is None:
            raise BusinessException.exc(StatusCode.USER_NOT_FOUND.value)
        return UserResponse.model_validate(user)

    async def refresh_token(self, refresh_token_str: str) -> TokenResponse:
        """用 refresh_token 换取新的 access_token 和 refresh_token。"""
        payload = await decode_refresh_token(refresh_token_str)
        user_id: int = payload["sub"]

        user = await self._repo.find_by_id(user_id)
        if user is None:
            raise BusinessException.exc(StatusCode.USER_NOT_FOUND.value)

        if not user.is_active:
            raise BusinessException.exc(StatusCode.DONT_HAVE_PERMISSION.value)

        new_payload = {
            "sub": user.id,
            "username": user.username,
            "role": user.role.value,
        }
        access_token = create_access_token(new_payload)
        new_refresh_token = create_refresh_token(new_payload)
        return TokenResponse(
            username=user.username,
            access_token=access_token,
            refresh_token=new_refresh_token,
        )

    # ------------------------------------------------------------------
    # 管理员接口（admin）
    # ------------------------------------------------------------------

    async def create_user(self, username: str, password: str, role: str) -> None:
        """管理员创建用户（任意角色）。"""
        if await self._repo.exists_by_username(username):
            raise BusinessException.exc(StatusCode.DUPLICATE_USERNAME.value)

        try:
            user_role = UserRole(role)
        except ValueError:
            raise BusinessException.exc(StatusCode.BAD_REQUEST.value)

        password_hash = hash_password(password)
        await self._repo.create(username, password_hash, user_role)

    async def admin_change_password(self, user_id: int, new_password: str) -> None:
        """管理员强制重置任意用户密码。"""
        user = await self._repo.find_by_id(user_id)
        if user is None:
            raise BusinessException.exc(StatusCode.USER_NOT_FOUND.value)
        await self._repo.update_password(user_id, hash_password(new_password))

    async def admin_delete_user(self, user_id: int) -> None:
        """管理员删除用户。用户不存在时抛出 BusinessException。"""
        deleted = await self._repo.delete_by_id(user_id)
        if not deleted:
            raise BusinessException.exc(StatusCode.USER_NOT_FOUND.value)

    async def admin_get_user_by_id(self, user_id: int) -> UserResponse:
        """管理员按 ID 查询任意用户。"""
        user = await self._repo.find_by_id(user_id)
        if user is None:
            raise BusinessException.exc(StatusCode.USER_NOT_FOUND.value)
        return UserResponse.model_validate(user)

    async def admin_get_user_by_username(self, username: str) -> UserResponse:
        """管理员按用户名精确查询用户。"""
        user = await self._repo.find_by_username(username)
        if user is None:
            raise BusinessException.exc(StatusCode.USER_NOT_FOUND.value)
        return UserResponse.model_validate(user)

    async def admin_get_users_page(
        self,
        page: int,
        page_size: int,
        username: str | None = None,
    ) -> PageResult[UserResponse]:
        """管理员分页查询用户列表，支持按用户名模糊过滤。"""
        users = await self._repo.find_page(page, page_size, username_like=username)
        total = await self._repo.count(username_like=username)
        return PageResult(
            items=[UserResponse.model_validate(u) for u in users],
            total=total,
            page=page,
            page_size=page_size,
        )
    
    async def admin_set_user_status(self, user_id: int) -> None:
        """管理员设置用户状态。"""
        user = await self._repo.find_by_id(user_id)
        if user is None:
            raise BusinessException.exc(StatusCode.USER_NOT_FOUND.value)
        is_active = not user.is_active
        await self._repo.set_status(user_id, is_active)
