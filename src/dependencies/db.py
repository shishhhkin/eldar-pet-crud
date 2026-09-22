from collections.abc import AsyncIterator
from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.dependencies.outbox import OutboxDep
from src.infra.db import readonly_session
from src.infra.unit_of_work import invalidating_tx_session


def get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    return cast('async_sessionmaker[AsyncSession]', request.app.state.session_factory)


SessionFactoryDep = Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)]


async def get_session(session_factory: SessionFactoryDep) -> AsyncIterator[AsyncSession]:
    async with readonly_session(session_factory) as session:
        yield session


async def get_tx_session(
    session_factory: SessionFactoryDep,
    outbox: OutboxDep,
) -> AsyncIterator[AsyncSession]:
    async with invalidating_tx_session(session_factory, outbox) as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]
TxSessionDep = Annotated[AsyncSession, Depends(get_tx_session, scope='function')]
