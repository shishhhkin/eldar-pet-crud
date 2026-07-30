from collections.abc import AsyncIterator
from typing import Final

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.config import Settings

settings = Settings()  # type: ignore[call-arg]

READONLY_EXECUTION_OPTIONS: Final = {'postgresql_readonly': True}


engine: AsyncEngine = create_async_engine(
    str(settings.postgres_url),
    pool_pre_ping=True,
)

SessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        await session.connection(execution_options=READONLY_EXECUTION_OPTIONS)
        yield session


async def get_tx_session() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session, session.begin():
        yield session
