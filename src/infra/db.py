from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from types import TracebackType
from typing import Final, Self

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

READONLY_EXECUTION_OPTIONS: Final = {'postgresql_readonly': True}


def build_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


@asynccontextmanager
async def readonly_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession]:
    async with session_factory() as session:
        await session.connection(execution_options=READONLY_EXECUTION_OPTIONS)
        yield session


@asynccontextmanager
async def tx_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession]:
    async with session_factory() as session, session.begin():
        yield session


class UnitOfWork:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def release_connection(self) -> None:
        await self.session.close()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if exc_type is None:
            await self.session.commit()
        else:
            await self.session.rollback()
