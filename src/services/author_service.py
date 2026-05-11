from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.exceptions import ObjectNotFoundError
from src.models.authors import AuthorModel
from src.schemas.authors import AuthorCreate, AuthorUpdate


async def _get_with_books(session: AsyncSession, author_id: UUID) -> AuthorModel | None:
    stmt = (
        select(AuthorModel)
        .where(AuthorModel.id == author_id)
        .options(selectinload(AuthorModel.books))
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def create_author(session: AsyncSession, payload: AuthorCreate) -> AuthorModel:
    author = AuthorModel(**payload.model_dump())
    session.add(author)
    await session.flush()
    await session.refresh(author, attribute_names=['books'])
    return author


async def get_author(session: AsyncSession, author_id: UUID) -> AuthorModel:
    author = await _get_with_books(session, author_id)
    if author is None:
        raise ObjectNotFoundError(AuthorModel, author_id)
    return author


async def update_author(
    session: AsyncSession, author_id: UUID, payload: AuthorUpdate
) -> AuthorModel:
    author = await _get_with_books(session, author_id)
    if author is None:
        raise ObjectNotFoundError(AuthorModel, author_id)
    for field, value in payload.model_dump().items():
        setattr(author, field, value)
    await session.flush()
    return author


async def delete_author(session: AsyncSession, author_id: UUID) -> None:
    author = await session.get(AuthorModel, author_id)
    if author is None:
        raise ObjectNotFoundError(AuthorModel, author_id)
    await session.delete(author)
    await session.flush()
