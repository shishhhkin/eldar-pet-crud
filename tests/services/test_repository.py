from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.authors import AuthorModel
from src.repository import Repo


async def _seed(session: AsyncSession, count: int) -> tuple[Repo[AuthorModel], list[AuthorModel]]:
    repo = Repo(session, AuthorModel)
    authors = [AuthorModel(name=f'author-{i}') for i in range(count)]
    for author in authors:
        repo.add(author)
    await repo.flush()
    return repo, authors


async def test_list_paginates(db_session: AsyncSession) -> None:
    repo, authors = await _seed(db_session, 5)
    ids = [author.id for author in authors]

    page1 = await repo.list(limit=2, offset=0)
    page2 = await repo.list(limit=2, offset=2)
    page3 = await repo.list(limit=2, offset=4)

    assert [author.id for author in page1] == ids[:2]
    assert [author.id for author in page2] == ids[2:4]
    assert [author.id for author in page3] == ids[4:]


async def test_list_excludes_soft_deleted(db_session: AsyncSession) -> None:
    repo, authors = await _seed(db_session, 3)
    authors[1].is_deleted = True
    await repo.flush()

    result = await repo.list(limit=10, offset=0)

    assert [author.id for author in result] == [authors[0].id, authors[2].id]


async def test_get_returns_none_for_missing(db_session: AsyncSession) -> None:
    repo = Repo(db_session, AuthorModel)

    assert await repo.get(uuid4()) is None


async def test_get_returns_none_for_soft_deleted(db_session: AsyncSession) -> None:
    repo, authors = await _seed(db_session, 1)
    authors[0].is_deleted = True
    await repo.flush()

    assert await repo.get(authors[0].id) is None
