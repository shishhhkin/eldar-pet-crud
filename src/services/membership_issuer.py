import asyncio
import logging
from collections.abc import Callable
from contextlib import suppress
from datetime import timedelta
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.clients.library import LibraryClient
from src.exceptions import ExternalServiceBadResponseError, ExternalServiceUnavailableError
from src.infra.db import tx_session
from src.mappers.users import to_membership_read
from src.repository import MembershipRequestRepo, UserMembershipRepo
from src.schemas.library import LibraryMembership
from src.schemas.users import MembershipRead
from src.utils.resilience import exponential_backoff

logger = logging.getLogger(__name__)


class MembershipIssuer:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repo_factory: Callable[[AsyncSession], UserMembershipRepo],
        requests_factory: Callable[[AsyncSession], MembershipRequestRepo],
        library: LibraryClient,
        pass_limit: int,
        interval_seconds: float,
        lease_seconds: float,
        retry_base_delay_seconds: float,
        retry_max_delay_seconds: float,
    ) -> None:
        self.session_factory = session_factory
        self.repo_factory = repo_factory
        self.requests_factory = requests_factory
        self.library = library
        self.pass_limit = pass_limit
        self.interval_seconds = interval_seconds
        self.lease = timedelta(seconds=lease_seconds)
        self.retry_base_delay_seconds = retry_base_delay_seconds
        self.retry_max_delay_seconds = retry_max_delay_seconds
        self.stopping = asyncio.Event()

    def stop(self) -> None:
        self.stopping.set()

    async def issue(self, user_id: UUID) -> MembershipRead | None:
        try:
            return await self._attempt(user_id, 0)
        except ExternalServiceUnavailableError:
            return None
        except SQLAlchemyError, OSError:
            logger.warning('membership request not settled: user_id=%s', user_id, exc_info=True)
            return None

    async def store(self, membership: LibraryMembership) -> MembershipRead:
        async with tx_session(self.session_factory) as session:
            stored = await self.repo_factory(session).store(membership)
            return to_membership_read(stored)

    async def process_pass(self) -> int:
        processed = 0
        while processed < self.pass_limit and not self.stopping.is_set():
            async with tx_session(self.session_factory) as session:
                request = await self.requests_factory(session).claim(self.lease)
            if request is None:
                break
            processed += 1
            try:
                await self._attempt(request.user_id, request.attempts)
            except ExternalServiceUnavailableError:
                break
        return processed

    async def run(self) -> None:
        while not self.stopping.is_set():
            try:
                await self.process_pass()
            except Exception:
                logger.exception('membership sync failed')
            with suppress(TimeoutError):
                await asyncio.wait_for(self.stopping.wait(), self.interval_seconds)

    async def _attempt(self, user_id: UUID, attempts: int) -> MembershipRead | None:
        try:
            membership = await self.library.issue_membership(user_id)
        except ExternalServiceUnavailableError as exc:
            logger.warning('membership issue deferred: user_id=%s (%s)', user_id, exc)
            async with tx_session(self.session_factory) as session:
                await self.requests_factory(session).release(user_id)
            raise
        except ExternalServiceBadResponseError as exc:
            attempts += 1
            logger.error(
                'membership issue rejected: user_id=%s attempts=%d (%s)',
                user_id,
                attempts,
                exc,
            )
            delay = exponential_backoff(
                attempts, self.retry_base_delay_seconds, self.retry_max_delay_seconds
            )
            async with tx_session(self.session_factory) as session:
                await self.requests_factory(session).reschedule(
                    user_id, attempts, timedelta(seconds=delay)
                )
            return None
        async with tx_session(self.session_factory) as session:
            if not await self.requests_factory(session).complete(user_id):
                logger.warning(
                    'membership issued for cancelled request: user_id=%s membership_id=%s',
                    user_id,
                    membership.id,
                )
                return None
            stored = await self.repo_factory(session).store(membership)
            return to_membership_read(stored)
