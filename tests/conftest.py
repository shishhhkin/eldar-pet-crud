from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.application import get_app
from src.db import get_session
from src.models import Base

TEST_DATABASE_URL = 'postgresql+asyncpg://postgres:123456@localhost:15432/postgres_test'


@pytest.fixture(scope='session')
async def engine() -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    yield engine
    await engine.dispose()


@pytest.fixture(scope='session')
def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(autouse=True)
async def prepare_schema(engine: AsyncEngine) -> AsyncIterator[None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest.fixture
async def client(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    app = get_app()

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test') as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def db_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session
