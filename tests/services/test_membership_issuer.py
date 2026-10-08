import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from http import HTTPMethod, HTTPStatus
from uuid import UUID

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.clients.library import LibraryClient
from src.infra.db import tx_session
from src.models.membership_requests import membership_requests
from src.models.user_memberships import UserMembershipModel
from src.models.users import UserModel
from src.repository import MembershipRequestRepo, UserMembershipRepo, UserRepo
from src.schemas.library import LibraryMembership
from src.services.membership_issuer import MembershipIssuer
from tests.conftest import (
    LIBRARY_RETRY_ATTEMPTS,
    MEMBERSHIP_RETRY_BASE_DELAY_SECONDS,
    MEMBERSHIP_RETRY_MAX_DELAY_SECONDS,
    MEMBERSHIP_SYNC_INTERVAL_SECONDS,
    MEMBERSHIP_SYNC_LEASE_SECONDS,
    make_issuer,
    wait_for_lock_waiter,
)
from tests.fake_library import FakeLibrary

ISSUER_LOGGER = 'src.services.membership_issuer'
WAIT_TIMEOUT_SECONDS = 5.0
LEASE = timedelta(seconds=MEMBERSHIP_SYNC_LEASE_SECONDS)
CLOCK_TOLERANCE = timedelta(seconds=1)
TOO_LONG_NUMBER = 'LIB-' + '9' * 13

type CreateUser = Callable[..., Awaitable[UUID]]
type Enqueue = Callable[..., Awaitable[None]]


@pytest.fixture
def create_user(session_factory: async_sessionmaker[AsyncSession]) -> CreateUser:
    async def create(username: str) -> UUID:
        async with tx_session(session_factory) as session:
            user = UserModel(username=username, email=f'{username}@example.com')
            await UserRepo(session).save(user)
        return user.id

    return create


@pytest.fixture
def enqueue(session_factory: async_sessionmaker[AsyncSession]) -> Enqueue:
    async def add(user_id: UUID, delay: timedelta = timedelta(0)) -> None:
        async with tx_session(session_factory) as session:
            await MembershipRequestRepo(session).add(user_id, delay)

    return add


async def _stored(session_factory: async_sessionmaker[AsyncSession]) -> dict[UUID, UUID]:
    async with session_factory() as session:
        stmt = select(UserMembershipModel.user_id, UserMembershipModel.id)
        return {user_id: membership_id for user_id, membership_id in await session.execute(stmt)}


