import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import suppress
from datetime import datetime, timedelta
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.dependencies.db import invalidating_tx_session
from src.infra.cache import TOMBSTONE, Cache
from src.infra.db import tx_session
from src.models import cache_invalidations
from src.repository.cache_invalidations import CacheInvalidationRepo, pop_pending_invalidations
from src.services.invalidation_outbox import InvalidationOutbox
from tests.conftest import (
    INVALIDATION_BATCH_SIZE,
    INVALIDATION_LEASE_SECONDS,
    INVALIDATION_RETRY_SECONDS,
    PauseRedisWrites,
    closed_port,
    outbox_keys,
)

CACHE_LOGGER = 'src.infra.cache'
OUTBOX_LOGGER = 'src.services.invalidation_outbox'
DB_DEPENDENCY_LOGGER = 'src.dependencies.db'
NEW_NAME = 'Новое Имя'
LEASE = timedelta(seconds=INVALIDATION_LEASE_SECONDS)
EXPIRED_LEASE = timedelta(0)
WAIT_TIMEOUT_SECONDS = 5.0
POLL_SECONDS = 0.01


def _key(author_id: str) -> str:
    return f'v1:author:{author_id}'


async def _create_author(client: AsyncClient) -> dict:
    response = await client.post(
        '/authors',
        json={'name': 'Лев Толстой', 'bio': 'русский писатель', 'books': []},
    )
    assert response.status_code == 201
    return response.json()


async def _add(session_factory: async_sessionmaker[AsyncSession], *keys: str) -> list[UUID]:
    async with tx_session(session_factory) as session:
        repo = CacheInvalidationRepo(session)
        for key in keys:
            await repo.add(key)
        return pop_pending_invalidations(session)


async def _claim(session_factory: async_sessionmaker[AsyncSession], lease: timedelta) -> None:
    async with tx_session(session_factory) as session:
        await CacheInvalidationRepo(session).claim(INVALIDATION_BATCH_SIZE, lease)


async def _claimed_until(
    session_factory: async_sessionmaker[AsyncSession], invalidation_id: UUID
) -> datetime | None:
    async with session_factory() as session:
        stmt = select(cache_invalidations.c.claimed_until).where(
            cache_invalidations.c.id == invalidation_id
        )
        return (await session.execute(stmt)).scalar_one()


async def _idle_in_transaction_count(session_factory: async_sessionmaker[AsyncSession]) -> int:
    async with session_factory() as session:
        stmt = text("SELECT count(*) FROM pg_stat_activity WHERE state = 'idle in transaction'")
        return (await session.execute(stmt)).scalar_one()


@pytest.fixture
async def unreachable_session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        f'postgresql+asyncpg://postgres:postgres@127.0.0.1:{closed_port()}/postgres'
    )
    yield async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    await engine.dispose()


