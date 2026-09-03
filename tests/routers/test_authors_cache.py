import logging
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.exceptions import NotFoundError
from src.infra.cache import TOMBSTONE, Cache, CacheSession
from src.infra.db import readonly_session
from src.infra.unit_of_work import invalidating_tx_session
from src.models.authors import AuthorModel
from src.repository import AuthorRepo, Repo
from src.schemas.authors import AuthorRead, AuthorUpdate
from src.services.author_service import AuthorService

CACHE_LOGGER = 'src.infra.cache'
SERVICE_LOGGER = 'src.services.base'
NEW_NAME = 'Новое Имя'


def _payload() -> dict:
    return {
        'name': 'Лев Толстой',
        'bio': 'русский писатель',
        'books': [{'title': 'Война и мир'}],
    }


def _key(author_id: str) -> str:
    return f'v1:author:{author_id}'


async def _create_author(client: AsyncClient) -> dict:
    response = await client.post('/authors', json=_payload())
    assert response.status_code == 201
    return response.json()


async def _forbidden_repo_get(*args: object, **kwargs: object) -> None:
    raise AssertionError('repository must not be queried on a cache hit')


async def _raise_redis_error(*args: object, **kwargs: object) -> None:
    raise RedisError('redis is down')


def _records(caplog: pytest.LogCaptureFixture, logger_name: str) -> list[logging.LogRecord]:
    return [record for record in caplog.records if record.name == logger_name]


async def test_cold_get_stores_response_in_cache(client: AsyncClient, redis_client: Redis) -> None:
    created = await _create_author(client)

    response = await client.get(f'/authors/{created["id"]}')

    assert response.status_code == 200
    raw = await redis_client.get(_key(created['id']))
    assert raw is not None
    assert AuthorRead.model_validate_json(raw) == AuthorRead.model_validate(response.json())


async def test_repeated_get_is_served_without_database(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = await _create_author(client)
    first = await client.get(f'/authors/{created["id"]}')
    assert first.status_code == 200

    monkeypatch.setattr(Repo, 'get', _forbidden_repo_get)
    second = await client.get(f'/authors/{created["id"]}')

    assert second.status_code == 200
    assert second.json() == first.json()


async def test_missing_author_is_not_cached(client: AsyncClient, redis_client: Redis) -> None:
    author_id = uuid4()

    response = await client.get(f'/authors/{author_id}')

    assert response.status_code == 404
    assert await redis_client.get(_key(str(author_id))) is None
    assert await redis_client.keys('v1:author:*') == []


async def test_get_falls_back_to_database_when_redis_fails(
    client: AsyncClient,
    cache: Cache,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    created = await _create_author(client)
    monkeypatch.setattr(cache.client, 'get', _raise_redis_error)
    monkeypatch.setattr(cache.client, 'set', _raise_redis_error)

    with caplog.at_level(logging.WARNING, logger=CACHE_LOGGER):
        response = await client.get(f'/authors/{created["id"]}')

    assert response.status_code == 200
    assert response.json() == created

    records = _records(caplog, CACHE_LOGGER)
    assert records
    assert all(record.levelno == logging.WARNING for record in records)


async def test_unusable_cached_payload_is_overwritten(
    client: AsyncClient,
    redis_client: Redis,
    caplog: pytest.LogCaptureFixture,
) -> None:
    created = await _create_author(client)
    key = _key(created['id'])
    await redis_client.set(key, b'{"foo": 1}')

    with caplog.at_level(logging.WARNING, logger=SERVICE_LOGGER):
        response = await client.get(f'/authors/{created["id"]}')

    assert response.status_code == 200
    assert response.json() == created

    records = _records(caplog, SERVICE_LOGGER)
    assert records
    assert all(record.levelno == logging.WARNING for record in records)

    raw = await redis_client.get(key)
    assert raw is not None
    assert AuthorRead.model_validate_json(raw) == AuthorRead.model_validate(response.json())


async def test_update_invalidates_cached_author(client: AsyncClient, redis_client: Redis) -> None:
    created = await _create_author(client)
    await client.get(f'/authors/{created["id"]}')

    updated = await client.patch(f'/authors/{created["id"]}', json={'name': NEW_NAME})
    assert updated.status_code == 200
    assert await redis_client.get(_key(created['id'])) == TOMBSTONE

    response = await client.get(f'/authors/{created["id"]}')

    assert response.status_code == 200
    assert response.json()['name'] == NEW_NAME


async def test_delete_invalidates_cached_author(client: AsyncClient, redis_client: Redis) -> None:
    created = await _create_author(client)
    await client.get(f'/authors/{created["id"]}')

    deleted = await client.delete(f'/authors/{created["id"]}')
    assert deleted.status_code == 204
    assert await redis_client.get(_key(created['id'])) == TOMBSTONE

    response = await client.get(f'/authors/{created["id"]}')

    assert response.status_code == 404


async def test_create_does_not_touch_cache(client: AsyncClient, redis_client: Redis) -> None:
    await _create_author(client)

    assert await redis_client.keys('*') == []


async def test_key_is_invalidated_after_commit(
    client: AsyncClient,
    cache: Cache,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = await _create_author(client)
    await client.get(f'/authors/{created["id"]}')
    stored_names: list[str | None] = []
    tombstone = cache.tombstone

    async def recording_tombstone(key: str) -> None:
        async with session_factory() as session:
            stored_names.append(
                await session.scalar(
                    select(AuthorModel.name).where(AuthorModel.id == UUID(created['id']))
                )
            )
        await tombstone(key)

    monkeypatch.setattr(cache, 'tombstone', recording_tombstone)

    response = await client.patch(f'/authors/{created["id"]}', json={'name': NEW_NAME})

    assert response.status_code == 200
    assert stored_names == [NEW_NAME]


async def test_failed_update_does_not_invalidate(
    session_factory: async_sessionmaker[AsyncSession],
    cache_session: CacheSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invalidated_keys: list[str] = []

    async def recording_tombstone(key: str) -> None:
        invalidated_keys.append(key)

    monkeypatch.setattr(cache_session.cache, 'tombstone', recording_tombstone)

    with pytest.raises(NotFoundError):
        async with invalidating_tx_session(session_factory, cache_session) as session:
            service = AuthorService(AuthorRepo(session), cache_session)
            await service.update(uuid4(), AuthorUpdate(name=NEW_NAME))

    assert invalidated_keys == []
    assert cache_session.pending == []


async def test_concurrent_get_does_not_restore_stale_value(
    client: AsyncClient,
    cache_session: CacheSession,
    session_factory: async_sessionmaker[AsyncSession],
    redis_client: Redis,
) -> None:
    created = await _create_author(client)
    key = _key(created['id'])

    async with readonly_session(session_factory) as session:
        stale = await AuthorRepo(session).get(UUID(created['id']), *AuthorService.load_options)
        stale_payload = AuthorRead.model_validate(stale).model_dump_json().encode()

    updated = await client.patch(f'/authors/{created["id"]}', json={'name': NEW_NAME})
    assert updated.status_code == 200

    await cache_session.add(key, stale_payload)

    assert await redis_client.get(key) == TOMBSTONE
    assert await cache_session.get(key) is None
