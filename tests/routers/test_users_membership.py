import asyncio
import logging
from uuid import UUID

import pytest
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.middleware import REQUEST_ID_HEADER
from src.models.user_memberships import UserMembershipModel
from src.schemas.users import MembershipRead
from tests.conftest import (
    LIBRARY_BREAKER_THRESHOLD,
    LIBRARY_RETRY_ATTEMPTS,
    without_synced_at,
)
from tests.fake_library import FakeLibrary

SERVICE_LOGGER = 'src.services.user_service'
WAIT_TIMEOUT_SECONDS = 5.0


def _payload(username: str = 'alice', email: str = 'alice@example.com') -> dict:
    return {'username': username, 'email': email, 'profile': {'bio': 'hello'}}


def _key(user_id: str) -> str:
    return f'v1:user:{user_id}'


async def _create_user(client: AsyncClient, username: str = 'alice') -> dict:
    response = await client.post('/users', json=_payload(username, f'{username}@example.com'))
    assert response.status_code == 201
    return response.json()


async def _stored_membership(db_session: AsyncSession, user_id: str) -> UserMembershipModel | None:
    stmt = select(UserMembershipModel).where(UserMembershipModel.user_id == UUID(user_id))
    return (await db_session.execute(stmt)).scalar_one_or_none()


def _library_gets(fake_library: FakeLibrary) -> int:
    return sum(request.method == 'GET' for request in fake_library.requests)


async def test_create_user_issues_and_stores_membership(
    client: AsyncClient, fake_library: FakeLibrary, db_session: AsyncSession
) -> None:
    created = await _create_user(client)

    issued = fake_library.memberships[UUID(created['id'])]
    membership = MembershipRead.model_validate(created['membership'])
    assert membership == MembershipRead(
        id=issued.id,
        number=issued.number,
        issued_at=issued.issued_at,
        synced_at=membership.synced_at,
    )
    stored = await _stored_membership(db_session, created['id'])
    assert stored is not None
    assert (stored.id, stored.number, stored.issued_at, stored.synced_at) == (
        issued.id,
        issued.number,
        issued.issued_at,
        membership.synced_at,
    )


async def test_create_user_while_library_down_leaves_membership_pending(
    library_down_client: AsyncClient, db_session: AsyncSession
) -> None:
    created = await _create_user(library_down_client)

    assert created['membership'] is None
    assert await _stored_membership(db_session, created['id']) is None


async def test_create_user_forwards_request_id(
    client: AsyncClient, fake_library: FakeLibrary
) -> None:
    response = await client.post('/users', json=_payload(), headers={REQUEST_ID_HEADER: 'rid-42'})

    assert response.status_code == 201
    assert fake_library.requests[0].headers[REQUEST_ID_HEADER] == 'rid-42'


async def test_duplicate_user_does_not_reach_library(
    client: AsyncClient, fake_library: FakeLibrary
) -> None:
    await _create_user(client)

    response = await client.post('/users', json=_payload(email='other@example.com'))

    assert response.status_code == 409
    assert len(fake_library.requests) == 1


async def test_open_breaker_skips_library_on_create(
    client: AsyncClient, fake_library: FakeLibrary
) -> None:
    fake_library.fail(LIBRARY_BREAKER_THRESHOLD)
    for username in ('alice', 'bob'):
        assert (await _create_user(client, username))['membership'] is None
    assert len(fake_library.requests) == LIBRARY_BREAKER_THRESHOLD

    created = await _create_user(client, 'carol')

    assert created['membership'] is None
    assert len(fake_library.requests) == LIBRARY_BREAKER_THRESHOLD


async def test_read_user_fetches_membership_and_caches(
    client: AsyncClient, fake_library: FakeLibrary, redis_client: Redis
) -> None:
    created = await _create_user(client)

    response = await client.get(f'/users/{created["id"]}')

    assert response.status_code == 200
    assert without_synced_at(response.json()) == without_synced_at(created)
    fetched = MembershipRead.model_validate(response.json()['membership'])
    assert fetched.synced_at > MembershipRead.model_validate(created['membership']).synced_at
    assert _library_gets(fake_library) == 1
    assert await redis_client.get(_key(created['id'])) is not None


