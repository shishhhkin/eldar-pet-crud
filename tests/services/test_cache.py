import asyncio
import logging
import socket
import time
from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from redis.asyncio import Redis
from redis.asyncio.retry import Retry
from redis.backoff import NoBackoff
from redis.exceptions import RedisError

from src.infra import cache as cache_module
from src.infra.cache import TOMBSTONE, Cache, CacheSession, build_key
from tests.conftest import (
    CACHE_TTL_SECONDS,
    INVALIDATION_ATTEMPTS,
    REDIS_TIMEOUT_SECONDS,
    TOMBSTONE_TTL_MS,
)

LOGGER_NAME = 'src.infra.cache'

UNREACHABLE_TIMEOUT_SECONDS = 1.0
EXPIRED_TOMBSTONE_TTL_MS = 50
CONFIGURED_TOMBSTONE_TTL_MS = 5000


async def _raise_redis_error(*args: object, **kwargs: object) -> None:
    raise RedisError('redis is down')


def _records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [record for record in caplog.records if record.name == LOGGER_NAME]


def _closed_port() -> int:
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return int(sock.getsockname()[1])


@pytest.fixture
def short_tombstone_cache(redis_client: Redis) -> Cache:
    return Cache(redis_client, CACHE_TTL_SECONDS, EXPIRED_TOMBSTONE_TTL_MS, INVALIDATION_ATTEMPTS)


@pytest.fixture
async def unreachable_cache() -> AsyncIterator[Cache]:
    client = Redis(
        host='127.0.0.1',
        port=_closed_port(),
        socket_connect_timeout=REDIS_TIMEOUT_SECONDS,
        socket_timeout=REDIS_TIMEOUT_SECONDS,
        retry=Retry(NoBackoff(), 0),
    )
    yield Cache(client, CACHE_TTL_SECONDS, TOMBSTONE_TTL_MS, INVALIDATION_ATTEMPTS)
    await client.aclose()


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
    cache = Cache(redis_client, 42, TOMBSTONE_TTL_MS, INVALIDATION_ATTEMPTS)

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
    cache = Cache(
        redis_client, CACHE_TTL_SECONDS, CONFIGURED_TOMBSTONE_TTL_MS, INVALIDATION_ATTEMPTS
    )

    await cache.tombstone(key)

    pttl = await redis_client.pttl(key)
    assert CONFIGURED_TOMBSTONE_TTL_MS - 1000 < pttl <= CONFIGURED_TOMBSTONE_TTL_MS


async def test_add_fills_key_once_tombstone_expires(short_tombstone_cache: Cache) -> None:
    key = 'v1:author:expired'
    await short_tombstone_cache.tombstone(key)
    await asyncio.sleep(EXPIRED_TOMBSTONE_TTL_MS / 1000 * 2)

    await short_tombstone_cache.add(key, b'{"fresh": true}')

    assert await short_tombstone_cache.get(key) == b'{"fresh": true}'


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


async def test_get_on_unreachable_redis_fails_fast(
    unreachable_cache: Cache, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        started = time.monotonic()
        result = await unreachable_cache.get('v1:author:unreachable')
        elapsed = time.monotonic() - started

    assert result is None
    assert elapsed < UNREACHABLE_TIMEOUT_SECONDS
    assert _records(caplog)


async def test_tombstone_reports_success(cache: Cache) -> None:
    assert await cache.tombstone('v1:author:invalidated') is True


async def test_tombstone_on_redis_error_reports_failure_and_warns(
    cache: Cache,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(cache.client, 'set', _raise_redis_error)

    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        assert await cache.tombstone('v1:author:broken') is False

    records = _records(caplog)
    assert len(records) == INVALIDATION_ATTEMPTS
    assert all(record.levelno == logging.WARNING for record in records)


async def test_tombstone_retries_until_redis_answers(
    cache: Cache, redis_client: Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    key = 'v1:author:flaky'
    working_set = cache.client.set
    attempts = 0

    async def failing_once_set(*args: object, **kwargs: object) -> object:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RedisError('redis is down')
        return await working_set(*args, **kwargs)

    monkeypatch.setattr(cache.client, 'set', failing_once_set)

    assert await cache.tombstone(key) is True
    assert attempts == 2
    assert await redis_client.get(key) == TOMBSTONE


async def test_tombstone_gives_up_after_configured_attempts(
    redis_client: Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = Cache(redis_client, CACHE_TTL_SECONDS, TOMBSTONE_TTL_MS, 1)
    attempts = 0

    async def counting_failing_set(*args: object, **kwargs: object) -> None:
        nonlocal attempts
        attempts += 1
        raise RedisError('redis is down')

    monkeypatch.setattr(cache.client, 'set', counting_failing_set)

    assert await cache.tombstone('v1:author:broken') is False
    assert attempts == 1


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


async def test_apply_pending_logs_error_for_lost_invalidation(
    cache_session: CacheSession,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    key = 'v1:author:lost'
    monkeypatch.setattr(cache_session.cache.client, 'set', _raise_redis_error)
    cache_session.invalidate_after_commit(key)

    with caplog.at_level(logging.ERROR, logger=LOGGER_NAME):
        await cache_session.apply_pending()

    records = [record for record in _records(caplog) if record.levelno == logging.ERROR]
    assert len(records) == 1
    assert key in records[0].getMessage()
    assert cache_session.pending == []


async def test_apply_pending_logs_only_keys_that_were_not_invalidated(
    cache_session: CacheSession,
    redis_client: Redis,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    lost_key = 'v1:author:lost'
    kept_key = 'v1:author:kept'
    working_set = cache_session.cache.client.set

    async def set_failing_for_lost_key(key: str, *args: object, **kwargs: object) -> object:
        if key == lost_key:
            raise RedisError('redis is down')
        return await working_set(key, *args, **kwargs)

    monkeypatch.setattr(cache_session.cache.client, 'set', set_failing_for_lost_key)
    cache_session.invalidate_after_commit(lost_key)
    cache_session.invalidate_after_commit(kept_key)

    with caplog.at_level(logging.ERROR, logger=LOGGER_NAME):
        await cache_session.apply_pending()

    records = [record for record in _records(caplog) if record.levelno == logging.ERROR]
    assert len(records) == 1
    assert lost_key in records[0].getMessage()
    assert kept_key not in records[0].getMessage()
    assert await redis_client.get(kept_key) == TOMBSTONE
    assert await redis_client.get(lost_key) is None


async def test_apply_pending_stays_quiet_when_every_key_is_invalidated(
    cache_session: CacheSession, caplog: pytest.LogCaptureFixture
) -> None:
    cache_session.invalidate_after_commit('v1:author:fine')

    with caplog.at_level(logging.ERROR, logger=LOGGER_NAME):
        await cache_session.apply_pending()

    assert [record for record in _records(caplog) if record.levelno == logging.ERROR] == []


async def test_repeated_apply_pending_does_nothing(
    cache_session: CacheSession, redis_client: Redis
) -> None:
    key = 'v1:author:drained'
    cache_session.invalidate_after_commit(key)
    await cache_session.apply_pending()
    await redis_client.delete(key)

    await cache_session.apply_pending()

    assert await redis_client.exists(key) == 0
