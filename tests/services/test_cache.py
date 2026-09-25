import asyncio
import logging
import time
from uuid import uuid4

import pytest
from redis.asyncio import Redis

from src.infra import cache as cache_module
from src.infra.cache import TOMBSTONE, Cache, build_key
from tests.conftest import CACHE_TTL_SECONDS, TOMBSTONE_TTL_MS, PauseRedisWrites

LOGGER_NAME = 'src.infra.cache'

UNREACHABLE_TIMEOUT_SECONDS = 1.0
EXPIRED_TOMBSTONE_TTL_MS = 50
CONFIGURED_TOMBSTONE_TTL_MS = 5000


def _records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [record for record in caplog.records if record.name == LOGGER_NAME]


def _only_warnings(caplog: pytest.LogCaptureFixture) -> bool:
    records = _records(caplog)
    return bool(records) and all(record.levelno == logging.WARNING for record in records)


def test_build_key_joins_version_namespace_and_id() -> None:
    obj_id = uuid4()

    assert build_key('author', obj_id) == f'{cache_module.KEY_VERSION}:author:{obj_id}'


def test_build_key_keeps_namespaces_apart_for_one_id() -> None:
    obj_id = uuid4()

    assert build_key('author', obj_id) != build_key('genre', obj_id)


async def test_get_missing_key_returns_none(cache: Cache) -> None:
    assert await cache.get('v1:author:missing') is None


async def test_add_stores_value_with_ttl(cache: Cache, redis_client: Redis) -> None:
    key = 'v1:author:stored'
    value = b'{"name": "\xd0\x9b\xd0\xb5\xd0\xbc"}'

    await cache.add(key, value)

    assert await cache.get(key) == value
    assert await redis_client.ttl(key) == CACHE_TTL_SECONDS


async def test_add_ttl_follows_configured_value(redis_client: Redis) -> None:
    key = 'v1:author:ttl'
    cache = Cache(redis_client, 42, TOMBSTONE_TTL_MS)

    await cache.add(key, b'{}')

    assert await redis_client.ttl(key) == 42


async def test_add_keeps_already_cached_value(cache: Cache) -> None:
    key = 'v1:author:existing'
    await cache.add(key, b'{"first": true}')

    await cache.add(key, b'{"second": true}')

    assert await cache.get(key) == b'{"first": true}'


async def test_tombstone_replaces_cached_value(cache: Cache, redis_client: Redis) -> None:
    key = 'v1:author:invalidated'
    await cache.add(key, b'{}')

    assert await cache.tombstone(key) is True

    assert await redis_client.get(key) == TOMBSTONE
    assert await cache.get(key) is None
    assert 0 < await redis_client.pttl(key) <= TOMBSTONE_TTL_MS


async def test_get_treats_raw_tombstone_as_miss(cache: Cache, redis_client: Redis) -> None:
    key = 'v1:author:tombstoned'
    await redis_client.set(key, TOMBSTONE)

    assert await cache.get(key) is None


async def test_add_does_not_overwrite_live_tombstone(cache: Cache, redis_client: Redis) -> None:
    key = 'v1:author:racing'
    await cache.tombstone(key)

    await cache.add(key, b'{"stale": true}')

    assert await redis_client.get(key) == TOMBSTONE
    assert await cache.get(key) is None


async def test_tombstone_ttl_follows_configured_value(redis_client: Redis) -> None:
    key = 'v1:author:tombstone-ttl'
    cache = Cache(redis_client, CACHE_TTL_SECONDS, CONFIGURED_TOMBSTONE_TTL_MS)

    await cache.tombstone(key)

    pttl = await redis_client.pttl(key)
    assert CONFIGURED_TOMBSTONE_TTL_MS - 1000 < pttl <= CONFIGURED_TOMBSTONE_TTL_MS


async def test_add_fills_key_once_tombstone_expires(redis_client: Redis) -> None:
    key = 'v1:author:expired'
    cache = Cache(redis_client, CACHE_TTL_SECONDS, EXPIRED_TOMBSTONE_TTL_MS)
    await cache.tombstone(key)
    await asyncio.sleep(EXPIRED_TOMBSTONE_TTL_MS / 1000 * 2)

    await cache.add(key, b'{"fresh": true}')

    assert await cache.get(key) == b'{"fresh": true}'


async def test_delete_removes_key(cache: Cache, redis_client: Redis) -> None:
    key = 'v1:author:discarded'
    await cache.add(key, b'{}')

    await cache.delete(key)

    assert await redis_client.exists(key) == 0


async def test_get_on_unreachable_redis_fails_fast_and_warns(
    unreachable_cache: Cache, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        started = time.monotonic()
        result = await unreachable_cache.get('v1:author:unreachable')
        elapsed = time.monotonic() - started

    assert result is None
    assert elapsed < UNREACHABLE_TIMEOUT_SECONDS
    assert _only_warnings(caplog)


async def test_add_on_unreachable_redis_is_swallowed_and_warns(
    unreachable_cache: Cache, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        await unreachable_cache.add('v1:author:unreachable', b'{}')

    assert _only_warnings(caplog)


async def test_delete_on_unreachable_redis_is_swallowed_and_warns(
    unreachable_cache: Cache, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        await unreachable_cache.delete('v1:author:unreachable')

    assert _only_warnings(caplog)


async def test_tombstone_on_unreachable_redis_reports_failure_once(
    unreachable_cache: Cache, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        assert await unreachable_cache.tombstone('v1:author:unreachable') is False

    assert _only_warnings(caplog)
    assert len(_records(caplog)) == 1


async def test_add_while_redis_rejects_writes_keeps_key_absent(
    cache: Cache, redis_client: Redis, pause_redis_writes: PauseRedisWrites
) -> None:
    key = 'v1:author:paused'
    await pause_redis_writes()

    await cache.add(key, b'{}')
    await redis_client.client_unpause()

    assert await redis_client.exists(key) == 0


async def test_tombstone_while_redis_rejects_writes_keeps_cached_value(
    cache: Cache, redis_client: Redis, pause_redis_writes: PauseRedisWrites
) -> None:
    key = 'v1:author:paused'
    await cache.add(key, b'{"cached": true}')
    await pause_redis_writes()

    assert await cache.tombstone(key) is False
    await redis_client.client_unpause()

    assert await cache.get(key) == b'{"cached": true}'
