import socket
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from contextlib import asynccontextmanager
from functools import partial

import pytest
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from redis.asyncio.retry import Retry
from redis.backoff import NoBackoff
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.community.postgres import PostgresContainer
from testcontainers.community.redis import RedisContainer

from src.application import get_app
from src.infra.cache import Cache
from src.infra.invalidation import InvalidationOutbox
from src.models import Base, cache_invalidations

CACHE_TTL_SECONDS = 60
TOMBSTONE_TTL_MS = 2000
REDIS_TIMEOUT_SECONDS = 0.5
REDIS_PAUSE_SAFETY_MS = 30_000
INVALIDATION_BATCH_SIZE = 100
INVALIDATION_RETRY_SECONDS = 0.05
INVALIDATION_LEASE_SECONDS = 60


def closed_port() -> int:
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return int(sock.getsockname()[1])


@pytest.fixture(scope='session')
def postgres_container() -> Iterator[PostgresContainer]:
    with PostgresContainer('postgres:17-alpine', driver='asyncpg') as container:
        yield container


@pytest.fixture(scope='session')
async def engine(postgres_container: PostgresContainer) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(postgres_container.get_connection_url(), pool_pre_ping=True)
    yield engine
    await engine.dispose()


@pytest.fixture(scope='session')
def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(autouse=True)
async def prepare_schema(engine: AsyncEngine) -> AsyncIterator[None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest.fixture(scope='session')
def redis_container() -> Iterator[RedisContainer]:
    with RedisContainer('redis:8-alpine') as container:
        yield container


@pytest.fixture(scope='session')
async def redis_client(redis_container: RedisContainer) -> AsyncIterator[Redis]:
    client = Redis(
        host=redis_container.get_container_host_ip(),
        port=int(redis_container.get_exposed_port(6379)),
        socket_connect_timeout=REDIS_TIMEOUT_SECONDS,
        socket_timeout=REDIS_TIMEOUT_SECONDS,
        retry=Retry(NoBackoff(), 0),
    )
    yield client
    await client.aclose()


@pytest.fixture(autouse=True)
async def flush_redis(redis_client: Redis) -> AsyncIterator[None]:
    await redis_client.flushdb()
    yield


@pytest.fixture
def cache(redis_client: Redis) -> Cache:
    return Cache(redis_client, CACHE_TTL_SECONDS, TOMBSTONE_TTL_MS)


@pytest.fixture
async def unreachable_cache() -> AsyncIterator[Cache]:
    client = Redis(
        host='127.0.0.1',
        port=closed_port(),
        socket_connect_timeout=REDIS_TIMEOUT_SECONDS,
        socket_timeout=REDIS_TIMEOUT_SECONDS,
        retry=Retry(NoBackoff(), 0),
    )
    yield Cache(client, CACHE_TTL_SECONDS, TOMBSTONE_TTL_MS)
    await client.aclose()


type PauseRedisWrites = Callable[[], Awaitable[object]]


@pytest.fixture
async def pause_redis_writes(redis_client: Redis) -> AsyncIterator[PauseRedisWrites]:
    yield partial(redis_client.client_pause, REDIS_PAUSE_SAFETY_MS, all=False)
    await redis_client.client_unpause()


def _outbox(session_factory: async_sessionmaker[AsyncSession], cache: Cache) -> InvalidationOutbox:
    return InvalidationOutbox(
        session_factory,
        cache,
        INVALIDATION_BATCH_SIZE,
        INVALIDATION_RETRY_SECONDS,
        INVALIDATION_LEASE_SECONDS,
    )


@pytest.fixture
def outbox(session_factory: async_sessionmaker[AsyncSession], cache: Cache) -> InvalidationOutbox:
    return _outbox(session_factory, cache)


@asynccontextmanager
async def _client(
    session_factory: async_sessionmaker[AsyncSession], cache: Cache
) -> AsyncIterator[AsyncClient]:
    app = get_app()
    app.state.session_factory = session_factory
    app.state.cache = cache
    app.state.outbox = _outbox(session_factory, cache)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test/v1') as ac:
        yield ac


@pytest.fixture
async def client(
    session_factory: async_sessionmaker[AsyncSession], cache: Cache
) -> AsyncIterator[AsyncClient]:
    async with _client(session_factory, cache) as ac:
        yield ac


@pytest.fixture
async def unreachable_client(
    session_factory: async_sessionmaker[AsyncSession], unreachable_cache: Cache
) -> AsyncIterator[AsyncClient]:
    async with _client(session_factory, unreachable_cache) as ac:
        yield ac


async def outbox_keys(session_factory: async_sessionmaker[AsyncSession]) -> list[str]:
    async with session_factory() as session:
        stmt = select(cache_invalidations.c.key).order_by(cache_invalidations.c.id)
        return list((await session.execute(stmt)).scalars().all())


@pytest.fixture
async def db_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session
