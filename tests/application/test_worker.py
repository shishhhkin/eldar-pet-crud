from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from testcontainers.community.postgres import PostgresContainer
from testcontainers.community.redis import RedisContainer

from src.infra.db import tx_session
from src.models.membership_requests import membership_requests
from src.models.users import UserModel
from src.repository import MembershipRequestRepo, UserRepo
from tests.conftest import closed_port
from tests.worker_process import STOPPED, running_worker, worker_env

PAUSE_SECONDS = 3600


def _unreachable_library_url() -> str:
    return f'http://127.0.0.1:{closed_port()}/v1'


async def test_worker_process_stops_on_sigterm_during_pause(
    postgres_container: PostgresContainer, redis_container: RedisContainer
) -> None:
    env = {
        **worker_env(postgres_container, redis_container, _unreachable_library_url()),
        'membership_sync_interval_seconds': str(PAUSE_SECONDS),
    }

    async with running_worker(env) as worker:
        assert await worker.stop() == 0

    assert worker.logged(STOPPED)


async def test_worker_process_keeps_request_while_library_unreachable(
    postgres_container: PostgresContainer,
    redis_container: RedisContainer,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with tx_session(session_factory) as session:
        user = UserModel(username='alice', email='alice@example.com')
        await UserRepo(session).save(user)
        await MembershipRequestRepo(session).add(user.id, timedelta(0))
    env = worker_env(postgres_container, redis_container, _unreachable_library_url())

    async with running_worker(env) as worker:
        await worker.wait_for('membership issue deferred')
        assert await worker.stop() == 0

    async with session_factory() as session:
        stmt = select(membership_requests.c.user_id, membership_requests.c.attempts)
        assert (await session.execute(stmt)).all() == [(user.id, 0)]
