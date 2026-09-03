import logging
from typing import cast
from uuid import UUID

from redis.asyncio import Redis
from redis.asyncio.retry import Retry
from redis.backoff import NoBackoff
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

SOCKET_TIMEOUT_SECONDS = 0.5

TOMBSTONE = b'\x00tombstone'
TOMBSTONE_TTL_MS = 2000

KEY_VERSION = 'v1'


def build_key(namespace: str, obj_id: UUID) -> str:
    return f'{KEY_VERSION}:{namespace}:{obj_id}'


def build_client(host: str, port: int) -> Redis:
    return Redis(
        host=host,
        port=port,
        socket_connect_timeout=SOCKET_TIMEOUT_SECONDS,
        socket_timeout=SOCKET_TIMEOUT_SECONDS,
        retry=Retry(NoBackoff(), 0),
    )


class Cache:
    def __init__(self, client: Redis, ttl_seconds: int) -> None:
        self.client = client
        self.ttl_seconds = ttl_seconds

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

    async def tombstone(self, key: str) -> None:
        try:
            await self.client.set(key, TOMBSTONE, px=TOMBSTONE_TTL_MS)
        except RedisError:
            logger.error('cache invalidation failed: %s', key, exc_info=True)

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
        for key in self.pending:
            await self.cache.tombstone(key)
        self.pending.clear()
