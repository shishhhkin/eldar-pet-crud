import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.clients.library import LibraryClient
from src.exceptions import ExternalServiceUnavailableError
from src.infra.db import readonly_session, tx_session
from src.mappers.users import to_membership_read
from src.repository import UserMembershipRepo
from src.schemas.library import LibraryMembership
from src.schemas.users import MembershipRead

logger = logging.getLogger(__name__)


class MembershipIssuer:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repo_factory: Callable[[AsyncSession], UserMembershipRepo],
        library: LibraryClient,
        batch_size: int,
        interval_seconds: float,
    ) -> None:
        self.session_factory = session_factory
        self.repo_factory = repo_factory
        self.library = library
        self.batch_size = batch_size
        self.interval_seconds = interval_seconds

    async def issue(self, user_id: UUID) -> MembershipRead | None:
        try:
            membership = await self.library.issue_membership(user_id)
        except ExternalServiceUnavailableError as exc:
            logger.warning('membership issue deferred: user_id=%s (%s)', user_id, exc)
            return None
        return await self.store(membership)

    async def store(self, membership: LibraryMembership) -> MembershipRead:
        synced_at = datetime.now(UTC)
        try:
            async with tx_session(self.session_factory) as session:
                await self.repo_factory(session).store(membership, synced_at)
        except SQLAlchemyError, OSError:
            logger.warning(
                'membership copy not stored: user_id=%s', membership.user_id, exc_info=True
            )
        return to_membership_read(membership, synced_at)

    async def sync_pending(self) -> int:
        async with readonly_session(self.session_factory) as session:
            user_ids = await self.repo_factory(session).pending_user_ids(self.batch_size)
        issued = 0
        for user_id in user_ids:
            if await self.issue(user_id) is None:
                break
            issued += 1
        return issued

    async def run(self) -> None:
        while True:
            await asyncio.sleep(self.interval_seconds)
            try:
                await self.sync_pending()
            except Exception:
                logger.exception('membership sync failed')
