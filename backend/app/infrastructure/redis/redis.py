from __future__ import annotations

import json
from typing import Any, AsyncGenerator

import redis.asyncio as aioredis

from app.config import settings


redis_client: aioredis.Redis = aioredis.from_url(
    settings.REDIS_URL,
    encoding="utf-8",
    decode_responses=True,
    max_connections=10,
    health_check_interval=30,
)


class RedisHelper:

    def __init__(self, client: aioredis.Redis | None = None) -> None:
        self._client = client or redis_client

    # ========================
    # 内部工具方法（统一序列化）
    # ========================

    def _serialize(self, value: Any) -> str:
        if isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False)

    def _deserialize(self, value: str | None) -> Any:
        if value is None:
            return None
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value

    # ========================
    # String
    # ========================

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        serialized = self._serialize(value)
        if ttl:
            await self._client.setex(key, ttl, serialized)
        else:
            await self._client.set(key, serialized)

    async def get(self, key: str) -> Any | None:
        raw = await self._client.get(key)
        return self._deserialize(raw)

    async def delete(self, *keys: str) -> None:
        if keys:
            await self._client.delete(*keys)

    async def exists(self, key: str) -> bool:
        return bool(await self._client.exists(key))

    async def expire(self, key: str, ttl: int) -> None:
        await self._client.expire(key, ttl)

    # ========================
    # List
    # ========================

    async def rpush(self, key: str, *values: Any) -> None:
        if not values:
            return
        serialized = [self._serialize(v) for v in values]
        await self._client.rpush(key, *serialized)

    async def lpop(self, key: str) -> Any | None:
        raw = await self._client.lpop(key)
        return self._deserialize(raw)

    async def lrange(self, key: str, start: int = 0, end: int = -1) -> list[Any]:
        raw_list = await self._client.lrange(key, start, end)
        return [self._deserialize(v) for v in raw_list]

    async def llen(self, key: str) -> int:
        return await self._client.llen(key)

    # ========================
    # Pub/Sub
    # ========================

    async def publish(self, channel: str, message: Any) -> None:
        await self._client.publish(channel, self._serialize(message))

    def pubsub(self) -> aioredis.client.PubSub:
        return self._client.pubsub()

    async def subscribe(self, channel: str) -> AsyncGenerator[Any, None]:
        """
        用于 SSE / WebSocket 推送
        """
        pubsub = self._client.pubsub()
        await pubsub.subscribe(channel)

        try:
            async for msg in pubsub.listen():
                if msg["type"] == "message":
                    yield self._deserialize(msg["data"])
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()

    # ========================
    # Hash
    # ========================

    async def hset(self, name: str, mapping: dict[str, Any]) -> None:
        serialized = {k: self._serialize(v) for k, v in mapping.items()}
        await self._client.hset(name, mapping=serialized)

    async def hget(self, name: str, key: str) -> Any | None:
        raw = await self._client.hget(name, key)
        return self._deserialize(raw)

    async def hgetall(self, name: str) -> dict[str, Any]:
        raw_map = await self._client.hgetall(name)
        return {k: self._deserialize(v) for k, v in raw_map.items()}

    # ========================
    # Stream
    # ========================

    async def xadd(
        self,
        stream: str,
        data: dict[str, Any],
        maxlen: int | None = None,
    ) -> str:
        """
        写入消息
        """
        serialized = {k: self._serialize(v) for k, v in data.items()}
        return await self._client.xadd(stream, serialized, maxlen=maxlen)

    async def xgroup_create(
        self,
        stream: str,
        group: str,
        id: str = "0",
    ) -> None:
        """
        创建消费组
        """
        try:
            await self._client.xgroup_create(
                name=stream,
                groupname=group,
                id=id,
                mkstream=True,
            )
        except Exception:
            pass  # 已存在

    async def xreadgroup(
        self,
        stream: str,
        group: str,
        consumer: str,
        count: int = 10,
        block: int = 5000,
    ) -> list[tuple[str, dict[str, Any]]]:
        """
        消费消息
        """
        result = await self._client.xreadgroup(
            groupname=group,
            consumername=consumer,
            streams={stream: ">"},
            count=count,
            block=block,
        )

        messages: list[tuple[str, dict[str, Any]]] = []

        for _, msgs in result:
            for msg_id, data in msgs:
                parsed = {k: self._deserialize(v) for k, v in data.items()}
                messages.append((msg_id, parsed))

        return messages

    async def xack(self, stream: str, group: str, msg_id: str) -> None:
        await self._client.xack(stream, group, msg_id)

    # ========================
    # 健康检查
    # ========================

    async def ping(self) -> bool:
        try:
            return await self._client.ping()
        except Exception:
            return False


redis_helper = RedisHelper()