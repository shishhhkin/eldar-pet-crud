import asyncio
import logging
from collections.abc import Callable
from contextlib import suppress
from datetime import timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.clients.library import LibraryClient
from src.exceptions import ExternalServiceBadResponseError, ExternalServiceUnavailableError
from src.infra.db import tx_session
from src.mappers.users import to_membership_read
from src.repository import PendingMembershipRepo, UserMembershipRepo
from src.schemas.library import LibraryMembership
from src.schemas.users import MembershipRead

logger = logging.getLogger(__name__)


class MembershipService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repo_factory: Callable[[AsyncSession], UserMembershipRepo],
        pending_factory: Callable[[AsyncSession], PendingMembershipRepo],
        library: LibraryClient,
        pass_limit: int,
        interval_seconds: float,
        lease_seconds: float,
        heartbeat: Callable[[], None] = lambda: None,
    ) -> None:
        self.session_factory = session_factory
        self.repo_factory = repo_factory
        self.pending_factory = pending_factory
        self.library = library
        self.pass_limit = pass_limit
        self.interval_seconds = interval_seconds
        self.lease = timedelta(seconds=lease_seconds)
        self.heartbeat = heartbeat
        self.stopping = asyncio.Event()

    def stop(self) -> None:
        self.stopping.set()

    async def issue(self, user_id: UUID, claim_token: UUID) -> MembershipRead | None:
        try:
            return await self._attempt(user_id, claim_token)
        except ExternalServiceUnavailableError:
            return None

    async def store(self, membership: LibraryMembership) -> MembershipRead:
        async with tx_session(self.session_factory) as session:
            stored = await self.repo_factory(session).store(membership)
            return to_membership_read(stored)

    async def process_pass(self) -> int:
        processed = 0
        while processed < self.pass_limit and not self.stopping.is_set():
            async with tx_session(self.session_factory) as session:
                claimed = await self.pending_factory(session).claim(self.lease)
            self.heartbeat()
            if claimed is None:
                break
            processed += 1
            try:
                await self._attempt(claimed.user_id, claimed.claim_token)
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

    async def _attempt(self, user_id: UUID, claim_token: UUID) -> MembershipRead | None:
        try:
            membership = await self.library.issue_membership(user_id)
        except ExternalServiceUnavailableError as exc:
            logger.warning('membership issue deferred: user_id=%s (%s)', user_id, exc)
            async with tx_session(self.session_factory) as session:
                await self.pending_factory(session).release(user_id, claim_token)
            raise
        except ExternalServiceBadResponseError as exc:
            logger.error('membership issue failed: user_id=%s (%s)', user_id, exc)
            async with tx_session(self.session_factory) as session:
                await self.pending_factory(session).fail(user_id, claim_token)
            return None
        async with tx_session(self.session_factory) as session:
            if not await self.pending_factory(session).complete(user_id, claim_token):
                logger.warning(
                    'membership issued for cancelled or reclaimed request: '
                    'user_id=%s membership_id=%s',
                    user_id,
                    membership.id,
                )
                return None
            stored = await self.repo_factory(session).store(membership)
            return to_membership_read(stored)
