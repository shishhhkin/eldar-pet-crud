import asyncio
import socket
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from contextlib import AbstractContextManager, asynccontextmanager, contextmanager
from datetime import timedelta
from functools import partial
from typing import Any
from uuid import uuid4

import httpx
import pytest
from aiobreaker import CircuitBreaker
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer, TopicPartition
from aiokafka.admin import AIOKafkaAdminClient, NewTopic
from aiokafka.structs import ConsumerRecord
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from redis.asyncio.retry import Retry
from redis.backoff import NoBackoff
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.community.kafka import KafkaContainer
from testcontainers.community.postgres import PostgresContainer
from testcontainers.community.redis import RedisContainer

from src.application import get_app
from src.clients.library import LibraryClient
from src.infra.cache import Cache
from src.infra.db import tx_session
from src.models import Base, cache_invalidations
from src.repository import (
    BookReservationOutboxRepo,
    BookReservationRepo,
    CacheInvalidationRepo,
    PendingMembershipRepo,
    UserMembershipRepo,
)
from src.schemas.book_reservations import BookReservationCreate, BookReservationRead
from src.services.book_reservation_relay import BookReservationRelay
from src.services.book_reservation_service import BookReservationService
from src.services.invalidation_outbox import InvalidationOutbox
from src.services.membership_service import MembershipService
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
MEMBERSHIP_SYNC_PASS_LIMIT = 100
MEMBERSHIP_SYNC_INTERVAL_SECONDS = 0.05
MEMBERSHIP_SYNC_LEASE_SECONDS = 60
KAFKA_IMAGE = 'confluentinc/cp-kafka:7.9.10'
KAFKA_SEND_TIMEOUT_SECONDS = 1.0
KAFKA_READ_TIMEOUT_SECONDS = 10.0
KAFKA_POLL_MS = 100
BOOK_RESERVATION_RELAY_PASS_LIMIT = 100
BOOK_RESERVATION_RELAY_INTERVAL_SECONDS = 0.05
BOOK_RESERVATION_RELAY_LEASE_SECONDS = 60
LOCK_WAIT_TIMEOUT_SECONDS = 5.0
LOCK_WAIT_POLL_SECONDS = 0.01


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


def make_library(http: httpx.AsyncClient, breaker: CircuitBreaker) -> LibraryClient:
    retry = RetryPolicy(
        LIBRARY_RETRY_ATTEMPTS, LIBRARY_RETRY_BASE_DELAY_SECONDS, LIBRARY_RETRY_MAX_DELAY_SECONDS
    )
    return LibraryClient(http, retry, breaker, LIBRARY_TIMEOUT_SECONDS)


@pytest.fixture
async def library(
    fake_library: FakeLibrary, breaker: CircuitBreaker
) -> AsyncIterator[LibraryClient]:
    transport = httpx.MockTransport(fake_library.handler)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as http:
        yield make_library(http, breaker)


@pytest.fixture
async def unreachable_library(breaker: CircuitBreaker) -> AsyncIterator[LibraryClient]:
    base_url = f'http://127.0.0.1:{closed_port()}/v1/'
    async with httpx.AsyncClient(
        base_url=base_url, timeout=LIBRARY_TIMEOUT_SECONDS, trust_env=False
    ) as http:
        yield make_library(http, breaker)


def make_membership_service(
    session_factory: async_sessionmaker[AsyncSession],
    library: LibraryClient,
    pass_limit: int = MEMBERSHIP_SYNC_PASS_LIMIT,
) -> MembershipService:
    return MembershipService(
        session_factory,
        UserMembershipRepo,
        PendingMembershipRepo,
        library,
        pass_limit,
        MEMBERSHIP_SYNC_INTERVAL_SECONDS,
        MEMBERSHIP_SYNC_LEASE_SECONDS,
    )


@pytest.fixture
def membership_service(
    session_factory: async_sessionmaker[AsyncSession], library: LibraryClient
) -> MembershipService:
    return make_membership_service(session_factory, library)


@pytest.fixture
def unreachable_membership_service(
    session_factory: async_sessionmaker[AsyncSession], unreachable_library: LibraryClient
) -> MembershipService:
    return make_membership_service(session_factory, unreachable_library)


@asynccontextmanager
async def _client(
    session_factory: async_sessionmaker[AsyncSession], cache: Cache, library: LibraryClient
) -> AsyncIterator[AsyncClient]:
    app = get_app()
    app.state.session_factory = session_factory
    app.state.cache = cache
    app.state.outbox = _outbox(session_factory, cache)
    app.state.library = library
    app.state.membership_service = make_membership_service(session_factory, library)

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


