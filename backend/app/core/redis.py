import redis.asyncio as aioredis

from app.core.config import settings


class RedisClient:
    def __init__(self):
        self._redis = None

    async def initialize(self):
        self._redis = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )

    async def close(self):
        if self._redis:
            await self._redis.close()

    @property
    def client(self):
        return self._redis

    async def get(self, key: str) -> str | None:
        return await self._redis.get(key)

    async def set(self, key: str, value: str, ex: int | None = None):
        await self._redis.set(key, value, ex=ex)

    async def delete(self, key: str):
        await self._redis.delete(key)

    async def incr(self, key: str) -> int:
        """Increment a counter and return its new value, creating it at 1.

        One round trip and atomic on the server, so two mutations racing each
        other still move the counter twice and neither loses the other's bump.
        """
        return await self._redis.incr(key)

    async def delete_pattern(self, pattern: str) -> int:
        """Delete every key matching a glob pattern, returning how many.

        scan_iter walks the keyspace in batches; KEYS would block the server
        for as long as it takes to scan every key.
        """
        deleted = 0
        async for key in self._redis.scan_iter(match=pattern):
            await self._redis.delete(key)
            deleted += 1
        return deleted

    async def exists(self, key: str) -> bool:
        return await self._redis.exists(key)


redis_client = RedisClient()
