import asyncio
import os
import time
from collections.abc import Callable
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from testcontainers.community.postgres import PostgresContainer
from testcontainers.community.redis import RedisContainer

from src.models import book_reservation_outbox
from src.relay import HEARTBEAT_NAME
from tests.conftest import Reserve, closed_port, read_messages
from tests.worker_process import (
    POLL_SECONDS,
    healthcheck,
    run_until_exit,
    running_worker,
    worker_env,
)

RELAY_MODULE = 'src.relay'
STARTED = 'book reservation relay started'
STOPPED = 'book reservation relay stopped'
LEASE_SECONDS = 60
WAIT_TIMEOUT_SECONDS = 15.0

type MakeEnv = Callable[..., dict[str, str]]


@pytest.fixture
def make_env(
    postgres_container: PostgresContainer,
    redis_container: RedisContainer,
    kafka_bootstrap: str,
    kafka_topic: str,
    tmp_path: Path,
) -> MakeEnv:
    def make(**overrides: str) -> dict[str, str]:
        library_url = f'http://127.0.0.1:{closed_port()}/v1'
        return {
            **worker_env(postgres_container, redis_container, library_url, tmp_path),
            'kafka_bootstrap_servers': kafka_bootstrap,
            'kafka_book_reservations_topic': kafka_topic,
            'book_reservation_relay_interval_seconds': str(POLL_SECONDS),
            **overrides,
        }

    return make


async def _wait_until_outbox_is_empty(session_factory: async_sessionmaker[AsyncSession]) -> None:
    stmt = select(book_reservation_outbox.c.book_reservation_id)
    async with asyncio.timeout(WAIT_TIMEOUT_SECONDS):
        while True:
            async with session_factory() as session:
                if not (await session.execute(stmt)).all():
                    return
            await asyncio.sleep(POLL_SECONDS)


async def test_relay_process_publishes_reservation_and_stops_on_sigterm(
    make_env: MakeEnv,
    reserve: Reserve,
    session_factory: async_sessionmaker[AsyncSession],
    kafka_bootstrap: str,
    kafka_topic: str,
) -> None:
    reservation = await reserve()

    async with running_worker(make_env(), RELAY_MODULE, STARTED) as relay:
        records = await read_messages(kafka_bootstrap, kafka_topic, 1)
        await _wait_until_outbox_is_empty(session_factory)
        assert await relay.stop() == 0

    assert relay.logged(STOPPED)
    assert [record.key for record in records] == [str(reservation.id).encode()]


async def test_running_relay_process_passes_healthcheck(make_env: MakeEnv, tmp_path: Path) -> None:
    env = make_env()

    async with running_worker(env, RELAY_MODULE, STARTED) as relay:
        async with asyncio.timeout(WAIT_TIMEOUT_SECONDS):
            while not (tmp_path / HEARTBEAT_NAME).exists():
                await asyncio.sleep(POLL_SECONDS)
        assert await healthcheck(env, RELAY_MODULE) == 0
        assert await relay.stop() == 0


async def test_relay_healthcheck_fails_on_stale_heartbeat(
    make_env: MakeEnv, tmp_path: Path
) -> None:
    env = make_env(book_reservation_relay_lease_seconds=str(LEASE_SECONDS))
    heartbeat = tmp_path / HEARTBEAT_NAME
    heartbeat.touch()
    beat_at = time.time() - POLL_SECONDS - LEASE_SECONDS - 1
    os.utime(heartbeat, (beat_at, beat_at))

    assert await healthcheck(env, RELAY_MODULE) == 1


async def test_relay_process_exits_when_kafka_is_unreachable(make_env: MakeEnv) -> None:
    env = make_env(kafka_bootstrap_servers=f'127.0.0.1:{closed_port()}')

    returncode, log = await run_until_exit(env, RELAY_MODULE)

    assert returncode != 0
    assert 'KafkaConnectionError' in log
    assert STARTED not in log
