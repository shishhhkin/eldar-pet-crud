import asyncio
import os
import time
from collections.abc import AsyncIterator, Callable
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from testcontainers.community.postgres import PostgresContainer
from testcontainers.community.redis import RedisContainer

from src.infra.db import tx_session
from src.models.pending_memberships import pending_memberships
from src.models.users import UserModel
from src.repository import PendingMembershipRepo, UserRepo
from src.worker import HEARTBEAT_NAME
from tests.conftest import closed_port
from tests.worker_process import POLL_SECONDS, STOPPED, healthcheck, running_worker, worker_env

PAUSE_SECONDS = 3600
LEASE_SECONDS = 60
WAIT_TIMEOUT_SECONDS = 15.0
SHORT_LIBRARY_CALL = {
    'library_retry_attempts': '1',
    'library_timeout_seconds': '1',
    'membership_sync_lease_seconds': '2',
}

type MakeEnv = Callable[..., dict[str, str]]


@pytest.fixture
def make_env(
    postgres_container: PostgresContainer, redis_container: RedisContainer, tmp_path: Path
) -> MakeEnv:
    def make(library_url: str | None = None, **overrides: str) -> dict[str, str]:
        url = library_url or f'http://127.0.0.1:{closed_port()}/v1'
        return {**worker_env(postgres_container, redis_container, url, tmp_path), **overrides}

    return make


@pytest.fixture
async def hanging_library_url() -> AsyncIterator[tuple[str, asyncio.Event]]:
    connected = asyncio.Event()

    async def hang(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        connected.set()
        await reader.read()
        writer.close()

    async with await asyncio.start_server(hang, '127.0.0.1', 0) as server:
        port = server.sockets[0].getsockname()[1]
        yield f'http://127.0.0.1:{port}/v1', connected


async def test_worker_process_stops_on_sigterm_during_pause(make_env: MakeEnv) -> None:
    env = make_env(membership_sync_interval_seconds=str(PAUSE_SECONDS))

    async with running_worker(env) as worker:
        assert await worker.stop() == 0

    assert worker.logged(STOPPED)


async def test_request_of_killed_worker_process_is_retried_after_restart(
    make_env: MakeEnv,
    hanging_library_url: tuple[str, asyncio.Event],
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with tx_session(session_factory) as session:
        user = UserModel(username='alice', email='alice@example.com')
        await UserRepo(session).save(user)
        await PendingMembershipRepo(session).add(user.id, timedelta(0))
    library_url, connected = hanging_library_url

    async with running_worker(make_env(library_url, **SHORT_LIBRARY_CALL)) as worker:
        async with asyncio.timeout(WAIT_TIMEOUT_SECONDS):
            await connected.wait()
        await worker.kill()

    async with session_factory() as session:
        stmt = select(pending_memberships.c.user_id, pending_memberships.c.failed_at)
        assert (await session.execute(stmt)).all() == [(user.id, None)]
    async with running_worker(make_env(**SHORT_LIBRARY_CALL)) as worker:
        await worker.wait_for(f'membership issue deferred: user_id={user.id}')
        assert await worker.stop() == 0


async def test_running_worker_process_passes_healthcheck(make_env: MakeEnv, tmp_path: Path) -> None:
    env = make_env()

    async with running_worker(env) as worker:
        async with asyncio.timeout(WAIT_TIMEOUT_SECONDS):
            while not (tmp_path / HEARTBEAT_NAME).exists():
                await asyncio.sleep(POLL_SECONDS)
        assert await healthcheck(env) == 0
        assert await worker.stop() == 0


async def test_healthcheck_fails_on_stale_heartbeat(make_env: MakeEnv, tmp_path: Path) -> None:
    env = make_env(membership_sync_lease_seconds=str(LEASE_SECONDS))
    heartbeat = tmp_path / HEARTBEAT_NAME
    heartbeat.touch()
    beat_at = time.time() - POLL_SECONDS - LEASE_SECONDS - 1
    os.utime(heartbeat, (beat_at, beat_at))

    assert await healthcheck(env) == 1
