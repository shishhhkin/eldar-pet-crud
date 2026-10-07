from http import HTTPMethod, HTTPStatus
from uuid import UUID

import httpx
from pydantic import ValidationError

from src.exceptions import CircuitOpenError, ExternalServiceUnavailableError, TransientError
from src.logging_config import request_id_var
from src.middleware import REQUEST_ID_HEADER
from src.schemas.library import LibraryMembership, LibraryMembershipCreate
from src.utils.resilience import CircuitBreaker, RetryPolicy

MEMBERSHIPS_PATH = 'memberships'


class LibraryClient:
    def __init__(
        self, http: httpx.AsyncClient, retry: RetryPolicy, breaker: CircuitBreaker
    ) -> None:
        self.http = http
        self.retry = retry
        self.breaker = breaker

    async def issue_membership(self, user_id: UUID) -> LibraryMembership:
        payload = LibraryMembershipCreate(user_id=user_id)
        response = await self._request(
            HTTPMethod.POST, MEMBERSHIPS_PATH, json=payload.model_dump(mode='json')
        )
        return self._parse(response, HTTPStatus.CREATED, HTTPStatus.OK)

    async def get_membership(self, membership_id: UUID) -> LibraryMembership | None:
        response = await self._request(HTTPMethod.GET, f'{MEMBERSHIPS_PATH}/{membership_id}')
        if response.status_code == HTTPStatus.NOT_FOUND:
            return None
        return self._parse(response, HTTPStatus.OK)

    async def _request(
        self, method: HTTPMethod, url: str, *, json: object = None
    ) -> httpx.Response:
        async def send() -> httpx.Response:
            return await self._send(method, url, json=json)

        try:
            return await self.retry.call(lambda: self.breaker.call(send))
        except TransientError as exc:
            raise ExternalServiceUnavailableError(str(exc)) from exc
        except CircuitOpenError as exc:
            raise ExternalServiceUnavailableError(f'{method} {url}: {exc}') from exc

    async def _send(self, method: HTTPMethod, url: str, *, json: object) -> httpx.Response:
        rid = request_id_var.get()
        headers = {REQUEST_ID_HEADER: rid} if rid else None
        try:
            response = await self.http.request(method, url, json=json, headers=headers)
        except httpx.TransportError as exc:
            raise TransientError(f'{method} {url}: {type(exc).__name__}') from exc
        if response.status_code >= HTTPStatus.INTERNAL_SERVER_ERROR:
            raise TransientError(f'{method} {url}: {response.status_code}')
        return response

    def _parse(self, response: httpx.Response, *expected: HTTPStatus) -> LibraryMembership:
        request = response.request
        if response.status_code not in expected:
            raise ExternalServiceUnavailableError(
                f'{request.method} {request.url}: unexpected status {response.status_code}'
            )
        try:
            return LibraryMembership.model_validate_json(response.content)
        except ValidationError as exc:
            raise ExternalServiceUnavailableError(
                f'{request.method} {request.url}: invalid body'
            ) from exc
