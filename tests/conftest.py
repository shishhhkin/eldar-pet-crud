from collections.abc import AsyncIterator, Iterator

import pytest
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.community.postgres import PostgresContainer
from testcontainers.community.redis import RedisContainer

from src.application import get_app
from src.cache import Cache, build_client
from src.db import readonly_session
from src.dependencies import get_cache, get_session, get_tx_session, invalidating_tx_session
from src.models import Base


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
    client = build_client(
        redis_container.get_container_host_ip(),
        int(redis_container.get_exposed_port(6379)),
    )
    yield client
    await client.aclose()


@pytest.fixture(autouse=True)
async def flush_redis(redis_client: Redis) -> AsyncIterator[None]:
    await redis_client.flushdb()
    yield


@pytest.fixture
def cache(redis_client: Redis) -> Cache:
    return Cache(redis_client)


@pytest.fixture
async def client(
    session_factory: async_sessionmaker[AsyncSession],
    cache: Cache,
) -> AsyncIterator[AsyncClient]:
    app = get_app()

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with readonly_session(session_factory) as session:
            yield session

    async def override_get_tx_session() -> AsyncIterator[AsyncSession]:
        async with invalidating_tx_session(session_factory, cache) as session:
            yield session

    def override_get_cache() -> Cache:
        return cache

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_tx_session] = override_get_tx_session
    app.dependency_overrides[get_cache] = override_get_cache

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test/v1') as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def db_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session
