from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.authors import AuthorModel
from src.repository import Repo


async def _seed(session: AsyncSession, count: int) -> tuple[Repo[AuthorModel], list[AuthorModel]]:
    repo = Repo(session, AuthorModel)
    authors = [AuthorModel(name=f'author-{i}') for i in range(count)]
    session.add_all(authors)
    await session.flush()
    return repo, authors


async def test_get_returns_none_for_missing(db_session: AsyncSession) -> None:
    repo = Repo(db_session, AuthorModel)

    assert await repo.get(uuid4()) is None


async def test_get_returns_none_for_soft_deleted(db_session: AsyncSession) -> None:
    repo, authors = await _seed(db_session, 1)
    authors[0].is_deleted = True
    await db_session.flush()

    assert await repo.get(authors[0].id) is None


async def test_get_returns_active(db_session: AsyncSession) -> None:
    repo, authors = await _seed(db_session, 1)

    fetched = await repo.get(authors[0].id)

    assert fetched is not None
    assert fetched.id == authors[0].id
