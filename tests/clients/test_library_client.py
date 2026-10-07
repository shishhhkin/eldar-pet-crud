from http import HTTPStatus
from uuid import uuid4

import pytest

from src.clients.library import LibraryClient
from src.exceptions import ExternalServiceBadResponseError, ExternalServiceUnavailableError
from src.middleware import REQUEST_ID_HEADER
from tests.conftest import LIBRARY_BREAKER_THRESHOLD, LIBRARY_RETRY_ATTEMPTS
from tests.fake_library import FakeLibrary


async def test_issue_membership(library: LibraryClient, fake_library: FakeLibrary) -> None:
    user_id = uuid4()

    membership = await library.issue_membership(user_id)

    assert membership.user_id == user_id
    assert fake_library.memberships == {user_id: membership}


async def test_issue_existing_membership_returns_it(
    library: LibraryClient, fake_library: FakeLibrary
) -> None:
    existing = fake_library.issue(uuid4())

    assert await library.issue_membership(existing.user_id) == existing
    assert len(fake_library.memberships) == 1
    assert [request.method for request in fake_library.requests] == ['POST']


async def test_get_membership(library: LibraryClient, fake_library: FakeLibrary) -> None:
    existing = fake_library.issue(uuid4())

    assert await library.get_membership(existing.id) == existing


async def test_get_missing_membership_raises_bad_response(
    library: LibraryClient, fake_library: FakeLibrary
) -> None:
    with pytest.raises(ExternalServiceBadResponseError) as exc_info:
        await library.get_membership(uuid4())

    assert 'unexpected status 404' in str(exc_info.value)
    assert len(fake_library.requests) == 1


@pytest.mark.parametrize(
    'status',
    [
        HTTPStatus.TOO_MANY_REQUESTS,
        HTTPStatus.INTERNAL_SERVER_ERROR,
        HTTPStatus.BAD_GATEWAY,
        HTTPStatus.SERVICE_UNAVAILABLE,
        HTTPStatus.GATEWAY_TIMEOUT,
    ],
)
async def test_retryable_statuses_are_retried(
    library: LibraryClient, fake_library: FakeLibrary, status: HTTPStatus
) -> None:
    fake_library.fail(LIBRARY_RETRY_ATTEMPTS - 1, status)

    membership = await library.issue_membership(uuid4())

    assert len(fake_library.requests) == LIBRARY_RETRY_ATTEMPTS
    assert list(fake_library.memberships.values()) == [membership]


async def test_retry_after_within_max_delay_is_retried(
    library: LibraryClient, fake_library: FakeLibrary
) -> None:
    fake_library.fail(status=HTTPStatus.TOO_MANY_REQUESTS, headers={'Retry-After': '0'})

    await library.issue_membership(uuid4())

    assert len(fake_library.requests) == 2


async def test_retry_after_beyond_max_delay_is_not_waited(
    library: LibraryClient, fake_library: FakeLibrary
) -> None:
    fake_library.fail(status=HTTPStatus.TOO_MANY_REQUESTS, headers={'Retry-After': '3600'})

    with pytest.raises(ExternalServiceUnavailableError) as exc_info:
        await library.issue_membership(uuid4())

    assert str(exc_info.value) == 'POST memberships: 429'
    assert len(fake_library.requests) == 1


async def test_timeouts_are_retried(library: LibraryClient, fake_library: FakeLibrary) -> None:
    existing = fake_library.issue(uuid4())
    fake_library.timeout(LIBRARY_RETRY_ATTEMPTS - 1)

    assert await library.get_membership(existing.id) == existing
    assert len(fake_library.requests) == LIBRARY_RETRY_ATTEMPTS


async def test_retry_after_lost_response_does_not_duplicate(
    library: LibraryClient, fake_library: FakeLibrary
) -> None:
    user_id = uuid4()
    fake_library.commit_then_timeout()

    membership = await library.issue_membership(user_id)

    assert fake_library.memberships == {user_id: membership}
    assert [request.method for request in fake_library.requests] == ['POST', 'POST']


async def test_exhausted_retries_raise_unavailable(
    library: LibraryClient, fake_library: FakeLibrary
) -> None:
    fake_library.fail(LIBRARY_RETRY_ATTEMPTS)

    with pytest.raises(ExternalServiceUnavailableError) as exc_info:
        await library.issue_membership(uuid4())

    assert str(exc_info.value) == 'POST memberships: 503'
    assert len(fake_library.requests) == LIBRARY_RETRY_ATTEMPTS


@pytest.mark.parametrize(
    'status',
    [
        HTTPStatus.NOT_FOUND,
        HTTPStatus.CONFLICT,
        HTTPStatus.UNPROCESSABLE_ENTITY,
        HTTPStatus.NOT_IMPLEMENTED,
        HTTPStatus.OK,
    ],
)
async def test_unexpected_response_is_not_retried(
    library: LibraryClient, fake_library: FakeLibrary, status: HTTPStatus
) -> None:
    fake_library.fail(status=status)

    with pytest.raises(ExternalServiceBadResponseError):
        await library.issue_membership(uuid4())

    assert len(fake_library.requests) == 1


async def test_unexpected_responses_do_not_open_breaker(
    library: LibraryClient, fake_library: FakeLibrary
) -> None:
    fake_library.fail(LIBRARY_BREAKER_THRESHOLD, HTTPStatus.UNPROCESSABLE_ENTITY)
    for _ in range(LIBRARY_BREAKER_THRESHOLD):
        with pytest.raises(ExternalServiceBadResponseError):
            await library.issue_membership(uuid4())

    await library.issue_membership(uuid4())

    assert len(fake_library.requests) == LIBRARY_BREAKER_THRESHOLD + 1


async def test_open_breaker_stops_requests(
    library: LibraryClient, fake_library: FakeLibrary
) -> None:
    fake_library.fail(LIBRARY_BREAKER_THRESHOLD * 2)

    for _ in range(3):
        with pytest.raises(ExternalServiceUnavailableError) as exc_info:
            await library.issue_membership(uuid4())

    assert str(exc_info.value) == 'POST memberships: circuit breaker open'
    assert len(fake_library.requests) == LIBRARY_BREAKER_THRESHOLD


async def test_unreachable_library_is_unavailable(unreachable_library: LibraryClient) -> None:
    with pytest.raises(ExternalServiceUnavailableError):
        await unreachable_library.issue_membership(uuid4())


async def test_no_request_id_header_outside_request(
    library: LibraryClient, fake_library: FakeLibrary
) -> None:
    await library.issue_membership(uuid4())

    assert REQUEST_ID_HEADER not in fake_library.requests[0].headers
