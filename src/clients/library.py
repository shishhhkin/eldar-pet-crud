import asyncio
from http import HTTPMethod, HTTPStatus
from uuid import UUID

import httpx
from aiobreaker import CircuitBreaker, CircuitBreakerError
from pydantic import ValidationError

from src.exceptions import (
    ExternalServiceBadResponseError,
    ExternalServiceUnavailableError,
    TransientError,
)
from src.logging_config import request_id_var
from src.middleware import REQUEST_ID_HEADER
from src.schemas.library import LibraryMembership, LibraryMembershipCreate
from src.utils.resilience import RetryPolicy

MEMBERSHIPS_PATH = 'memberships'
RETRYABLE_STATUSES = frozenset(
    {
        HTTPStatus.TOO_MANY_REQUESTS,
        HTTPStatus.INTERNAL_SERVER_ERROR,
        HTTPStatus.BAD_GATEWAY,
        HTTPStatus.SERVICE_UNAVAILABLE,
        HTTPStatus.GATEWAY_TIMEOUT,
    }
)


def retry_after_seconds(response: httpx.Response) -> float | None:
    value = response.headers.get('Retry-After')
    if value is None or not value.isdigit():
        return None
    return float(value)


class LibraryClient:
    def __init__(
        self,
        http: httpx.AsyncClient,
        retry: RetryPolicy,
        breaker: CircuitBreaker,
        timeout_seconds: float,
    ) -> None:
        self.http = http
        self.retry = retry
        self.breaker = breaker
        self.timeout_seconds = timeout_seconds

    async def issue_membership(self, user_id: UUID) -> LibraryMembership:
        payload = LibraryMembershipCreate(user_id=user_id)
        response = await self._request(
            HTTPMethod.POST, MEMBERSHIPS_PATH, json=payload.model_dump(mode='json')
        )
        return self._parse(response, HTTPStatus.CREATED, HTTPStatus.OK)

    async def get_membership(self, membership_id: UUID) -> LibraryMembership:
        response = await self._request(HTTPMethod.GET, f'{MEMBERSHIPS_PATH}/{membership_id}')
        return self._parse(response, HTTPStatus.OK)

    async def _request(
        self, method: HTTPMethod, url: str, *, json: object = None
    ) -> httpx.Response:
        async def send() -> httpx.Response:
            return await self._send(method, url, json=json)

        try:
            response: httpx.Response = await self.retry.call(lambda: self.breaker.call_async(send))
        except TransientError as exc:
            raise ExternalServiceUnavailableError(str(exc)) from exc
        except CircuitBreakerError as exc:
            raise ExternalServiceUnavailableError(f'{method} {url}: circuit breaker open') from exc
        return response

    async def _send(self, method: HTTPMethod, url: str, *, json: object) -> httpx.Response:
        rid = request_id_var.get()
        headers = {REQUEST_ID_HEADER: rid} if rid else None
        try:
            async with asyncio.timeout(self.timeout_seconds):
                response = await self.http.request(method, url, json=json, headers=headers)
        except (httpx.TransportError, TimeoutError) as exc:
            raise TransientError(f'{method} {url}: {type(exc).__name__}') from exc
        if response.status_code in RETRYABLE_STATUSES:
            raise TransientError(
                f'{method} {url}: {response.status_code}', retry_after_seconds(response)
            )
        return response

    def _parse(self, response: httpx.Response, *expected: HTTPStatus) -> LibraryMembership:
        request = response.request
        if response.status_code not in expected:
            raise ExternalServiceBadResponseError(
                f'{request.method} {request.url}: unexpected status {response.status_code}'
            )
        try:
            return LibraryMembership.model_validate_json(response.content)
        except ValidationError as exc:
            raise ExternalServiceBadResponseError(
                f'{request.method} {request.url}: invalid body'
            ) from exc
