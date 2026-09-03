from uuid import uuid4

import pytest
from httpx import AsyncClient
from redis.asyncio import Redis

from src.services.author_service import AuthorService


def _author_payload() -> dict:
    return {'name': 'Лев Толстой', 'bio': 'русский писатель', 'books': [{'title': 'Война и мир'}]}


def _genre_payload() -> dict:
    return {'name': 'фантастика', 'moods': [{'name': 'грусть'}]}


def _user_payload() -> dict:
    return {
        'username': 'alice',
        'email': 'alice@example.com',
        'profile': {'avatar_url': 'https://example.com/a.png', 'bio': 'hello', 'socials': {}},
    }


async def _create(client: AsyncClient, path: str, payload: dict) -> str:
    response = await client.post(path, json=payload)
    assert response.status_code == 201
    return str(response.json()['id'])


async def test_entities_are_cached_under_separate_namespaces(
    client: AsyncClient, redis_client: Redis
) -> None:
    author_id = await _create(client, '/authors', _author_payload())
    genre_id = await _create(client, '/genres', _genre_payload())
    user_id = await _create(client, '/users', _user_payload())

    for path, obj_id in (('/authors', author_id), ('/genres', genre_id), ('/users', user_id)):
        assert (await client.get(f'{path}/{obj_id}')).status_code == 200

    assert set(await redis_client.keys('*')) == {
        f'v1:author:{author_id}'.encode(),
        f'v1:genre:{genre_id}'.encode(),
        f'v1:user:{user_id}'.encode(),
    }


async def test_cached_entity_is_not_served_for_another_entity_with_same_id(
    client: AsyncClient, redis_client: Redis
) -> None:
    author_id = await _create(client, '/authors', _author_payload())
    assert (await client.get(f'/authors/{author_id}')).status_code == 200

    assert (await client.get(f'/genres/{author_id}')).status_code == 404
    assert (await client.get(f'/users/{author_id}')).status_code == 404

    assert await redis_client.keys('*') == [f'v1:author:{author_id}'.encode()]


async def test_missing_entity_does_not_reuse_another_namespace(
    client: AsyncClient, redis_client: Redis
) -> None:
    obj_id = uuid4()
    await redis_client.set(f'v1:author:{obj_id}', b'{}')

    assert (await client.get(f'/genres/{obj_id}')).status_code == 404
    assert (await client.get(f'/users/{obj_id}')).status_code == 404


async def test_cache_key_is_independent_of_entity_name(
    client: AsyncClient, redis_client: Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(AuthorService, 'entity_name', 'Писатель')
    author_id = await _create(client, '/authors', _author_payload())

    assert (await client.get(f'/authors/{author_id}')).status_code == 200

    assert await redis_client.keys('*') == [f'v1:author:{author_id}'.encode()]


async def test_not_found_message_is_independent_of_cache_namespace(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(AuthorService, 'cache_namespace', 'writer')
    author_id = uuid4()

    response = await client.get(f'/authors/{author_id}')

    assert response.status_code == 404
    assert response.json()['detail'] == f'Author {author_id} not found'
