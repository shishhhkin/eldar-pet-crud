from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.infra.cache import CacheSession
from src.infra.db import tx_session


@asynccontextmanager
async def invalidating_tx_session(
    session_factory: async_sessionmaker[AsyncSession],
    cache: CacheSession,
) -> AsyncGenerator[AsyncSession]:
    async with tx_session(session_factory) as session:
        yield session
    await cache.apply_pending()
