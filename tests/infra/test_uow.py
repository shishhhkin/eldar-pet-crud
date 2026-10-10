import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.infra.uow import UnitOfWork
from src.repository import CacheInvalidationRepo
from tests.conftest import outbox_keys


async def test_uow_rolls_back_on_exception(
    session_factory: async_sessionmaker[AsyncSession], db_session: AsyncSession
) -> None:
    with pytest.raises(RuntimeError):
        async with UnitOfWork(db_session):
            await CacheInvalidationRepo(db_session).add('first')
            raise RuntimeError

    assert not db_session.in_transaction()
    assert await outbox_keys(session_factory) == []