async def test_update_invalidates_right_after_commit_and_leaves_no_row(
    client: AsyncClient,
    redis_client: Redis,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    created = await _create_author(client)
    assert (await client.get(f'/authors/{created["id"]}')).status_code == 200

    updated = await client.patch(f'/authors/{created["id"]}', json={'name': NEW_NAME})

    assert updated.status_code == 200
    assert await redis_client.get(_key(created['id'])) == TOMBSTONE
    assert await outbox_keys(session_factory) == []


async def test_delete_invalidates_right_after_commit_and_leaves_no_row(
    client: AsyncClient,
    redis_client: Redis,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    created = await _create_author(client)

    deleted = await client.delete(f'/authors/{created["id"]}')

    assert deleted.status_code == 204
    assert await redis_client.get(_key(created['id'])) == TOMBSTONE
    assert await outbox_keys(session_factory) == []


async def test_update_with_unreachable_redis_keeps_invalidation_in_database(
    unreachable_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    created = await _create_author(unreachable_client)

    updated = await unreachable_client.patch(f'/authors/{created["id"]}', json={'name': NEW_NAME})

    assert updated.status_code == 200
    assert updated.json()['name'] == NEW_NAME
    assert await outbox_keys(session_factory) == [_key(created['id'])]


async def test_kept_invalidation_is_applied_once_redis_accepts_writes_again(
    client: AsyncClient,
    redis_client: Redis,
    outbox: InvalidationOutbox,
    session_factory: async_sessionmaker[AsyncSession],
    pause_redis_writes: PauseRedisWrites,
) -> None:
    created = await _create_author(client)
    key = _key(created['id'])
    assert (await client.get(f'/authors/{created["id"]}')).status_code == 200
    cached = await redis_client.get(key)
    assert cached is not None

    await pause_redis_writes()
    updated = await client.patch(f'/authors/{created["id"]}', json={'name': NEW_NAME})

    assert updated.status_code == 200
    assert await outbox_keys(session_factory) == [key]
    assert await redis_client.get(key) == cached

    await redis_client.client_unpause()
    await outbox.flush()

    assert await outbox_keys(session_factory) == []
    assert await redis_client.get(key) == TOMBSTONE
    assert (await client.get(f'/authors/{created["id"]}')).json()['name'] == NEW_NAME


async def test_failed_update_leaves_no_invalidation(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    response = await client.patch(f'/authors/{uuid4()}', json={'name': NEW_NAME})

    assert response.status_code == 404
    assert await outbox_keys(session_factory) == []


async def test_rolled_back_transaction_leaves_no_invalidation(
    outbox: InvalidationOutbox,
    redis_client: Redis,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    key = 'v1:author:rolled-back'

    with pytest.raises(RuntimeError):
        async with invalidating_tx_session(session_factory, outbox) as session:
            await CacheInvalidationRepo(session).add(key)
            raise RuntimeError('business failure')

    assert await outbox_keys(session_factory) == []
    assert await redis_client.exists(key) == 0


async def test_flush_applies_every_stored_invalidation(
    outbox: InvalidationOutbox,
    redis_client: Redis,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    keys = ['v1:author:1', 'v1:author:2']
    await _add(session_factory, *keys)

    await outbox.flush()

    assert [await redis_client.get(key) for key in keys] == [TOMBSTONE, TOMBSTONE]
    assert await outbox_keys(session_factory) == []


async def test_flush_works_through_given_repository_factory(
    cache: Cache,
    redis_client: Redis,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    key = 'v1:author:1'
    await _add(session_factory, key)
    sessions: list[AsyncSession] = []

    def repo_factory(session: AsyncSession) -> CacheInvalidationRepo:
        sessions.append(session)
        return CacheInvalidationRepo(session)

    outbox = InvalidationOutbox(
        session_factory,
        repo_factory,
        cache,
        INVALIDATION_BATCH_SIZE,
        INVALIDATION_RETRY_SECONDS,
        INVALIDATION_LEASE_SECONDS,
    )

    await outbox.flush()

    assert await redis_client.get(key) == TOMBSTONE
    assert await outbox_keys(session_factory) == []
    assert len(set(sessions)) == 2


async def test_flush_drains_more_than_one_batch(
    cache: Cache,
    redis_client: Redis,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    keys = ['v1:author:1', 'v1:author:2', 'v1:author:3']
    await _add(session_factory, *keys)
    outbox = InvalidationOutbox(
        session_factory,
        CacheInvalidationRepo,
        cache,
        1,
        INVALIDATION_RETRY_SECONDS,
        INVALIDATION_LEASE_SECONDS,
    )

    await outbox.flush()

    assert [await redis_client.get(key) for key in keys] == [TOMBSTONE] * len(keys)
    assert await outbox_keys(session_factory) == []


async def test_flush_with_ids_applies_only_those_invalidations(
    outbox: InvalidationOutbox,
    redis_client: Redis,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    [own_id] = await _add(session_factory, 'v1:author:own')
    await _add(session_factory, 'v1:author:foreign')

    await outbox.flush([own_id])

    assert await redis_client.get('v1:author:own') == TOMBSTONE
    assert await redis_client.exists('v1:author:foreign') == 0
    assert await outbox_keys(session_factory) == ['v1:author:foreign']


@pytest.mark.parametrize(
    'batch_size', [INVALIDATION_BATCH_SIZE, 1], ids=['partial_batch', 'full_batch']
)
async def test_flush_with_unreachable_redis_keeps_rows_and_stops_at_first_failure(
    batch_size: int,
    unreachable_cache: Cache,
    session_factory: async_sessionmaker[AsyncSession],
    caplog: pytest.LogCaptureFixture,
) -> None:
    keys = ['v1:author:1', 'v1:author:2']
    await _add(session_factory, *keys)
    outbox = InvalidationOutbox(
        session_factory,
        CacheInvalidationRepo,
        unreachable_cache,
        batch_size,
        INVALIDATION_RETRY_SECONDS,
        INVALIDATION_LEASE_SECONDS,
    )

    with caplog.at_level(logging.WARNING, logger=CACHE_LOGGER):
        async with asyncio.timeout(WAIT_TIMEOUT_SECONDS):
            await outbox.flush()

    assert await outbox_keys(session_factory) == keys
    assert len([record for record in caplog.records if record.name == CACHE_LOGGER]) == 1


async def test_invalidations_left_by_failed_flush_are_applied_by_next_flush(
    outbox: InvalidationOutbox,
    redis_client: Redis,
    session_factory: async_sessionmaker[AsyncSession],
    pause_redis_writes: PauseRedisWrites,
) -> None:
    keys = ['v1:author:1', 'v1:author:2']
    await _add(session_factory, *keys)
    await pause_redis_writes()
    await outbox.flush()
    assert await outbox_keys(session_factory) == keys

    await redis_client.client_unpause()
    await outbox.flush()

    assert [await redis_client.get(key) for key in keys] == [TOMBSTONE, TOMBSTONE]
    assert await outbox_keys(session_factory) == []


async def test_flush_commits_claim_and_holds_no_transaction_while_waiting_for_redis(
    outbox: InvalidationOutbox,
    session_factory: async_sessionmaker[AsyncSession],
    pause_redis_writes: PauseRedisWrites,
) -> None:
    [invalidation_id] = await _add(session_factory, 'v1:author:1')
    await pause_redis_writes()

    flushing = asyncio.create_task(outbox.flush())
    async with asyncio.timeout(WAIT_TIMEOUT_SECONDS):
        while await _claimed_until(session_factory, invalidation_id) is None:
            await asyncio.sleep(POLL_SECONDS)

    assert await _idle_in_transaction_count(session_factory) == 0
    assert not flushing.done()
    await flushing


async def test_flush_skips_invalidation_claimed_by_another_processor(
    outbox: InvalidationOutbox,
    redis_client: Redis,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    key = 'v1:author:1'
    await _add(session_factory, key)
    await _claim(session_factory, LEASE)

    await outbox.flush()

    assert await redis_client.exists(key) == 0
    assert await outbox_keys(session_factory) == [key]


async def test_flush_takes_over_invalidation_whose_lease_expired(
    outbox: InvalidationOutbox,
    redis_client: Redis,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    key = 'v1:author:1'
    await _add(session_factory, key)
    await _claim(session_factory, EXPIRED_LEASE)

    await outbox.flush()

    assert await redis_client.get(key) == TOMBSTONE
    assert await outbox_keys(session_factory) == []


async def test_flush_with_unreachable_database_raises(
    cache: Cache,
    unreachable_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    outbox = InvalidationOutbox(
        unreachable_session_factory,
        CacheInvalidationRepo,
        cache,
        INVALIDATION_BATCH_SIZE,
        INVALIDATION_RETRY_SECONDS,
        INVALIDATION_LEASE_SECONDS,
    )

    with pytest.raises(OSError):
        await outbox.flush()


async def test_run_logs_failed_iteration_and_keeps_processing(
    cache: Cache,
    redis_client: Redis,
    session_factory: async_sessionmaker[AsyncSession],
    caplog: pytest.LogCaptureFixture,
) -> None:
    key = 'v1:author:1'
    await _add(session_factory, key)
    calls = 0

    def failing_once_repo_factory(session: AsyncSession) -> CacheInvalidationRepo:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError('unexpected failure')
        return CacheInvalidationRepo(session)

    outbox = InvalidationOutbox(
        session_factory,
        failing_once_repo_factory,
        cache,
        INVALIDATION_BATCH_SIZE,
        INVALIDATION_RETRY_SECONDS,
        INVALIDATION_LEASE_SECONDS,
    )

    with caplog.at_level(logging.ERROR, logger=OUTBOX_LOGGER):
        worker = asyncio.create_task(outbox.run())
        try:
            async with asyncio.timeout(WAIT_TIMEOUT_SECONDS):
                while await outbox_keys(session_factory):
                    await asyncio.sleep(POLL_SECONDS)
        finally:
            worker.cancel()
            with suppress(asyncio.CancelledError):
                await worker

    assert await redis_client.get(key) == TOMBSTONE
    records = [record for record in caplog.records if record.name == OUTBOX_LOGGER]
    assert [record.levelno for record in records] == [logging.ERROR]


async def test_database_failure_after_commit_leaves_invalidation_to_worker(
    cache: Cache,
    session_factory: async_sessionmaker[AsyncSession],
    unreachable_session_factory: async_sessionmaker[AsyncSession],
    caplog: pytest.LogCaptureFixture,
) -> None:
    key = 'v1:author:1'
    outbox = InvalidationOutbox(
        unreachable_session_factory,
        CacheInvalidationRepo,
        cache,
        INVALIDATION_BATCH_SIZE,
        INVALIDATION_RETRY_SECONDS,
        INVALIDATION_LEASE_SECONDS,
    )

    with caplog.at_level(logging.WARNING, logger=DB_DEPENDENCY_LOGGER):
        async with invalidating_tx_session(session_factory, outbox) as session:
            await CacheInvalidationRepo(session).add(key)

    assert await outbox_keys(session_factory) == [key]
    records = [record for record in caplog.records if record.name == DB_DEPENDENCY_LOGGER]
    assert [record.levelno for record in records] == [logging.WARNING]


async def test_unexpected_failure_after_commit_propagates(
    cache: Cache,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    key = 'v1:author:1'

    def broken_repo_factory(session: AsyncSession) -> CacheInvalidationRepo:
        raise RuntimeError('unexpected failure')

    outbox = InvalidationOutbox(
        session_factory,
        broken_repo_factory,
        cache,
        INVALIDATION_BATCH_SIZE,
        INVALIDATION_RETRY_SECONDS,
        INVALIDATION_LEASE_SECONDS,
    )

    with pytest.raises(RuntimeError, match='unexpected failure'):
        async with invalidating_tx_session(session_factory, outbox) as session:
            await CacheInvalidationRepo(session).add(key)

    assert await outbox_keys(session_factory) == [key]


async def test_claim_skips_rows_locked_by_another_processor(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _add(session_factory, 'v1:author:1', 'v1:author:2')

    async with tx_session(session_factory) as first, tx_session(session_factory) as second:
        claimed_by_first = await CacheInvalidationRepo(first).claim(INVALIDATION_BATCH_SIZE, LEASE)
        claimed_by_second = await CacheInvalidationRepo(second).claim(
            INVALIDATION_BATCH_SIZE, LEASE
        )

    assert [key for _, key in claimed_by_first] == ['v1:author:1', 'v1:author:2']
    assert claimed_by_second == []


async def test_invalidation_stored_after_claim_survives_delete_of_claimed_rows(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    key = 'v1:author:1'
    await _add(session_factory, key)

    async with tx_session(session_factory) as session:
        repo = CacheInvalidationRepo(session)
        claimed = await repo.claim(INVALIDATION_BATCH_SIZE, LEASE)
        [later_id] = await _add(session_factory, key)
        await repo.delete([invalidation_id for invalidation_id, _ in claimed])

    async with tx_session(session_factory) as session:
        remaining = await CacheInvalidationRepo(session).claim(INVALIDATION_BATCH_SIZE, LEASE)

    assert [invalidation_id for invalidation_id, _ in remaining] == [later_id]