async def wait_for_lock_waiter(session_factory: async_sessionmaker[AsyncSession]) -> None:
    stmt = text("SELECT count(*) FROM pg_stat_activity WHERE wait_event_type = 'Lock'")
    async with asyncio.timeout(LOCK_WAIT_TIMEOUT_SECONDS):
        while True:
            async with session_factory() as session:
                if await session.scalar(stmt):
                    return
            await asyncio.sleep(LOCK_WAIT_POLL_SECONDS)


@pytest.fixture
async def db_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session


@pytest.fixture(scope='session')
def kafka_container() -> Iterator[KafkaContainer]:
    with KafkaContainer(KAFKA_IMAGE).with_kraft() as container:
        yield container


@pytest.fixture(scope='session')
def kafka_bootstrap(kafka_container: KafkaContainer) -> str:
    return kafka_container.get_bootstrap_server()


async def create_topic(bootstrap: str) -> str:
    topic = f'book-reservations-{uuid4().hex}'
    admin = AIOKafkaAdminClient(bootstrap_servers=bootstrap)
    await admin.start()
    try:
        await admin.create_topics([NewTopic(topic, num_partitions=1, replication_factor=1)])
    finally:
        await admin.close()
    return topic


@pytest.fixture
async def kafka_topic(kafka_bootstrap: str) -> str:
    return await create_topic(kafka_bootstrap)


@pytest.fixture
async def kafka_producer(kafka_bootstrap: str) -> AsyncIterator[AIOKafkaProducer]:
    producer = AIOKafkaProducer(
        bootstrap_servers=kafka_bootstrap, enable_idempotence=True, acks='all'
    )
    await producer.start()
    yield producer
    await producer.stop()


type KafkaOutage = Callable[[], AbstractContextManager[None]]


@pytest.fixture
def kafka_outage(kafka_container: KafkaContainer) -> KafkaOutage:
    @contextmanager
    def outage() -> Iterator[None]:
        container = kafka_container.get_wrapped_container()
        container.pause()
        try:
            yield
        finally:
            container.unpause()

    return outage


async def read_messages(bootstrap: str, topic: str, count: int) -> list[ConsumerRecord]:
    consumer = AIOKafkaConsumer(topic, bootstrap_servers=bootstrap, auto_offset_reset='earliest')
    await consumer.start()
    try:
        records: list[ConsumerRecord] = []
        async with asyncio.timeout(KAFKA_READ_TIMEOUT_SECONDS):
            while len(records) < count:
                for batch in (await consumer.getmany(timeout_ms=KAFKA_POLL_MS)).values():
                    records.extend(batch)
        return records
    finally:
        await consumer.stop()


def reservation_event(body: dict[str, Any]) -> dict[str, Any]:
    return {
        'id': body['id'],
        'title': body['title'],
        'author': body['author'],
        'reserved_at': body['created_at'],
    }


async def topic_size(bootstrap: str, topic: str) -> int:
    consumer = AIOKafkaConsumer(bootstrap_servers=bootstrap)
    await consumer.start()
    try:
        partition = TopicPartition(topic, 0)
        return int((await consumer.end_offsets([partition]))[partition])
    finally:
        await consumer.stop()


def make_relay(
    session_factory: async_sessionmaker[AsyncSession],
    producer: AIOKafkaProducer,
    topic: str,
    *,
    pass_limit: int = BOOK_RESERVATION_RELAY_PASS_LIMIT,
    send_timeout_seconds: float = KAFKA_SEND_TIMEOUT_SECONDS,
) -> BookReservationRelay:
    return BookReservationRelay(
        session_factory,
        BookReservationOutboxRepo,
        producer,
        topic,
        pass_limit,
        BOOK_RESERVATION_RELAY_INTERVAL_SECONDS,
        BOOK_RESERVATION_RELAY_LEASE_SECONDS,
        send_timeout_seconds,
    )


@pytest.fixture
def relay(
    session_factory: async_sessionmaker[AsyncSession],
    kafka_producer: AIOKafkaProducer,
    kafka_topic: str,
) -> BookReservationRelay:
    return make_relay(session_factory, kafka_producer, kafka_topic)


type Reserve = Callable[..., Awaitable[BookReservationRead]]


@pytest.fixture
def reserve(session_factory: async_sessionmaker[AsyncSession]) -> Reserve:
    async def create(title: str = 'Мастер и Маргарита') -> BookReservationRead:
        async with tx_session(session_factory) as session:
            service = BookReservationService(
                BookReservationRepo(session), BookReservationOutboxRepo(session)
            )
            return await service.create(
                BookReservationCreate(title=title, author='Михаил Булгаков')
            )

    return create
