import os
from collections.abc import AsyncIterator
from uuid import uuid4

import httpx
import pytest
from aiobreaker import CircuitBreaker

from src.clients.library import LibraryClient
from src.exceptions import ExternalServiceBadResponseError
from tests.conftest import LIBRARY_TIMEOUT_SECONDS, build_library

EXTERNAL_LIBRARY_URL = os.environ.get('EXTERNAL_LIBRARY_URL')

pytestmark = pytest.mark.skipif(
    EXTERNAL_LIBRARY_URL is None, reason='EXTERNAL_LIBRARY_URL is not set'
)


@pytest.fixture
async def external_library(breaker: CircuitBreaker) -> AsyncIterator[LibraryClient]:
    async with httpx.AsyncClient(
        base_url=str(EXTERNAL_LIBRARY_URL), timeout=LIBRARY_TIMEOUT_SECONDS, trust_env=False
    ) as http:
        yield build_library(http, breaker)


async def test_issue_returns_membership_for_user(external_library: LibraryClient) -> None:
    user_id = uuid4()

    membership = await external_library.issue_membership(user_id)

    assert membership.user_id == user_id


async def test_repeated_issue_returns_same_membership(external_library: LibraryClient) -> None:
    user_id = uuid4()
    issued = await external_library.issue_membership(user_id)

    assert await external_library.issue_membership(user_id) == issued


async def test_get_returns_issued_membership(external_library: LibraryClient) -> None:
    issued = await external_library.issue_membership(uuid4())

    assert await external_library.get_membership(issued.id) == issued


async def test_get_unknown_membership_raises_bad_response(
    external_library: LibraryClient,
) -> None:
    with pytest.raises(ExternalServiceBadResponseError):
        await external_library.get_membership(uuid4())
