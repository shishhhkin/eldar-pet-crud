import logging
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from src.infra.cache import TOMBSTONE
from src.models.genres import GenreModel
from src.schemas.genres import GenreRead

SERVICE_LOGGER = 'src.services.base'
NEW_NAME = 'роман'


def _payload() -> dict:
    return {'name': 'фантастика', 'moods': [{'name': 'грусть'}, {'name': 'надежда'}]}


def _key(genre_id: str) -> str:
    return f'v1:genre:{genre_id}'


async def _create_genre(client: AsyncClient) -> dict:
    response = await client.post('/genres', json=_payload())
    assert response.status_code == 201
    return response.json()


async def test_cold_get_stores_response_in_cache(client: AsyncClient, redis_client: Redis) -> None:
    created = await _create_genre(client)

    response = await client.get(f'/genres/{created["id"]}')

    assert response.status_code == 200
    raw = await redis_client.get(_key(created['id']))
    assert raw is not None
    cached = GenreRead.model_validate_json(raw)
    assert cached == GenreRead.model_validate(response.json())
    assert [mood.name for mood in cached.moods] == ['грусть', 'надежда']


async def test_repeated_get_is_served_from_cache(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    created = await _create_genre(client)
    first = await client.get(f'/genres/{created["id"]}')
    assert first.status_code == 200

    await db_session.execute(
        update(GenreModel).where(GenreModel.id == UUID(created['id'])).values(name=NEW_NAME)
    )
    await db_session.commit()

    second = await client.get(f'/genres/{created["id"]}')

    assert second.status_code == 200
    assert second.json() == first.json()
    assert second.json()['moods'] == created['moods']


async def test_missing_genre_is_not_cached(client: AsyncClient, redis_client: Redis) -> None:
    genre_id = uuid4()

    response = await client.get(f'/genres/{genre_id}')

    assert response.status_code == 404
    assert await redis_client.keys('v1:genre:*') == []


async def test_unusable_cached_payload_is_overwritten(
    client: AsyncClient,
    redis_client: Redis,
    caplog: pytest.LogCaptureFixture,
) -> None:
    created = await _create_genre(client)
    key = _key(created['id'])
    await redis_client.set(key, b'{"foo": 1}')

    with caplog.at_level(logging.WARNING, logger=SERVICE_LOGGER):
        response = await client.get(f'/genres/{created["id"]}')

    assert response.status_code == 200
    assert response.json() == created

    records = [record for record in caplog.records if record.name == SERVICE_LOGGER]
    assert records
    assert all(record.levelno == logging.WARNING for record in records)

    raw = await redis_client.get(key)
    assert raw is not None
    assert GenreRead.model_validate_json(raw) == GenreRead.model_validate(response.json())


async def test_update_invalidates_cached_genre(client: AsyncClient, redis_client: Redis) -> None:
    created = await _create_genre(client)
    await client.get(f'/genres/{created["id"]}')

    updated = await client.patch(
        f'/genres/{created["id"]}', json={'name': NEW_NAME, 'moods': [{'name': 'радость'}]}
    )
    assert updated.status_code == 200
    assert await redis_client.get(_key(created['id'])) == TOMBSTONE

    response = await client.get(f'/genres/{created["id"]}')

    assert response.status_code == 200
    assert response.json()['name'] == NEW_NAME
    assert [mood['name'] for mood in response.json()['moods']] == ['радость']


async def test_delete_invalidates_cached_genre(client: AsyncClient, redis_client: Redis) -> None:
    created = await _create_genre(client)
    await client.get(f'/genres/{created["id"]}')

    deleted = await client.delete(f'/genres/{created["id"]}')
    assert deleted.status_code == 204
    assert await redis_client.get(_key(created['id'])) == TOMBSTONE

    response = await client.get(f'/genres/{created["id"]}')

    assert response.status_code == 404


async def test_create_does_not_touch_cache(client: AsyncClient, redis_client: Redis) -> None:
    await _create_genre(client)

    assert await redis_client.keys('*') == []
