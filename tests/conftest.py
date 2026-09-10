from collections.abc import AsyncIterator, Iterator

import pytest
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from redis.asyncio.retry import Retry
from redis.backoff import NoBackoff
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.community.postgres import PostgresContainer
from testcontainers.community.redis import RedisContainer

from src.application import get_app
from src.infra.cache import Cache, CacheSession
from src.infra.invalidation import InvalidationQueue
from src.models import Base

CACHE_TTL_SECONDS = 60
TOMBSTONE_TTL_MS = 2000
INVALIDATION_ATTEMPTS = 3
REDIS_TIMEOUT_SECONDS = 0.5
INVALIDATION_QUEUE_SIZE = 100
INVALIDATION_RETRY_SECONDS = 0.05


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
def invalidations() -> InvalidationQueue:
    return InvalidationQueue(INVALIDATION_QUEUE_SIZE, INVALIDATION_RETRY_SECONDS)


@pytest.fixture
def cache(redis_client: Redis, invalidations: InvalidationQueue) -> Cache:
    return Cache(
        redis_client,
        CACHE_TTL_SECONDS,
        TOMBSTONE_TTL_MS,
        INVALIDATION_ATTEMPTS,
        invalidations,
    )


@pytest.fixture
def cache_session(cache: Cache) -> CacheSession:
    return CacheSession(cache)


@pytest.fixture
async def client(
    session_factory: async_sessionmaker[AsyncSession],
    cache: Cache,
) -> AsyncIterator[AsyncClient]:
    app = get_app()
    app.state.session_factory = session_factory
    app.state.cache = cache

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test/v1') as ac:
        yield ac


@pytest.fixture
async def db_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session
