import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from http import HTTPStatus
from uuid import UUID, uuid4

import httpx

from src.schemas.library import LibraryMembership, LibraryMembershipCreate

BASE_URL = 'http://library/v1/'
MEMBERSHIPS_PATH = '/v1/memberships'


class Fault(StrEnum):
    TIMEOUT = 'timeout'
    COMMIT_THEN_TIMEOUT = 'commit_then_timeout'


@dataclass
class Hold:
    reached: asyncio.Event = field(default_factory=asyncio.Event)
    release: asyncio.Event = field(default_factory=asyncio.Event)


class FakeLibrary:
    def __init__(self) -> None:
        self.memberships: dict[UUID, LibraryMembership] = {}
        self.requests: list[httpx.Request] = []
        self._faults: deque[Fault | httpx.Response] = deque()
        self._hold: Hold | None = None

    def fail(
        self,
        times: int = 1,
        status: HTTPStatus = HTTPStatus.SERVICE_UNAVAILABLE,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._faults.extend(httpx.Response(status, headers=headers) for _ in range(times))

    def timeout(self, times: int = 1) -> None:
        self._faults.extend([Fault.TIMEOUT] * times)

    def commit_then_timeout(self) -> None:
        self._faults.append(Fault.COMMIT_THEN_TIMEOUT)

    def hold_next_get(self) -> Hold:
        self._hold = Hold()
        return self._hold

    def issue(self, user_id: UUID) -> LibraryMembership:
        membership = LibraryMembership(
            id=uuid4(),
            user_id=user_id,
            number=f'LIB-{len(self.memberships) + 1:08d}',
            issued_at=datetime.now(UTC),
            version=1,
        )
        self.memberships[user_id] = membership
        return membership

    def change(self, user_id: UUID, number: str) -> LibraryMembership:
        current = self.memberships[user_id]
        changed = current.model_copy(update={'number': number, 'version': current.version + 1})
        self.memberships[user_id] = changed
        return changed

    def forget(self, user_id: UUID) -> None:
        del self.memberships[user_id]

    async def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        fault = self._faults.popleft() if self._faults else None
        if fault is Fault.TIMEOUT:
            raise httpx.ReadTimeout('timed out', request=request)
        if isinstance(fault, httpx.Response):
            return fault
        response = self._route(request)
        if request.method == 'GET' and self._hold is not None:
            hold, self._hold = self._hold, None
            hold.reached.set()
            await hold.release.wait()
        if fault is Fault.COMMIT_THEN_TIMEOUT:
            raise httpx.ReadTimeout('timed out', request=request)
        return response

    def _route(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == MEMBERSHIPS_PATH and request.method == 'POST':
            payload = LibraryMembershipCreate.model_validate_json(request.content)
            existing = self.memberships.get(payload.user_id)
            if existing is not None:
                return self._json(HTTPStatus.OK, existing)
            return self._json(HTTPStatus.CREATED, self.issue(payload.user_id))
        membership_id = UUID(path.removeprefix(f'{MEMBERSHIPS_PATH}/'))
        for membership in self.memberships.values():
            if membership.id == membership_id:
                return self._json(HTTPStatus.OK, membership)
        return httpx.Response(HTTPStatus.NOT_FOUND)

    @staticmethod
    def _json(status: HTTPStatus, membership: LibraryMembership) -> httpx.Response:
        return httpx.Response(status, json=membership.model_dump(mode='json'))
