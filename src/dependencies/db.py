import logging
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.dependencies.outbox import OutboxDep
from src.infra.db import readonly_session, tx_session
from src.repository.cache_invalidations import pop_pending_invalidations
from src.services.invalidation_outbox import InvalidationOutbox

logger = logging.getLogger(__name__)


def get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    return cast('async_sessionmaker[AsyncSession]', request.app.state.session_factory)


SessionFactoryDep = Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)]


async def get_session(session_factory: SessionFactoryDep) -> AsyncIterator[AsyncSession]:
    async with readonly_session(session_factory) as session:
        yield session


@asynccontextmanager
async def invalidating_tx_session(
    session_factory: async_sessionmaker[AsyncSession],
    outbox: InvalidationOutbox,
) -> AsyncGenerator[AsyncSession]:
    async with tx_session(session_factory) as session:
        yield session
    pending = pop_pending_invalidations(session)
    if pending:
        try:
            await outbox.flush(pending)
        except SQLAlchemyError, OSError:
            logger.warning('cache invalidation deferred to outbox worker', exc_info=True)


async def get_tx_session(
    session_factory: SessionFactoryDep,
    outbox: OutboxDep,
) -> AsyncIterator[AsyncSession]:
    async with invalidating_tx_session(session_factory, outbox) as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]
TxSessionDep = Annotated[AsyncSession, Depends(get_tx_session, scope='function')]
