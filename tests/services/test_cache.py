import logging
import socket
import time

import pytest
from redis.asyncio import Redis
from redis.exceptions import RedisError

from src.cache import Cache, build_client, settings

LOGGER_NAME = 'src.cache'

UNREACHABLE_TIMEOUT_SECONDS = 1.0


async def _raise_redis_error(*args: object, **kwargs: object) -> None:
    raise RedisError('redis is down')


def _records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [record for record in caplog.records if record.name == LOGGER_NAME]


def _closed_port() -> int:
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return int(sock.getsockname()[1])


async def test_get_missing_key_returns_none(cache: Cache) -> None:
    assert await cache.get('v1:author:missing') is None


async def test_set_stores_value_with_ttl(cache: Cache, redis_client: Redis) -> None:
    key = 'v1:author:stored'
    value = b'{"name": "\xd0\x9b\xd0\xb5\xd0\xbc"}'

    await cache.set(key, value)

    assert await cache.get(key) == value
    assert await redis_client.ttl(key) == settings.cache_ttl_seconds


async def test_set_ttl_follows_settings(
    cache: Cache,
    redis_client: Redis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    key = 'v1:author:ttl'
    monkeypatch.setattr(settings, 'cache_ttl_seconds', 42)

    await cache.set(key, b'{}')

    assert await redis_client.ttl(key) == 42


async def test_delete_removes_key(cache: Cache) -> None:
    key = 'v1:author:deleted'
    await cache.set(key, b'{}')

    await cache.delete(key)

    assert await cache.get(key) is None


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


async def test_set_on_redis_error_is_swallowed_and_warns(
    cache: Cache,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    key = 'v1:author:broken'
    monkeypatch.setattr(cache.client, 'set', _raise_redis_error)

    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        await cache.set(key, b'{}')

    monkeypatch.undo()
    assert await cache.get(key) is None

    records = _records(caplog)
    assert records
    assert all(record.levelno == logging.WARNING for record in records)


async def test_get_on_unreachable_redis_fails_fast(caplog: pytest.LogCaptureFixture) -> None:
    client = build_client('127.0.0.1', _closed_port())
    cache = Cache(client)

    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        started = time.monotonic()
        result = await cache.get('v1:author:unreachable')
        elapsed = time.monotonic() - started

    await client.aclose()

    assert result is None
    assert elapsed < UNREACHABLE_TIMEOUT_SECONDS
    assert _records(caplog)


async def test_delete_on_redis_error_is_swallowed_and_logs_error(
    cache: Cache,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(cache.client, 'delete', _raise_redis_error)

    with caplog.at_level(logging.ERROR, logger=LOGGER_NAME):
        await cache.delete('v1:author:broken')

    records = _records(caplog)
    assert records
    assert all(record.levelno == logging.ERROR for record in records)
