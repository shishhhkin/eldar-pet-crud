import socket
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from contextlib import asynccontextmanager
from datetime import timedelta
from functools import partial

import httpx
import pytest
from aiobreaker import CircuitBreaker
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
from src.clients.library import LibraryClient
from src.infra.cache import Cache
from src.models import Base, cache_invalidations
from src.repository import CacheInvalidationRepo, UserMembershipRepo, UserRepo
from src.services.invalidation_outbox import InvalidationOutbox
from src.services.membership_issuer import MembershipIssuer
from src.services.user_registration import UserRegistration
from src.utils.resilience import RetryPolicy
from tests.fake_library import BASE_URL, FakeLibrary

CACHE_TTL_SECONDS = 60
TOMBSTONE_TTL_MS = 2000
REDIS_TIMEOUT_SECONDS = 0.5
REDIS_PAUSE_SAFETY_MS = 30_000
INVALIDATION_BATCH_SIZE = 100
INVALIDATION_RETRY_SECONDS = 0.05
INVALIDATION_LEASE_SECONDS = 60
LIBRARY_TIMEOUT_SECONDS = 0.5
LIBRARY_RETRY_ATTEMPTS = 3
LIBRARY_RETRY_BASE_DELAY_SECONDS = 0.001
LIBRARY_RETRY_MAX_DELAY_SECONDS = 0.005
LIBRARY_BREAKER_THRESHOLD = 5
LIBRARY_BREAKER_RESET_SECONDS = 60
MEMBERSHIP_SYNC_BATCH_SIZE = 100
MEMBERSHIP_SYNC_INTERVAL_SECONDS = 0.05


def closed_port() -> int:
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return int(sock.getsockname()[1])


def without_synced_at(user: dict) -> dict:
    if user['membership'] is None:
        return user
    membership = {k: v for k, v in user['membership'].items() if k != 'synced_at'}
    return {**user, 'membership': membership}


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
        CacheInvalidationRepo,
        cache,
        INVALIDATION_BATCH_SIZE,
        INVALIDATION_RETRY_SECONDS,
        INVALIDATION_LEASE_SECONDS,
    )


@pytest.fixture
def outbox(session_factory: async_sessionmaker[AsyncSession], cache: Cache) -> InvalidationOutbox:
    return _outbox(session_factory, cache)


@pytest.fixture
def fake_library() -> FakeLibrary:
    return FakeLibrary()


@pytest.fixture
def breaker() -> CircuitBreaker:
    return CircuitBreaker(
        fail_max=LIBRARY_BREAKER_THRESHOLD,
        timeout_duration=timedelta(seconds=LIBRARY_BREAKER_RESET_SECONDS),
    )


def build_library(http: httpx.AsyncClient, breaker: CircuitBreaker) -> LibraryClient:
    retry = RetryPolicy(
        LIBRARY_RETRY_ATTEMPTS, LIBRARY_RETRY_BASE_DELAY_SECONDS, LIBRARY_RETRY_MAX_DELAY_SECONDS
    )
    return LibraryClient(http, retry, breaker)


@pytest.fixture
async def library(
    fake_library: FakeLibrary, breaker: CircuitBreaker
) -> AsyncIterator[LibraryClient]:
    transport = httpx.MockTransport(fake_library.handler)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as http:
        yield build_library(http, breaker)


@pytest.fixture
async def unreachable_library(breaker: CircuitBreaker) -> AsyncIterator[LibraryClient]:
    base_url = f'http://127.0.0.1:{closed_port()}/v1/'
    async with httpx.AsyncClient(
        base_url=base_url, timeout=LIBRARY_TIMEOUT_SECONDS, trust_env=False
    ) as http:
        yield build_library(http, breaker)


def _issuer(
    session_factory: async_sessionmaker[AsyncSession], library: LibraryClient
) -> MembershipIssuer:
    return MembershipIssuer(
        session_factory,
        UserMembershipRepo,
        library,
        MEMBERSHIP_SYNC_BATCH_SIZE,
        MEMBERSHIP_SYNC_INTERVAL_SECONDS,
    )


@pytest.fixture
def membership_issuer(
    session_factory: async_sessionmaker[AsyncSession], library: LibraryClient
) -> MembershipIssuer:
    return _issuer(session_factory, library)


@pytest.fixture
def unreachable_membership_issuer(
    session_factory: async_sessionmaker[AsyncSession], unreachable_library: LibraryClient
) -> MembershipIssuer:
    return _issuer(session_factory, unreachable_library)


@pytest.fixture
def user_registration(
    session_factory: async_sessionmaker[AsyncSession], membership_issuer: MembershipIssuer
) -> UserRegistration:
    return UserRegistration(session_factory, UserRepo, membership_issuer)


@asynccontextmanager
async def _client(
    session_factory: async_sessionmaker[AsyncSession], cache: Cache, library: LibraryClient
) -> AsyncIterator[AsyncClient]:
    app = get_app()
    app.state.session_factory = session_factory
    app.state.cache = cache
    app.state.outbox = _outbox(session_factory, cache)
    app.state.library = library
    app.state.membership_issuer = _issuer(session_factory, library)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test/v1') as ac:
        yield ac


@pytest.fixture
async def client(
    session_factory: async_sessionmaker[AsyncSession], cache: Cache, library: LibraryClient
) -> AsyncIterator[AsyncClient]:
    async with _client(session_factory, cache, library) as ac:
        yield ac


@pytest.fixture
async def unreachable_client(
    session_factory: async_sessionmaker[AsyncSession],
    unreachable_cache: Cache,
    library: LibraryClient,
) -> AsyncIterator[AsyncClient]:
    async with _client(session_factory, unreachable_cache, library) as ac:
        yield ac


@pytest.fixture
async def library_down_client(
    session_factory: async_sessionmaker[AsyncSession],
    cache: Cache,
    unreachable_library: LibraryClient,
) -> AsyncIterator[AsyncClient]:
    async with _client(session_factory, cache, unreachable_library) as ac:
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
