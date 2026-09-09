import logging
from typing import cast
from uuid import UUID

from redis.asyncio import Redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

TOMBSTONE = b'\x00tombstone'

KEY_VERSION = 'v1'


def build_key(namespace: str, obj_id: UUID) -> str:
    return f'{KEY_VERSION}:{namespace}:{obj_id}'


class Cache:
    def __init__(
        self,
        client: Redis,
        ttl_seconds: int,
        tombstone_ttl_ms: int,
        invalidation_attempts: int,
    ) -> None:
        self.client = client
        self.ttl_seconds = ttl_seconds
        self.tombstone_ttl_ms = tombstone_ttl_ms
        self.invalidation_attempts = invalidation_attempts

    async def get(self, key: str) -> bytes | None:
        try:
            value = cast('bytes | None', await self.client.get(key))
        except RedisError:
            logger.warning('cache read failed: %s', key, exc_info=True)
            return None
        return None if value == TOMBSTONE else value

    async def add(self, key: str, value: bytes) -> None:
        try:
            await self.client.set(key, value, ex=self.ttl_seconds, nx=True)
        except RedisError:
            logger.warning('cache write failed: %s', key, exc_info=True)

    async def tombstone(self, key: str) -> bool:
        for _ in range(self.invalidation_attempts):
            try:
                await self.client.set(key, TOMBSTONE, px=self.tombstone_ttl_ms)
            except RedisError:
                logger.warning('cache invalidation attempt failed: %s', key, exc_info=True)
            else:
                return True
        return False

    async def delete(self, key: str) -> None:
        try:
            await self.client.delete(key)
        except RedisError:
            logger.warning('cache delete failed: %s', key, exc_info=True)


class CacheSession:
    def __init__(self, cache: Cache) -> None:
        self.cache = cache
        self.pending: list[str] = []

    async def get(self, key: str) -> bytes | None:
        return await self.cache.get(key)

    async def add(self, key: str, value: bytes) -> None:
        await self.cache.add(key, value)

    async def delete(self, key: str) -> None:
        await self.cache.delete(key)

    def invalidate_after_commit(self, key: str) -> None:
        self.pending.append(key)

    async def apply_pending(self) -> None:
        lost: list[str] = []
        for key in self.pending:
            if not await self.cache.tombstone(key):
                lost.append(key)
        self.pending.clear()
        if lost:
            logger.error('cache invalidation lost: %s', ', '.join(lost))
