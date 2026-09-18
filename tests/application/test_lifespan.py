import asyncio
from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from testcontainers.community.postgres import PostgresContainer
from testcontainers.community.redis import RedisContainer

from src.application import get_app
from src.infra.cache import TOMBSTONE
from src.infra.db import tx_session
from src.repository import CacheInvalidationRepo
from tests.conftest import PauseRedisWrites, outbox_keys

FAST_RETRY_SECONDS = 0.05
WAIT_TIMEOUT_SECONDS = 5.0
SHUTDOWN_TIMEOUT_SECONDS = 2.0
NEW_NAME = 'Новое Имя'


@pytest.fixture(autouse=True)
def containers_env(
    monkeypatch: pytest.MonkeyPatch,
    postgres_container: PostgresContainer,
    redis_container: RedisContainer,
) -> None:
    monkeypatch.setenv('postgres_user', postgres_container.username)
    monkeypatch.setenv('postgres_password', postgres_container.password)
    monkeypatch.setenv('postgres_host', postgres_container.get_container_host_ip())
    monkeypatch.setenv('postgres_port', str(postgres_container.get_exposed_port(5432)))
    monkeypatch.setenv('postgres_db', postgres_container.dbname)
    monkeypatch.setenv('redis_host', redis_container.get_container_host_ip())
    monkeypatch.setenv('redis_port', str(redis_container.get_exposed_port(6379)))
    monkeypatch.setenv('cache_invalidation_retry_seconds', str(FAST_RETRY_SECONDS))


@pytest.fixture
def app() -> FastAPI:
    return get_app()


@pytest.fixture
async def running_client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test/v1') as client:
            yield client


async def _wait_until_outbox_is_empty(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with asyncio.timeout(WAIT_TIMEOUT_SECONDS):
        while await outbox_keys(session_factory):
            await asyncio.sleep(FAST_RETRY_SECONDS)


async def _create_author(client: AsyncClient) -> dict:
    response = await client.post('/authors', json={'name': 'Лев Толстой', 'books': []})
    assert response.status_code == 201
    return response.json()


async def test_started_app_serves_and_caches_requests(
    running_client: AsyncClient, redis_client: Redis
) -> None:
    created = await _create_author(running_client)

    response = await running_client.get(f'/authors/{created["id"]}')

    assert response.status_code == 200
    assert response.json() == created
    assert await redis_client.get(f'v1:author:{created["id"]}') is not None


async def test_invalidation_stored_before_startup_is_applied_after_start(
    app: FastAPI,
    redis_client: Redis,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    key = f'v1:author:{uuid4()}'
    await redis_client.set(key, b'{"stale": true}')
    async with tx_session(session_factory) as session:
        await CacheInvalidationRepo(session).add(key)

    async with app.router.lifespan_context(app):
        await _wait_until_outbox_is_empty(session_factory)

    assert await redis_client.get(key) == TOMBSTONE


async def test_worker_applies_invalidation_once_redis_accepts_writes(
    running_client: AsyncClient,
    redis_client: Redis,
    session_factory: async_sessionmaker[AsyncSession],
    pause_redis_writes: PauseRedisWrites,
) -> None:
    created = await _create_author(running_client)
    assert (await running_client.get(f'/authors/{created["id"]}')).status_code == 200

    await pause_redis_writes()
    updated = await running_client.patch(f'/authors/{created["id"]}', json={'name': NEW_NAME})
    assert updated.status_code == 200
    assert await outbox_keys(session_factory) != []

    await redis_client.client_unpause()
    await _wait_until_outbox_is_empty(session_factory)

    response = await running_client.get(f'/authors/{created["id"]}')
    assert response.json()['name'] == NEW_NAME


async def test_shutdown_completes_while_redis_rejects_invalidations(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
    pause_redis_writes: PauseRedisWrites,
) -> None:
    key = f'v1:author:{uuid4()}'
    async with tx_session(session_factory) as session:
        await CacheInvalidationRepo(session).add(key)
    await pause_redis_writes()

    async with asyncio.timeout(SHUTDOWN_TIMEOUT_SECONDS):
        async with app.router.lifespan_context(app):
            await asyncio.sleep(FAST_RETRY_SECONDS * 2)

    assert await outbox_keys(session_factory) == [key]
