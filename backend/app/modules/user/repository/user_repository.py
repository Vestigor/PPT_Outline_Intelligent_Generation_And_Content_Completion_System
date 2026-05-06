from __future__ import annotations

from typing import Optional

from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.model.entity.user import User, UserRole


class UserRepository:
    """User 数据访问层，封装所有针对 users 表的异步查询。"""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def find_by_id(self, user_id: int) -> Optional[User]:
        result = await self._db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def find_by_username(self, username: str) -> Optional[User]:
        result = await self._db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def find_by_email(self, email: str) -> Optional[User]:
        result = await self._db.execute(
            select(User).where(func.lower(User.email) == email.lower())
        )
        return result.scalar_one_or_none()

    async def exists_by_username(self, username: str) -> bool:
        result = await self._db.execute(select(User.id).where(User.username == username))
        return result.scalar_one_or_none() is not None

    async def exists_by_email(self, email: str) -> bool:
        result = await self._db.execute(
            select(User.id).where(func.lower(User.email) == email.lower())
        )
        return result.scalar_one_or_none() is not None

    async def create(
        self,
        username: str,
        password_hash: str,
        role: UserRole = UserRole.USER,
        email: str | None = None,
        is_email_verified: bool = False,
    ) -> User:
        user = User(
            username=username,
            password_hash=password_hash,
            role=role,
            email=email,
            is_email_verified=is_email_verified,
        )
        self._db.add(user)
        await self._db.flush()
        await self._db.refresh(user)
        return user

    async def update_password(self, user_id: int, new_password_hash: str) -> None:
        user = await self.find_by_id(user_id)
        if user is not None:
            user.password_hash = new_password_hash
            await self._db.flush()

    async def update_email(
        self, user_id: int, email: str | None, is_email_verified: bool
    ) -> None:
        user = await self.find_by_id(user_id)
        if user is not None:
            user.email = email
            user.is_email_verified = is_email_verified
            await self._db.flush()

    async def set_status(self, user_id: int, is_active: bool) -> None:
        user = await self.find_by_id(user_id)
        if user is not None:
            user.is_active = is_active
            await self._db.flush()

    async def delete_by_id(self, user_id: int) -> bool:
        result = await self._db.execute(delete(User).where(User.id == user_id))
        return result.rowcount > 0

    async def find_page(
        self,
        page: int,
        page_size: int,
        username_like: Optional[str] = None,
    ) -> list[User]:
        stmt = select(User).order_by(User.id)
        if username_like:
            stmt = stmt.where(User.username.ilike(f"%{username_like}%"))
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def count(self, username_like: Optional[str] = None) -> int:
        stmt = select(func.count(User.id))
        if username_like:
            stmt = stmt.where(User.username.ilike(f"%{username_like}%"))
        result = await self._db.execute(stmt)
        return result.scalar_one()