async def test_cached_read_does_not_call_library(
    client: AsyncClient, fake_library: FakeLibrary
) -> None:
    created = await _create_user(client)
    first = (await client.get(f'/users/{created["id"]}')).json()

    for _ in range(2):
        assert (await client.get(f'/users/{created["id"]}')).json() == first

    assert _library_gets(fake_library) == 1


async def test_read_user_refreshes_copy_changed_in_library(
    client: AsyncClient, fake_library: FakeLibrary, db_session: AsyncSession
) -> None:
    created = await _create_user(client)
    user_id = UUID(created['id'])
    changed = fake_library.change(user_id, 'LIB-99999999')

    response = await client.get(f'/users/{created["id"]}')

    membership = MembershipRead.model_validate(response.json()['membership'])
    assert membership.number == changed.number
    stored = await _stored_membership(db_session, created['id'])
    assert stored is not None
    assert (stored.number, stored.version, stored.synced_at) == (
        changed.number,
        changed.version,
        membership.synced_at,
    )


async def test_slow_read_of_older_version_keeps_newer_copy(
    client: AsyncClient, fake_library: FakeLibrary, db_session: AsyncSession
) -> None:
    created = await _create_user(client)
    hold = fake_library.hold_next_get()
    slow = asyncio.create_task(client.get(f'/users/{created["id"]}'))
    async with asyncio.timeout(WAIT_TIMEOUT_SECONDS):
        await hold.reached.wait()
    changed = fake_library.change(UUID(created['id']), 'LIB-99999999')

    fast = await client.get(f'/users/{created["id"]}')
    hold.release.set()
    async with asyncio.timeout(WAIT_TIMEOUT_SECONDS):
        await slow

    assert fast.json()['membership']['number'] == changed.number
    stored = await _stored_membership(db_session, created['id'])
    assert stored is not None
    assert (stored.number, stored.version) == (changed.number, changed.version)


async def test_read_user_while_library_down_serves_copy_uncached(
    client: AsyncClient, fake_library: FakeLibrary, redis_client: Redis
) -> None:
    created = await _create_user(client)
    fake_library.fail(LIBRARY_RETRY_ATTEMPTS)

    response = await client.get(f'/users/{created["id"]}')

    assert response.status_code == 200
    assert response.json() == created
    assert await redis_client.get(_key(created['id'])) is None


async def test_read_pending_user_is_not_cached(
    library_down_client: AsyncClient, redis_client: Redis
) -> None:
    created = await _create_user(library_down_client)

    response = await library_down_client.get(f'/users/{created["id"]}')

    assert response.status_code == 200
    assert response.json()['membership'] is None
    assert await redis_client.get(_key(created['id'])) is None


async def test_read_pending_user_does_not_call_library(
    client: AsyncClient, fake_library: FakeLibrary
) -> None:
    fake_library.fail(LIBRARY_RETRY_ATTEMPTS)
    created = await _create_user(client)

    await client.get(f'/users/{created["id"]}')

    assert _library_gets(fake_library) == 0


async def test_read_user_with_membership_missing_in_library_logs_error(
    client: AsyncClient,
    fake_library: FakeLibrary,
    redis_client: Redis,
    caplog: pytest.LogCaptureFixture,
) -> None:
    created = await _create_user(client)
    fake_library.forget(UUID(created['id']))

    with caplog.at_level(logging.ERROR, logger=SERVICE_LOGGER):
        response = await client.get(f'/users/{created["id"]}')

    assert response.json() == {**created, 'membership': None}
    assert await redis_client.get(_key(created['id'])) is None
    assert any(
        record.name == SERVICE_LOGGER and created['membership']['id'] in record.getMessage()
        for record in caplog.records
    )


async def test_update_user_returns_copy_without_library(
    client: AsyncClient, fake_library: FakeLibrary
) -> None:
    created = await _create_user(client)
    requests_before = len(fake_library.requests)

    response = await client.patch(f'/users/{created["id"]}', json={'username': 'bob'})

    assert response.status_code == 200
    assert response.json()['membership'] == created['membership']
    assert len(fake_library.requests) == requests_before


async def test_delete_user_soft_deletes_membership(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    created = await _create_user(client)

    assert (await client.delete(f'/users/{created["id"]}')).status_code == 204

    stored = await _stored_membership(db_session, created['id'])
    assert stored is not None
    assert stored.is_deleted
