from __future__ import annotations

import random
import string

from app.common.exception.code import StatusCode
from app.common.exception.exception import BusinessException
from app.common.model.entity.user import UserRole
from app.config import settings
from app.infrastructure.email.email_service import send_verification_code, send_password_reset_code
from app.infrastructure.log.logging_config import get_logger
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

logger = get_logger(__name__)

_EMAIL_CODE_PREFIX = "email_code:"


def _generate_code(length: int = 6) -> str:
    return ''.join(random.choices(string.digits, k=length))


def _email_code_key(email: str, purpose: str) -> str:
    return f"{_EMAIL_CODE_PREFIX}{purpose}:{email.lower()}"


class UserService:
    """用户业务逻辑层。"""

    def __init__(self, repo: UserRepository) -> None:
        self._repo = repo

    # ──────────────────────────────────────────────
    # 邮箱验证码
    # ──────────────────────────────────────────────

    async def send_email_code(self, email: str, purpose: str) -> None:
        """
        发送邮箱验证码。
        - purpose='register'      → 检查邮箱是否已被注册
        - purpose='reset_password' → 检查邮箱是否已注册（必须存在才能重置）
        """
        email = email.lower().strip()

        if purpose == "register":
            if await self._repo.exists_by_email(email):
                raise BusinessException.exc(StatusCode.EMAIL_ALREADY_REGISTERED.value)
        elif purpose == "reset_password":
            if not await self._repo.exists_by_email(email):
                raise BusinessException.exc(StatusCode.EMAIL_NOT_FOUND.value)
        elif purpose == "bind_email":
            if await self._repo.exists_by_email(email):
                raise BusinessException.exc(StatusCode.EMAIL_ALREADY_REGISTERED.value)
        else:
            raise BusinessException.exc(StatusCode.BAD_REQUEST.value)

        code = _generate_code()
        key  = _email_code_key(email, purpose)
        await redis_helper.set(key, code, ttl=settings.EMAIL_CODE_TTL_SECONDS)
        logger.info("Sending %s code to %s", purpose, email)

        try:
            if purpose == "register":
                await send_verification_code(email, code)
            else:
                await send_password_reset_code(email, code)
        except Exception as exc:
            logger.error("Failed to send email to %s: %s", email, exc)
            await redis_helper.delete(key)
            raise BusinessException.exc(StatusCode.EMAIL_CODE_SEND_FAILED.value) from exc

    async def _verify_email_code(self, email: str, purpose: str, code: str) -> None:
        """验证邮箱验证码，通过后删除（单次有效）。"""
        key = _email_code_key(email, purpose)
        stored = await redis_helper.get(key)
        if stored is None or str(stored) != str(code):
            raise BusinessException.exc(StatusCode.EMAIL_CODE_INVALID.value)
        await redis_helper.delete(key)

    # ──────────────────────────────────────────────
    # 注册 / 登录
    # ──────────────────────────────────────────────

    async def register(self, username: str, password: str, email: str, code: str) -> None:
        """用户注册（需邮箱验证码）。"""
        email = email.lower().strip()
        logger.info("Register attempt: username=%s email=%s", username, email)

        if await self._repo.exists_by_username(username):
            raise BusinessException.exc(StatusCode.DUPLICATE_USERNAME.value)

        if await self._repo.exists_by_email(email):
            raise BusinessException.exc(StatusCode.EMAIL_ALREADY_REGISTERED.value)

        await self._verify_email_code(email, "register", code)

        password_hash = hash_password(password)
        await self._repo.create(
            username=username,
            password_hash=password_hash,
            role=UserRole.USER,
            email=email,
            is_email_verified=True,
        )
        logger.info("User registered: username=%s email=%s", username, email)

    async def login(self, username: str, password: str) -> TokenResponse:
        """验证用户名密码，返回 access_token 和 refresh_token。"""
        logger.info("Login attempt: username=%s", username)
        user = await self._repo.find_by_username(username)
        if user is None or not verify_password(password, user.password_hash):
            raise BusinessException.exc(StatusCode.BAD_CREDENTIALS.value)

        if not user.is_active:
            raise BusinessException.exc(StatusCode.USER_NOT_ACTIVE.value)

        payload = {
            "sub": str(user.id),
            "username": user.username,
            "role": user.role.value,
        }
        access_token  = create_access_token(payload)
        refresh_token = create_refresh_token(payload)
        logger.info("Login successful: user_id=%d username=%s", user.id, username)
        return TokenResponse(
            username=user.username,
            access_token=access_token,
            refresh_token=refresh_token,
        )

    async def forgot_password(self, email: str, code: str, new_password: str) -> None:
        """通过邮箱验证码重置密码。"""
        email = email.lower().strip()
        user = await self._repo.find_by_email(email)
        if user is None:
            raise BusinessException.exc(StatusCode.EMAIL_NOT_FOUND.value)

        await self._verify_email_code(email, "reset_password", code)

        await self._repo.update_password(user.id, hash_password(new_password))
        logger.info("Password reset via email: user_id=%d", user.id)

    async def update_email(
        self, user_id: int, new_email: str, code: str, password: str
    ) -> None:
        """绑定/修改邮箱：验证当前密码 + 新邮箱验证码。"""
        new_email = new_email.lower().strip()
        user = await self._repo.find_by_id(user_id)
        if user is None:
            raise BusinessException.exc(StatusCode.USER_NOT_FOUND.value)
        if not verify_password(password, user.password_hash):
            raise BusinessException.exc(StatusCode.INVALID_OLD_PASSWORD.value)
        existing = await self._repo.find_by_email(new_email)
        if existing is not None and existing.id != user_id:
            raise BusinessException.exc(StatusCode.EMAIL_ALREADY_REGISTERED.value)
        await self._verify_email_code(new_email, "bind_email", code)
        await self._repo.update_email(user_id, new_email, True)
        logger.info("Email updated: user_id=%d new_email=%s", user_id, new_email)

    async def admin_set_email(
        self, requester_role: str, user_id: int, email: str | None
    ) -> None:
        """管理员直接设置用户邮箱（无需验证码，标记为未验证）。"""
        user = await self._repo.find_by_id(user_id)
        if user is None:
            raise BusinessException.exc(StatusCode.USER_NOT_FOUND.value)
        if user.role == UserRole.SUPER_ADMIN:
            raise BusinessException.exc(StatusCode.SUPER_ADMIN_PROTECTED.value)
        if requester_role == UserRole.ADMIN.value and user.role == UserRole.ADMIN:
            raise BusinessException.exc(StatusCode.ADMIN_CANNOT_MANAGE_ADMIN.value)
        if email:
            existing = await self._repo.find_by_email(email)
            if existing is not None and existing.id != user_id:
                raise BusinessException.exc(StatusCode.EMAIL_ALREADY_REGISTERED.value)
        await self._repo.update_email(user_id, email, False)
        logger.info("Admin set email for user_id=%d email=%s", user_id, email)

    async def change_password(self, user_id: int, old_password: str, new_password: str) -> None:
        """修改当前用户密码（需提供旧密码）。"""
        logger.info("Password change attempt: user_id=%d", user_id)
        user = await self._repo.find_by_id(user_id)
        if user is None:
            raise BusinessException.exc(StatusCode.USER_NOT_FOUND.value)
        if not verify_password(old_password, user.password_hash):
            raise BusinessException.exc(StatusCode.INVALID_OLD_PASSWORD.value)
        await self._repo.update_password(user_id, hash_password(new_password))
        logger.info("Password changed: user_id=%d", user_id)

    async def logout(self, token: str) -> None:
        """将 access_token 加入 Redis 黑名单，使其立即失效。"""
        if token:
            ttl = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
            await redis_helper.set(f"jwt_blacklist:{token}", "1", ttl=ttl)
            logger.info("Token blacklisted (logout)")

    async def delete_account(self, user_id: int) -> None:
        """删除当前用户。"""
        logger.info("Account deletion: user_id=%d", user_id)
        deleted = await self._repo.delete_by_id(user_id)
        if not deleted:
            raise BusinessException.exc(StatusCode.USER_NOT_FOUND.value)

    async def get_user_by_id(self, user_id: int) -> UserResponse:
        user = await self._repo.find_by_id(user_id)
        if user is None:
            raise BusinessException.exc(StatusCode.USER_NOT_FOUND.value)
        return UserResponse.model_validate(user)

    async def refresh_token(self, refresh_token_str: str) -> TokenResponse:
        """用 refresh_token 换取新的令牌对。"""
        payload = await decode_refresh_token(refresh_token_str)
        user_id: int = int(payload["sub"])
        user = await self._repo.find_by_id(user_id)
        if user is None:
            raise BusinessException.exc(StatusCode.USER_NOT_FOUND.value)
        if not user.is_active:
            raise BusinessException.exc(StatusCode.DONT_HAVE_PERMISSION.value)

        new_payload = {
            "sub": str(user.id),
            "username": user.username,
            "role": user.role.value,
        }
        access_token  = create_access_token(new_payload)
        new_refresh   = create_refresh_token(new_payload)
        logger.info("Token refreshed: user_id=%d", user_id)
        return TokenResponse(
            username=user.username,
            access_token=access_token,
            refresh_token=new_refresh,
        )

    # ──────────────────────────────────────────────
    # 管理员接口
    # ──────────────────────────────────────────────

    async def create_user(self, requester_role: str, username: str, password: str, role: str) -> None:
        logger.info("Admin creating user: username=%s role=%s", username, role)
        if await self._repo.exists_by_username(username):
            raise BusinessException.exc(StatusCode.DUPLICATE_USERNAME.value)

        try:
            user_role = UserRole(role)
        except ValueError:
            raise BusinessException.exc(StatusCode.BAD_REQUEST.value)

        if user_role in (UserRole.ADMIN, UserRole.SUPER_ADMIN) and requester_role != UserRole.SUPER_ADMIN.value:
            raise BusinessException.exc(StatusCode.DONT_HAVE_PERMISSION.value)

        password_hash = hash_password(password)
        await self._repo.create(username=username, password_hash=password_hash, role=user_role)

    async def admin_change_password(self, requester_role: str, user_id: int, new_password: str) -> None:
        user = await self._repo.find_by_id(user_id)
        if user is None:
            raise BusinessException.exc(StatusCode.USER_NOT_FOUND.value)
        if user.role == UserRole.SUPER_ADMIN:
            raise BusinessException.exc(StatusCode.SUPER_ADMIN_PROTECTED.value)
        if requester_role == UserRole.ADMIN.value and user.role == UserRole.ADMIN:
            raise BusinessException.exc(StatusCode.ADMIN_CANNOT_MANAGE_ADMIN.value)
        await self._repo.update_password(user_id, hash_password(new_password))

    async def admin_delete_user(self, requester_role: str, user_id: int) -> None:
        user = await self._repo.find_by_id(user_id)
        if user is None:
            raise BusinessException.exc(StatusCode.USER_NOT_FOUND.value)
        if user.role == UserRole.SUPER_ADMIN:
            raise BusinessException.exc(StatusCode.SUPER_ADMIN_PROTECTED.value)
        if requester_role == UserRole.ADMIN.value and user.role == UserRole.ADMIN:
            raise BusinessException.exc(StatusCode.ADMIN_CANNOT_MANAGE_ADMIN.value)
        await self._repo.delete_by_id(user_id)

    async def admin_get_user_by_id(self, user_id: int) -> UserResponse:
        user = await self._repo.find_by_id(user_id)
        if user is None:
            raise BusinessException.exc(StatusCode.USER_NOT_FOUND.value)
        return UserResponse.model_validate(user)

    async def admin_get_user_by_username(self, username: str) -> UserResponse:
        user = await self._repo.find_by_username(username)
        if user is None:
            raise BusinessException.exc(StatusCode.USER_NOT_FOUND.value)
        return UserResponse.model_validate(user)

    async def admin_get_users_page(
        self, page: int, page_size: int, username: str | None = None,
    ) -> PageResult[UserResponse]:
        users = await self._repo.find_page(page, page_size, username_like=username)
        total = await self._repo.count(username_like=username)
        return PageResult(
            items=[UserResponse.model_validate(u) for u in users],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def admin_set_user_status(self, requester_role: str, user_id: int) -> None:
        user = await self._repo.find_by_id(user_id)
        if user is None:
            raise BusinessException.exc(StatusCode.USER_NOT_FOUND.value)
        if user.role == UserRole.SUPER_ADMIN:
            raise BusinessException.exc(StatusCode.SUPER_ADMIN_PROTECTED.value)
        if requester_role == UserRole.ADMIN.value and user.role == UserRole.ADMIN:
            raise BusinessException.exc(StatusCode.ADMIN_CANNOT_MANAGE_ADMIN.value)
        await self._repo.set_status(user_id, not user.is_active)
