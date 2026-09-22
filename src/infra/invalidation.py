import asyncio
import logging
from collections.abc import Sequence
from datetime import timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.infra.cache import Cache
from src.infra.db import tx_session
from src.repository import CacheInvalidationRepo

logger = logging.getLogger(__name__)


class InvalidationOutbox:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        cache: Cache,
        batch_size: int,
        retry_interval_seconds: float,
        lease_seconds: float,
    ) -> None:
        self.session_factory = session_factory
        self.cache = cache
        self.batch_size = batch_size
        self.retry_interval_seconds = retry_interval_seconds
        self.lease = timedelta(seconds=lease_seconds)

    async def flush(self, ids: Sequence[UUID] | None = None) -> None:
        try:
            while await self._process_batch(ids) == self.batch_size:
                pass
        except Exception:
            logger.exception('cache invalidation outbox processing failed')

    async def run(self) -> None:
        while True:
            await asyncio.sleep(self.retry_interval_seconds)
            await self.flush()

    async def _process_batch(self, ids: Sequence[UUID] | None) -> int:
        async with tx_session(self.session_factory) as session:
            claimed = await CacheInvalidationRepo(session).claim(self.batch_size, self.lease, ids)
        if not claimed:
            return 0
        done: list[UUID] = []
        for invalidation_id, key in claimed:
            if not await self.cache.tombstone(key):
                break
            done.append(invalidation_id)
        remaining = [invalidation_id for invalidation_id, _ in claimed[len(done) :]]
        async with tx_session(self.session_factory) as session:
            repo = CacheInvalidationRepo(session)
            if done:
                await repo.delete(done)
            if remaining:
                await repo.release(remaining)
        return len(done)
