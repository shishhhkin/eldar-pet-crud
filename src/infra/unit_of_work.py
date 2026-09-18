from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.infra.db import tx_session
from src.infra.invalidation import InvalidationOutbox
from src.repository.cache_invalidations import pop_pending_invalidations


@asynccontextmanager
async def invalidating_tx_session(
    session_factory: async_sessionmaker[AsyncSession],
    outbox: InvalidationOutbox,
) -> AsyncGenerator[AsyncSession]:
    async with tx_session(session_factory) as session:
        yield session
    pending = pop_pending_invalidations(session)
    if pending:
        await outbox.flush(pending)
