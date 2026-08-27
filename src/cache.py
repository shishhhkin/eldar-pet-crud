import logging
from typing import cast

from redis.asyncio import Redis
from redis.asyncio.retry import Retry
from redis.backoff import NoBackoff
from redis.exceptions import RedisError

from src.config import Settings

logger = logging.getLogger(__name__)

settings = Settings()  # type: ignore[call-arg]

SOCKET_TIMEOUT_SECONDS = 0.5


def build_client(host: str, port: int) -> Redis:
    return Redis(
        host=host,
        port=port,
        socket_connect_timeout=SOCKET_TIMEOUT_SECONDS,
        socket_timeout=SOCKET_TIMEOUT_SECONDS,
        retry=Retry(NoBackoff(), 0),
    )


class Cache:
    def __init__(self, client: Redis) -> None:
        self.client = client

    async def get(self, key: str) -> bytes | None:
        try:
            return cast('bytes | None', await self.client.get(key))
        except RedisError:
            logger.warning('cache read failed: %s', key, exc_info=True)
            return None

    async def set(self, key: str, value: bytes) -> None:
        try:
            await self.client.set(key, value, ex=settings.cache_ttl_seconds)
        except RedisError:
            logger.warning('cache write failed: %s', key, exc_info=True)

    async def delete(self, key: str) -> None:
        try:
            await self.client.delete(key)
        except RedisError:
            logger.error('cache invalidation failed: %s', key, exc_info=True)


client: Redis = build_client(settings.redis_host, settings.redis_port)

cache = Cache(client)


async def close_cache() -> None:
    await client.aclose()
