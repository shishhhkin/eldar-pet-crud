import asyncio
from collections.abc import Awaitable, Callable
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.infra.db import tx_session
from src.models.user_memberships import UserMembershipModel
from src.models.users import UserModel
from src.repository import UserMembershipRepo, UserRepo
from src.schemas.library import LibraryMembership
from src.services.membership_issuer import MembershipIssuer
from tests.conftest import LIBRARY_RETRY_ATTEMPTS, MEMBERSHIP_SYNC_INTERVAL_SECONDS
from tests.fake_library import FakeLibrary

WAIT_TIMEOUT_SECONDS = 5.0

type CreateUser = Callable[..., Awaitable[UUID]]


@pytest.fixture
def create_user(session_factory: async_sessionmaker[AsyncSession]) -> CreateUser:
    async def create(username: str, *, is_deleted: bool = False) -> UUID:
        async with tx_session(session_factory) as session:
            user = UserModel(
                username=username, email=f'{username}@example.com', is_deleted=is_deleted
            )
            await UserRepo(session).save(user)
        return user.id

    return create


async def _stored(session_factory: async_sessionmaker[AsyncSession]) -> dict[UUID, UUID]:
    async with session_factory() as session:
        stmt = select(UserMembershipModel.user_id, UserMembershipModel.id)
        return {user_id: membership_id for user_id, membership_id in await session.execute(stmt)}


async def test_sync_issues_memberships_for_pending_users(
    membership_issuer: MembershipIssuer,
    fake_library: FakeLibrary,
    create_user: CreateUser,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_ids = [await create_user('alice'), await create_user('bob')]

    assert await membership_issuer.sync_pending() == 2

    assert await _stored(session_factory) == {
        user_id: fake_library.memberships[user_id].id for user_id in user_ids
    }


async def test_sync_attaches_membership_already_issued_by_library(
    membership_issuer: MembershipIssuer,
    fake_library: FakeLibrary,
    create_user: CreateUser,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await create_user('alice')
    existing = fake_library.issue(user_id)

    assert await membership_issuer.sync_pending() == 1

    assert await _stored(session_factory) == {user_id: existing.id}
    assert len(fake_library.memberships) == 1


async def test_sync_skips_deleted_users(
    membership_issuer: MembershipIssuer,
    fake_library: FakeLibrary,
    create_user: CreateUser,
) -> None:
    await create_user('alice', is_deleted=True)

    assert await membership_issuer.sync_pending() == 0
    assert fake_library.requests == []


async def test_sync_stops_batch_when_library_unavailable(
    membership_issuer: MembershipIssuer,
    fake_library: FakeLibrary,
    create_user: CreateUser,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await create_user('alice')
    await create_user('bob')
    fake_library.fail(LIBRARY_RETRY_ATTEMPTS)

    assert await membership_issuer.sync_pending() == 0

    assert len(fake_library.requests) == LIBRARY_RETRY_ATTEMPTS
    assert await _stored(session_factory) == {}


async def test_repeated_sync_is_idempotent(
    membership_issuer: MembershipIssuer,
    fake_library: FakeLibrary,
    create_user: CreateUser,
) -> None:
    await create_user('alice')
    await membership_issuer.sync_pending()
    requests = len(fake_library.requests)

    assert await membership_issuer.sync_pending() == 0
    assert len(fake_library.requests) == requests


async def test_issue_is_idempotent_for_same_user(
    membership_issuer: MembershipIssuer,
    create_user: CreateUser,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await create_user('alice')

    first, second = await asyncio.gather(
        membership_issuer.issue(user_id), membership_issuer.issue(user_id)
    )

    assert first is not None
    assert second is not None
    assert first.id == second.id
    assert await _stored(session_factory) == {user_id: first.id}


async def test_issue_returns_none_when_library_unreachable(
    unreachable_membership_issuer: MembershipIssuer,
    create_user: CreateUser,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await create_user('alice')

    assert await unreachable_membership_issuer.issue(user_id) is None
    assert await _stored(session_factory) == {}


async def _store(
    session_factory: async_sessionmaker[AsyncSession],
    membership: LibraryMembership,
    synced_at: datetime,
) -> None:
    async with tx_session(session_factory) as session:
        await UserMembershipRepo(session).store(membership, synced_at)


async def _stored_copy(session_factory: async_sessionmaker[AsyncSession]) -> UserMembershipModel:
    async with session_factory() as session:
        return (await session.execute(select(UserMembershipModel))).scalar_one()


async def test_store_skips_older_version_synced_later(
    fake_library: FakeLibrary,
    create_user: CreateUser,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await create_user('alice')
    issued = fake_library.issue(user_id)
    changed = fake_library.change(user_id, 'LIB-99999999')
    synced_at = datetime.now(UTC)
    await _store(session_factory, changed, synced_at)

    await _store(session_factory, issued, synced_at + timedelta(seconds=1))

    stored = await _stored_copy(session_factory)
    assert (stored.number, stored.version, stored.synced_at) == (
        changed.number,
        changed.version,
        synced_at,
    )


async def test_store_same_version_moves_synced_at_forward_only(
    fake_library: FakeLibrary,
    create_user: CreateUser,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    issued = fake_library.issue(await create_user('alice'))
    synced_at = datetime.now(UTC)
    await _store(session_factory, issued, synced_at)

    await _store(session_factory, issued, synced_at - timedelta(seconds=1))
    assert (await _stored_copy(session_factory)).synced_at == synced_at

    await _store(session_factory, issued, synced_at + timedelta(seconds=1))
    assert (await _stored_copy(session_factory)).synced_at == synced_at + timedelta(seconds=1)


async def test_run_loop_backfills_pending_users(
    membership_issuer: MembershipIssuer,
    create_user: CreateUser,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await create_user('alice')
    worker = asyncio.create_task(membership_issuer.run())
    try:
        async with asyncio.timeout(WAIT_TIMEOUT_SECONDS):
            while user_id not in await _stored(session_factory):
                await asyncio.sleep(MEMBERSHIP_SYNC_INTERVAL_SECONDS)
    finally:
        worker.cancel()
        with suppress(asyncio.CancelledError):
            await worker
