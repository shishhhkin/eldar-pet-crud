import logging
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.infra.cache import TOMBSTONE, Cache
from src.infra.db import readonly_session
from src.models.authors import AuthorModel
from src.repository import AuthorRepo
from src.schemas.authors import AuthorRead
from tests.conftest import outbox_keys

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


def _records(caplog: pytest.LogCaptureFixture, logger_name: str) -> list[logging.LogRecord]:
    return [record for record in caplog.records if record.name == logger_name]


async def test_cold_get_stores_response_in_cache(client: AsyncClient, redis_client: Redis) -> None:
    created = await _create_author(client)

    response = await client.get(f'/authors/{created["id"]}')

    assert response.status_code == 200
    raw = await redis_client.get(_key(created['id']))
    assert raw is not None
    assert AuthorRead.model_validate_json(raw) == AuthorRead.model_validate(response.json())


async def test_repeated_get_is_served_from_cache(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    created = await _create_author(client)
    first = await client.get(f'/authors/{created["id"]}')
    assert first.status_code == 200

    await db_session.execute(
        update(AuthorModel).where(AuthorModel.id == UUID(created['id'])).values(name=NEW_NAME)
    )
    await db_session.commit()

    second = await client.get(f'/authors/{created["id"]}')

    assert second.status_code == 200
    assert second.json() == first.json()
    assert second.json()['name'] != NEW_NAME


async def test_missing_author_is_not_cached(client: AsyncClient, redis_client: Redis) -> None:
    author_id = uuid4()

    response = await client.get(f'/authors/{author_id}')

    assert response.status_code == 404
    assert await redis_client.get(_key(str(author_id))) is None
    assert await redis_client.keys('v1:author:*') == []


async def test_get_falls_back_to_database_when_redis_is_unreachable(
    unreachable_client: AsyncClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    created = await _create_author(unreachable_client)

    with caplog.at_level(logging.WARNING, logger=CACHE_LOGGER):
        response = await unreachable_client.get(f'/authors/{created["id"]}')

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


async def test_failed_update_does_not_invalidate(
    client: AsyncClient,
    redis_client: Redis,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    response = await client.patch(f'/authors/{uuid4()}', json={'name': NEW_NAME})

    assert response.status_code == 404
    assert await redis_client.keys('*') == []
    assert await outbox_keys(session_factory) == []


async def test_concurrent_get_does_not_restore_stale_value(
    client: AsyncClient,
    cache: Cache,
    session_factory: async_sessionmaker[AsyncSession],
    redis_client: Redis,
) -> None:
    created = await _create_author(client)
    key = _key(created['id'])

    async with readonly_session(session_factory) as session:
        stale = await AuthorRepo(session).get_with_relations(UUID(created['id']))
        stale_payload = AuthorRead.model_validate(stale).model_dump_json().encode()

    updated = await client.patch(f'/authors/{created["id"]}', json={'name': NEW_NAME})
    assert updated.status_code == 200

    await cache.add(key, stale_payload)

    assert await redis_client.get(key) == TOMBSTONE
    assert await cache.get(key) is None
