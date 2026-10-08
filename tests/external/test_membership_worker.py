import asyncio
from datetime import timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from testcontainers.community.postgres import PostgresContainer
from testcontainers.community.redis import RedisContainer

from src.infra.db import tx_session
from src.models.membership_requests import membership_requests
from src.models.user_memberships import UserMembershipModel
from src.models.users import UserModel
from src.repository import MembershipRequestRepo, UserRepo
from tests.external import EXTERNAL_LIBRARY_URL, requires_library
from tests.worker_process import POLL_SECONDS, running_worker, worker_env

pytestmark = requires_library

WAIT_TIMEOUT_SECONDS = 15.0


async def _membership(
    session_factory: async_sessionmaker[AsyncSession], user_id: UUID
) -> UserMembershipModel | None:
    async with session_factory() as session:
        stmt = select(UserMembershipModel).where(UserMembershipModel.user_id == user_id)
        return (await session.execute(stmt)).scalar_one_or_none()


async def test_worker_process_issues_membership_through_library(
    postgres_container: PostgresContainer,
    redis_container: RedisContainer,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with tx_session(session_factory) as session:
        user = UserModel(username='alice', email='alice@example.com')
        await UserRepo(session).save(user)
        await MembershipRequestRepo(session).add(user.id, timedelta(0))
    env = worker_env(postgres_container, redis_container, str(EXTERNAL_LIBRARY_URL))

    async with running_worker(env) as worker:
        async with asyncio.timeout(WAIT_TIMEOUT_SECONDS):
            while await _membership(session_factory, user.id) is None:
                await asyncio.sleep(POLL_SECONDS)
        assert await worker.stop() == 0

    async with session_factory() as session:
        stmt = select(func.count()).select_from(membership_requests)
        assert (await session.execute(stmt)).scalar_one() == 0
