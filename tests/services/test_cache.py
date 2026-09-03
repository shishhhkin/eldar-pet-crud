import asyncio
import logging
import socket
import time
from uuid import uuid4

import pytest
from redis.asyncio import Redis
from redis.exceptions import RedisError

from src.infra import cache as cache_module
from src.infra.cache import TOMBSTONE, Cache, CacheSession, build_client, build_key
from tests.conftest import CACHE_TTL_SECONDS

LOGGER_NAME = 'src.infra.cache'

UNREACHABLE_TIMEOUT_SECONDS = 1.0
EXPIRED_TOMBSTONE_TTL_MS = 50


async def _raise_redis_error(*args: object, **kwargs: object) -> None:
    raise RedisError('redis is down')


def _records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [record for record in caplog.records if record.name == LOGGER_NAME]


def _closed_port() -> int:
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return int(sock.getsockname()[1])


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
    cache = Cache(redis_client, 42)

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

    await cache.tombstone(key)

    assert await redis_client.get(key) == TOMBSTONE
    assert await cache.get(key) is None
    assert 0 < await redis_client.pttl(key) <= cache_module.TOMBSTONE_TTL_MS


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


async def test_add_fills_key_once_tombstone_expires(
    cache: Cache, monkeypatch: pytest.MonkeyPatch
) -> None:
    key = 'v1:author:expired'
    monkeypatch.setattr(cache_module, 'TOMBSTONE_TTL_MS', EXPIRED_TOMBSTONE_TTL_MS)
    await cache.tombstone(key)
    await asyncio.sleep(EXPIRED_TOMBSTONE_TTL_MS / 1000 * 2)

    await cache.add(key, b'{"fresh": true}')

    assert await cache.get(key) == b'{"fresh": true}'


async def test_delete_removes_key(cache: Cache, redis_client: Redis) -> None:
    key = 'v1:author:discarded'
    await cache.add(key, b'{}')

    await cache.delete(key)

    assert await redis_client.exists(key) == 0


async def test_get_on_redis_error_returns_none_and_warns(
    cache: Cache,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(cache.client, 'get', _raise_redis_error)

    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        assert await cache.get('v1:author:broken') is None

    records = _records(caplog)
    assert records
    assert all(record.levelno == logging.WARNING for record in records)


async def test_add_on_redis_error_is_swallowed_and_warns(
    cache: Cache,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    key = 'v1:author:broken'
    monkeypatch.setattr(cache.client, 'set', _raise_redis_error)

    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        await cache.add(key, b'{}')

    monkeypatch.undo()
    assert await cache.get(key) is None

    records = _records(caplog)
    assert records
    assert all(record.levelno == logging.WARNING for record in records)


async def test_get_on_unreachable_redis_fails_fast(caplog: pytest.LogCaptureFixture) -> None:
    client = build_client('127.0.0.1', _closed_port())
    cache = Cache(client, CACHE_TTL_SECONDS)

    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        started = time.monotonic()
        result = await cache.get('v1:author:unreachable')
        elapsed = time.monotonic() - started

    await client.aclose()

    assert result is None
    assert elapsed < UNREACHABLE_TIMEOUT_SECONDS
    assert _records(caplog)


async def test_tombstone_on_redis_error_is_swallowed_and_logs_error(
    cache: Cache,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(cache.client, 'set', _raise_redis_error)

    with caplog.at_level(logging.ERROR, logger=LOGGER_NAME):
        await cache.tombstone('v1:author:broken')

    records = _records(caplog)
    assert records
    assert all(record.levelno == logging.ERROR for record in records)


async def test_delete_on_redis_error_is_swallowed_and_warns(
    cache: Cache,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(cache.client, 'delete', _raise_redis_error)

    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        await cache.delete('v1:author:broken')

    records = _records(caplog)
    assert records
    assert all(record.levelno == logging.WARNING for record in records)


async def test_scheduled_key_is_not_invalidated_before_apply(
    cache_session: CacheSession, redis_client: Redis
) -> None:
    key = 'v1:author:deferred'
    await cache_session.add(key, b'{}')

    cache_session.invalidate_after_commit(key)

    assert await redis_client.get(key) == b'{}'
    assert cache_session.pending == [key]


async def test_apply_pending_tombstones_every_scheduled_key(
    cache_session: CacheSession, redis_client: Redis
) -> None:
    keys = ['v1:author:1', 'v1:author:2']
    for key in keys:
        cache_session.invalidate_after_commit(key)

    await cache_session.apply_pending()

    assert [await redis_client.get(key) for key in keys] == [TOMBSTONE, TOMBSTONE]
    assert cache_session.pending == []


async def test_repeated_apply_pending_does_nothing(
    cache_session: CacheSession, redis_client: Redis
) -> None:
    key = 'v1:author:drained'
    cache_session.invalidate_after_commit(key)
    await cache_session.apply_pending()
    await redis_client.delete(key)

    await cache_session.apply_pending()

    assert await redis_client.exists(key) == 0
