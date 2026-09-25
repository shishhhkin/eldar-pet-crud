import logging
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from src.infra.cache import TOMBSTONE
from src.models.users import UserModel
from src.schemas.users import UserRead

SERVICE_LOGGER = 'src.services.base'
NEW_USERNAME = 'bob'


def _payload() -> dict:
    return {
        'username': 'alice',
        'email': 'alice@example.com',
        'profile': {
            'avatar_url': 'https://example.com/a.png',
            'bio': 'hello',
            'socials': {'tg': '@alice'},
        },
    }


def _key(user_id: str) -> str:
    return f'v1:user:{user_id}'


async def _create_user(client: AsyncClient) -> dict:
    response = await client.post('/users', json=_payload())
    assert response.status_code == 201
    return response.json()


async def test_cold_get_stores_response_in_cache(client: AsyncClient, redis_client: Redis) -> None:
    created = await _create_user(client)

    response = await client.get(f'/users/{created["id"]}')

    assert response.status_code == 200
    raw = await redis_client.get(_key(created['id']))
    assert raw is not None
    assert UserRead.model_validate_json(raw) == UserRead.model_validate(response.json())


async def test_repeated_get_is_served_from_cache(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    created = await _create_user(client)
    first = await client.get(f'/users/{created["id"]}')
    assert first.status_code == 200
    assert first.json()['profile']['socials'] == {'tg': '@alice'}

    await db_session.execute(
        update(UserModel).where(UserModel.id == UUID(created['id'])).values(username=NEW_USERNAME)
    )
    await db_session.commit()

    second = await client.get(f'/users/{created["id"]}')

    assert second.status_code == 200
    assert second.json() == first.json()


async def test_missing_user_is_not_cached(client: AsyncClient, redis_client: Redis) -> None:
    user_id = uuid4()

    response = await client.get(f'/users/{user_id}')

    assert response.status_code == 404
    assert await redis_client.keys('v1:user:*') == []


async def test_unusable_cached_payload_is_overwritten(
    client: AsyncClient,
    redis_client: Redis,
    caplog: pytest.LogCaptureFixture,
) -> None:
    created = await _create_user(client)
    key = _key(created['id'])
    await redis_client.set(key, b'{"foo": 1}')

    with caplog.at_level(logging.WARNING, logger=SERVICE_LOGGER):
        response = await client.get(f'/users/{created["id"]}')

    assert response.status_code == 200
    assert response.json() == created

    records = [record for record in caplog.records if record.name == SERVICE_LOGGER]
    assert records
    assert all(record.levelno == logging.WARNING for record in records)

    raw = await redis_client.get(key)
    assert raw is not None
    assert UserRead.model_validate_json(raw) == UserRead.model_validate(response.json())


async def test_update_invalidates_cached_user(client: AsyncClient, redis_client: Redis) -> None:
    created = await _create_user(client)
    await client.get(f'/users/{created["id"]}')

    updated = await client.patch(f'/users/{created["id"]}', json={'username': NEW_USERNAME})
    assert updated.status_code == 200
    assert await redis_client.get(_key(created['id'])) == TOMBSTONE

    response = await client.get(f'/users/{created["id"]}')

    assert response.status_code == 200
    assert response.json()['username'] == NEW_USERNAME


async def test_delete_invalidates_cached_user(client: AsyncClient, redis_client: Redis) -> None:
    created = await _create_user(client)
    await client.get(f'/users/{created["id"]}')

    deleted = await client.delete(f'/users/{created["id"]}')
    assert deleted.status_code == 204
    assert await redis_client.get(_key(created['id'])) == TOMBSTONE

    response = await client.get(f'/users/{created["id"]}')

    assert response.status_code == 404


async def test_create_does_not_touch_cache(client: AsyncClient, redis_client: Redis) -> None:
    await _create_user(client)

    assert await redis_client.keys('*') == []
