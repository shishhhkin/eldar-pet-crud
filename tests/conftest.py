from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.application import get_app
from src.config import Settings
from src.db import get_session, get_tx_session
from src.models import Base

_settings = Settings()  # type: ignore[call-arg]
TEST_DB_NAME = f'{_settings.postgres_db}_test'
_DSN_BASE = (
    f'postgresql+asyncpg://{_settings.postgres_user}:{_settings.postgres_password}'
    f'@{_settings.postgres_host}:{_settings.postgres_port}'
)
TEST_DATABASE_URL = f'{_DSN_BASE}/{TEST_DB_NAME}'
_ADMIN_DATABASE_URL = f'{_DSN_BASE}/{_settings.postgres_db}'


@pytest.fixture(scope='session', autouse=True)
async def ensure_test_database() -> None:
    admin = create_async_engine(_ADMIN_DATABASE_URL, isolation_level='AUTOCOMMIT')
    try:
        async with admin.connect() as conn:
            exists = await conn.scalar(
                text('SELECT 1 FROM pg_database WHERE datname = :name'),
                {'name': TEST_DB_NAME},
            )
            if not exists:
                await conn.execute(text(f'CREATE DATABASE "{TEST_DB_NAME}"'))
    finally:
        await admin.dispose()


@pytest.fixture(scope='session')
async def engine(ensure_test_database: None) -> AsyncIterator[AsyncEngine]:
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

    async def override_get_tx_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session, session.begin():
            yield session

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_tx_session] = override_get_tx_session

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