async def _requests(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[UUID, tuple[int, timedelta]]:
    async with session_factory() as session:
        stmt = select(
            membership_requests.c.user_id,
            membership_requests.c.attempts,
            membership_requests.c.next_attempt_at - func.now(),
        )
        return {
            user_id: (attempts, wait) for user_id, attempts, wait in await session.execute(stmt)
        }


async def _set_attempts(
    session_factory: async_sessionmaker[AsyncSession], user_id: UUID, attempts: int
) -> None:
    async with tx_session(session_factory) as session:
        await session.execute(
            update(membership_requests)
            .where(membership_requests.c.user_id == user_id)
            .values(attempts=attempts)
        )


async def test_pass_issues_memberships_and_removes_requests(
    membership_issuer: MembershipIssuer,
    fake_library: FakeLibrary,
    create_user: CreateUser,
    enqueue: Enqueue,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_ids = [await create_user('alice'), await create_user('bob')]
    for user_id in user_ids:
        await enqueue(user_id)

    assert await membership_issuer.process_pass() == 2

    assert await _stored(session_factory) == {
        user_id: fake_library.memberships[user_id].id for user_id in user_ids
    }
    assert await _requests(session_factory) == {}


async def test_pass_attaches_membership_already_issued_by_library(
    membership_issuer: MembershipIssuer,
    fake_library: FakeLibrary,
    create_user: CreateUser,
    enqueue: Enqueue,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await create_user('alice')
    existing = fake_library.issue(user_id)
    await enqueue(user_id)

    assert await membership_issuer.process_pass() == 1

    assert await _stored(session_factory) == {user_id: existing.id}
    assert len(fake_library.memberships) == 1


async def test_pass_skips_request_leased_by_another_executor(
    membership_issuer: MembershipIssuer,
    fake_library: FakeLibrary,
    create_user: CreateUser,
    enqueue: Enqueue,
) -> None:
    await enqueue(await create_user('alice'), LEASE)

    assert await membership_issuer.process_pass() == 0
    assert fake_library.requests == []


async def test_pass_takes_request_whose_lease_expired(
    membership_issuer: MembershipIssuer,
    fake_library: FakeLibrary,
    create_user: CreateUser,
    enqueue: Enqueue,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await create_user('alice')
    await enqueue(user_id, -CLOCK_TOLERANCE)

    assert await membership_issuer.process_pass() == 1

    assert await _stored(session_factory) == {user_id: fake_library.memberships[user_id].id}


async def test_claim_returns_user_id_and_attempts(
    create_user: CreateUser,
    enqueue: Enqueue,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await create_user('alice')
    await enqueue(user_id)

    async with tx_session(session_factory) as session:
        claimed = await MembershipRequestRepo(session).claim(LEASE)

    assert claimed == (user_id, 0)


async def test_concurrent_claims_take_different_requests(
    create_user: CreateUser,
    enqueue: Enqueue,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_ids = {await create_user('alice'), await create_user('bob')}
    for user_id in user_ids:
        await enqueue(user_id)

    async with asyncio.timeout(WAIT_TIMEOUT_SECONDS):
        async with tx_session(session_factory) as first:
            held = await MembershipRequestRepo(first).claim(LEASE)
            async with tx_session(session_factory) as second:
                other = await MembershipRequestRepo(second).claim(LEASE)

    assert held is not None
    assert other is not None
    assert {held.user_id, other.user_id} == user_ids


async def test_claim_returns_nothing_when_no_request_is_due(
    create_user: CreateUser,
    enqueue: Enqueue,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await enqueue(await create_user('alice'), LEASE)

    async with tx_session(session_factory) as session:
        assert await MembershipRequestRepo(session).claim(LEASE) is None


async def test_pass_stops_and_releases_request_when_library_unavailable(
    membership_issuer: MembershipIssuer,
    fake_library: FakeLibrary,
    create_user: CreateUser,
    enqueue: Enqueue,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_ids = [await create_user('alice'), await create_user('bob')]
    for user_id in user_ids:
        await enqueue(user_id)
    fake_library.fail(LIBRARY_RETRY_ATTEMPTS)

    assert await membership_issuer.process_pass() == 1

    assert len(fake_library.requests) == LIBRARY_RETRY_ATTEMPTS
    requests = await _requests(session_factory)
    assert {user_id: attempts for user_id, (attempts, _) in requests.items()} == {
        user_id: 0 for user_id in user_ids
    }
    assert all(wait <= timedelta(0) for _, wait in requests.values())
    assert await _stored(session_factory) == {}


async def test_rejected_request_is_postponed_and_pass_continues(
    membership_issuer: MembershipIssuer,
    fake_library: FakeLibrary,
    create_user: CreateUser,
    enqueue: Enqueue,
    session_factory: async_sessionmaker[AsyncSession],
    caplog: pytest.LogCaptureFixture,
) -> None:
    rejected, issued = await create_user('alice'), await create_user('bob')
    await enqueue(rejected)
    await enqueue(issued)
    fake_library.fail(status=HTTPStatus.UNPROCESSABLE_ENTITY)

    with caplog.at_level(logging.ERROR, logger=ISSUER_LOGGER):
        assert await membership_issuer.process_pass() == 2

    assert await _stored(session_factory) == {issued: fake_library.memberships[issued].id}
    requests = await _requests(session_factory)
    assert list(requests) == [rejected]
    attempts, wait = requests[rejected]
    delay = timedelta(seconds=MEMBERSHIP_RETRY_BASE_DELAY_SECONDS * 2)
    assert attempts == 1
    assert delay - CLOCK_TOLERANCE < wait <= delay
    assert any(str(rejected) in record.getMessage() for record in caplog.records)


@pytest.mark.parametrize(
    ('attempts', 'delay_seconds'),
    [
        (2, MEMBERSHIP_RETRY_BASE_DELAY_SECONDS * 2**3),
        (10, MEMBERSHIP_RETRY_MAX_DELAY_SECONDS),
        (1_000_000, MEMBERSHIP_RETRY_MAX_DELAY_SECONDS),
    ],
)
async def test_postponement_doubles_with_attempts_up_to_cap(
    membership_issuer: MembershipIssuer,
    fake_library: FakeLibrary,
    create_user: CreateUser,
    enqueue: Enqueue,
    session_factory: async_sessionmaker[AsyncSession],
    attempts: int,
    delay_seconds: float,
) -> None:
    user_id = await create_user('alice')
    await enqueue(user_id)
    await _set_attempts(session_factory, user_id, attempts)
    fake_library.fail(status=HTTPStatus.UNPROCESSABLE_ENTITY)

    assert await membership_issuer.process_pass() == 1

    new_attempts, wait = (await _requests(session_factory))[user_id]
    delay = timedelta(seconds=delay_seconds)
    assert new_attempts == attempts + 1
    assert delay - CLOCK_TOLERANCE < wait <= delay


async def test_pass_is_limited_by_pass_limit(
    session_factory: async_sessionmaker[AsyncSession],
    library: LibraryClient,
    create_user: CreateUser,
    enqueue: Enqueue,
) -> None:
    for username in ('alice', 'bob'):
        await enqueue(await create_user(username))

    assert await make_issuer(session_factory, library, pass_limit=1).process_pass() == 1

    assert len(await _requests(session_factory)) == 1


async def test_issue_after_cancel_does_not_store_copy(
    membership_issuer: MembershipIssuer,
    fake_library: FakeLibrary,
    create_user: CreateUser,
    enqueue: Enqueue,
    session_factory: async_sessionmaker[AsyncSession],
    caplog: pytest.LogCaptureFixture,
) -> None:
    user_id = await create_user('alice')
    await enqueue(user_id, LEASE)
    async with tx_session(session_factory) as session:
        await MembershipRequestRepo(session).cancel(user_id)

    with caplog.at_level(logging.WARNING, logger=ISSUER_LOGGER):
        assert await membership_issuer.issue(user_id) is None

    assert await _stored(session_factory) == {}
    membership_id = str(fake_library.memberships[user_id].id)
    assert any(membership_id in record.getMessage() for record in caplog.records)


async def test_completion_waits_for_concurrent_cancel_and_skips_copy(
    membership_issuer: MembershipIssuer,
    create_user: CreateUser,
    enqueue: Enqueue,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await create_user('alice')
    await enqueue(user_id, LEASE)

    async with tx_session(session_factory) as session:
        await MembershipRequestRepo(session).cancel(user_id)
        issue = asyncio.create_task(membership_issuer.issue(user_id))
        await wait_for_lock_waiter(session_factory)

    async with asyncio.timeout(WAIT_TIMEOUT_SECONDS):
        assert await issue is None
    assert await _stored(session_factory) == {}


async def test_same_request_completed_twice_stores_single_copy(
    membership_issuer: MembershipIssuer,
    fake_library: FakeLibrary,
    create_user: CreateUser,
    enqueue: Enqueue,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await create_user('alice')
    await enqueue(user_id, LEASE)

    results = await asyncio.gather(
        membership_issuer.issue(user_id), membership_issuer.issue(user_id)
    )

    assert sorted(result is None for result in results) == [False, True]
    assert await _stored(session_factory) == {user_id: fake_library.memberships[user_id].id}
    assert len(fake_library.memberships) == 1


async def test_issue_returns_none_and_postpones_when_library_rejects(
    membership_issuer: MembershipIssuer,
    fake_library: FakeLibrary,
    create_user: CreateUser,
    enqueue: Enqueue,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await create_user('alice')
    await enqueue(user_id, LEASE)
    fake_library.fail(status=HTTPStatus.UNPROCESSABLE_ENTITY)

    assert await membership_issuer.issue(user_id) is None

    assert len(fake_library.requests) == 1
    assert await _stored(session_factory) == {}
    attempts, wait = (await _requests(session_factory))[user_id]
    assert attempts == 1
    assert wait > timedelta(0)


async def test_issue_returns_none_and_releases_when_library_unreachable(
    unreachable_membership_issuer: MembershipIssuer,
    create_user: CreateUser,
    enqueue: Enqueue,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await create_user('alice')
    await enqueue(user_id, LEASE)

    assert await unreachable_membership_issuer.issue(user_id) is None

    assert await _stored(session_factory) == {}
    attempts, wait = (await _requests(session_factory))[user_id]
    assert attempts == 0
    assert wait <= timedelta(0)


async def test_issue_keeps_lease_when_copy_cannot_be_stored(
    membership_issuer: MembershipIssuer,
    fake_library: FakeLibrary,
    create_user: CreateUser,
    enqueue: Enqueue,
    session_factory: async_sessionmaker[AsyncSession],
    caplog: pytest.LogCaptureFixture,
) -> None:
    user_id = await create_user('alice')
    await enqueue(user_id, LEASE)
    fake_library.issue(user_id)
    fake_library.change(user_id, TOO_LONG_NUMBER)

    with caplog.at_level(logging.WARNING, logger=ISSUER_LOGGER):
        assert await membership_issuer.issue(user_id) is None

    assert await _stored(session_factory) == {}
    attempts, wait = (await _requests(session_factory))[user_id]
    assert attempts == 0
    assert wait > LEASE - CLOCK_TOLERANCE
    assert any(str(user_id) in record.getMessage() for record in caplog.records)


async def _store(
    session_factory: async_sessionmaker[AsyncSession], membership: LibraryMembership
) -> UserMembershipModel:
    async with tx_session(session_factory) as session:
        return await UserMembershipRepo(session).store(membership)


async def _stored_copy(session_factory: async_sessionmaker[AsyncSession]) -> UserMembershipModel:
    async with session_factory() as session:
        return (await session.execute(select(UserMembershipModel))).scalar_one()


async def _db_now(session_factory: async_sessionmaker[AsyncSession]) -> datetime:
    async with session_factory() as session:
        return (await session.execute(select(func.now()))).scalar_one()


async def test_store_sets_synced_at_on_db_side(
    fake_library: FakeLibrary,
    create_user: CreateUser,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    issued = fake_library.issue(await create_user('alice'))
    before = await _db_now(session_factory)

    returned = await _store(session_factory, issued)

    stored = await _stored_copy(session_factory)
    assert before < stored.synced_at < await _db_now(session_factory)
    assert returned.synced_at == stored.synced_at


async def test_store_keeps_newer_version_and_returns_it(
    fake_library: FakeLibrary,
    create_user: CreateUser,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await create_user('alice')
    issued = fake_library.issue(user_id)
    changed = fake_library.change(user_id, 'LIB-99999999')
    first = await _store(session_factory, changed)

    returned = await _store(session_factory, issued)

    stored = await _stored_copy(session_factory)
    assert (stored.number, stored.version) == (changed.number, changed.version)
    assert (returned.number, returned.version) == (changed.number, changed.version)
    assert stored.synced_at > first.synced_at


async def test_store_moves_synced_at_forward(
    fake_library: FakeLibrary,
    create_user: CreateUser,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    issued = fake_library.issue(await create_user('alice'))
    first = await _store(session_factory, issued)

    second = await _store(session_factory, issued)

    assert second.synced_at > first.synced_at
    assert (await _stored_copy(session_factory)).synced_at == second.synced_at


async def test_run_loop_issues_pending_requests(
    membership_issuer: MembershipIssuer,
    create_user: CreateUser,
    enqueue: Enqueue,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await create_user('alice')
    await enqueue(user_id)
    worker = asyncio.create_task(membership_issuer.run())
    try:
        async with asyncio.timeout(WAIT_TIMEOUT_SECONDS):
            while user_id not in await _stored(session_factory):
                await asyncio.sleep(MEMBERSHIP_SYNC_INTERVAL_SECONDS)
    finally:
        membership_issuer.stop()
        async with asyncio.timeout(WAIT_TIMEOUT_SECONDS):
            await worker


async def test_stop_finishes_request_in_flight_and_leaves_rest_of_pass(
    membership_issuer: MembershipIssuer,
    fake_library: FakeLibrary,
    create_user: CreateUser,
    enqueue: Enqueue,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    first, second = await create_user('alice'), await create_user('bob')
    await enqueue(first)
    await enqueue(second)
    hold = fake_library.hold_next(HTTPMethod.POST)
    worker = asyncio.create_task(membership_issuer.run())
    async with asyncio.timeout(WAIT_TIMEOUT_SECONDS):
        await hold.reached.wait()

    membership_issuer.stop()
    hold.release.set()
    async with asyncio.timeout(WAIT_TIMEOUT_SECONDS):
        await worker

    assert await _stored(session_factory) == {first: fake_library.memberships[first].id}
    assert list(await _requests(session_factory)) == [second]
    assert len(fake_library.requests) == 1
