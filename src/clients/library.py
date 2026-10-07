import logging
from http import HTTPMethod, HTTPStatus
from uuid import UUID

import httpx
from pydantic import TypeAdapter, ValidationError

from src.exceptions import CircuitOpenError, ExternalServiceUnavailableError, TransientError
from src.logging_config import request_id_var
from src.middleware import REQUEST_ID_HEADER
from src.schemas.library import LibraryMembership, LibraryMembershipCreate
from src.utils.resilience import CircuitBreaker, RetryPolicy

logger = logging.getLogger(__name__)

MEMBERSHIPS_PATH = 'memberships'

_membership = TypeAdapter(LibraryMembership)
_memberships = TypeAdapter(list[LibraryMembership])


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
        if response.status_code == HTTPStatus.CONFLICT:
            logger.info('membership already issued, looking up: user_id=%s', user_id)
            existing = await self.find_membership(user_id)
            if existing is None:
                raise ExternalServiceUnavailableError(
                    f'membership for user {user_id} conflicts but absent'
                )
            return existing
        return self._parse(response, HTTPStatus.CREATED, _membership)

    async def get_membership(self, membership_id: UUID) -> LibraryMembership | None:
        response = await self._request(HTTPMethod.GET, f'{MEMBERSHIPS_PATH}/{membership_id}')
        if response.status_code == HTTPStatus.NOT_FOUND:
            return None
        return self._parse(response, HTTPStatus.OK, _membership)

    async def find_membership(self, user_id: UUID) -> LibraryMembership | None:
        response = await self._request(
            HTTPMethod.GET, MEMBERSHIPS_PATH, params={'user_id': str(user_id)}
        )
        memberships = self._parse(response, HTTPStatus.OK, _memberships)
        return memberships[0] if memberships else None

    async def _request(
        self,
        method: HTTPMethod,
        url: str,
        *,
        json: object = None,
        params: dict[str, str] | None = None,
    ) -> httpx.Response:
        async def send() -> httpx.Response:
            return await self._send(method, url, json=json, params=params)

        try:
            return await self.retry.call(lambda: self.breaker.call(send))
        except TransientError as exc:
            raise ExternalServiceUnavailableError(str(exc)) from exc
        except CircuitOpenError as exc:
            raise ExternalServiceUnavailableError(f'{method} {url}: {exc}') from exc

    async def _send(
        self,
        method: HTTPMethod,
        url: str,
        *,
        json: object,
        params: dict[str, str] | None,
    ) -> httpx.Response:
        rid = request_id_var.get()
        headers = {REQUEST_ID_HEADER: rid} if rid else None
        try:
            response = await self.http.request(
                method, url, json=json, params=params, headers=headers
            )
        except httpx.TransportError as exc:
            raise TransientError(f'{method} {url}: {type(exc).__name__}') from exc
        if response.status_code >= HTTPStatus.INTERNAL_SERVER_ERROR:
            raise TransientError(f'{method} {url}: {response.status_code}')
        return response

    def _parse[T](
        self, response: httpx.Response, expected: HTTPStatus, adapter: TypeAdapter[T]
    ) -> T:
        request = response.request
        if response.status_code != expected:
            raise ExternalServiceUnavailableError(
                f'{request.method} {request.url}: unexpected status {response.status_code}'
            )
        try:
            return adapter.validate_json(response.content)
        except ValidationError as exc:
            raise ExternalServiceUnavailableError(
                f'{request.method} {request.url}: invalid body'
            ) from exc
