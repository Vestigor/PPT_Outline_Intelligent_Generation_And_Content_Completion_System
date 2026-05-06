from __future__ import annotations

import base64
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from cryptography.fernet import Fernet
from jose import ExpiredSignatureError, JWTError, jwt

from app.config import settings
from app.common.exception.code import StatusCode
from app.common.exception.exception import AuthException
from app.infrastructure.log.logging_config import get_logger
from app.infrastructure.redis.redis import redis_helper

logger = get_logger(__name__)

def hash_password(plain: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plain.encode(), salt).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def _get_fernet() -> Fernet:
    """使用 SECRET_KEY 派生 Fernet 加密密钥。"""
    raw = settings.SECRET_KEY.encode()
    derived = hashlib.sha256(raw).digest()
    fernet_key = base64.urlsafe_b64encode(derived)
    return Fernet(fernet_key)


def encrypt_api_key(plain: str) -> str:
    """对 API Key 做对称加密，返回 base64 密文字符串。"""
    return _get_fernet().encrypt(plain.encode()).decode()


def decrypt_api_key(encrypted: str) -> str:
    """解密 API Key，返回明文。"""
    return _get_fernet().decrypt(encrypted.encode()).decode()


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    payload = data.copy()
    expire = datetime.now(tz=timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload.update({"exp": expire, "type": "access"})
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(data: dict[str, Any]) -> str:
    payload = data.copy()
    expire = datetime.now(tz=timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload.update({"exp": expire, "type": "refresh"})
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


async def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )

        if payload.get("type") != "access":
            logger.error("Invalid JWT type")
            raise AuthException.exc(StatusCode.INVALID_JWT_TYPE.value)

        if not payload.get("sub") and not payload.get("jti"):
            logger.error("Invalid JWT")
            raise AuthException.exc(StatusCode.INVALID_JWT.value)

        if await tokenInBlacklist(token):
            logger.error("JWT blacklisted")
            raise AuthException.exc(StatusCode.JWT_BLACKLISTED.value)
        
        return payload

    except ExpiredSignatureError:
        raise AuthException.exc(StatusCode.JWT_EXPIRED.value)
    except JWTError as e:
        logger.warning("JWT decode failed: %s", e)
        raise AuthException.exc(StatusCode.INVALID_JWT.value)


async def decode_refresh_token(token: str) -> dict[str, Any]:
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )

        if payload.get("type") != "refresh":
            raise AuthException.exc(StatusCode.INVALID_JWT_TYPE.value)

        if not payload.get("sub"):
            raise AuthException.exc(StatusCode.INVALID_JWT.value)

        if await tokenInBlacklist(token):
            raise AuthException.exc(StatusCode.JWT_BLACKLISTED.value)

        return payload

    except ExpiredSignatureError:
        raise AuthException.exc(StatusCode.JWT_EXPIRED.value)
    except JWTError as e:
        logger.warning("Refresh JWT decode failed: %s", e)
        raise AuthException.exc(StatusCode.INVALID_JWT.value)


async def tokenInBlacklist(token: str) -> bool:
    return await redis_helper.exists(f"jwt_blacklist:{token}")
