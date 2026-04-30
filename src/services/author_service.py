from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.exceptions import AuthorNotFound
from src.models.authors import AuthorModel
from src.schemas.authors import AuthorCreate, AuthorUpdate


async def create_author(session: AsyncSession, payload: AuthorCreate) -> AuthorModel:
    author = AuthorModel(name=payload.name, bio=payload.bio)
    session.add(author)
    await session.flush()
    return author


async def get_author(session: AsyncSession, author_id: UUID) -> AuthorModel:
    author = await session.get(AuthorModel, author_id)
    if author is None:
        raise AuthorNotFound(author_id)
    return author


async def update_author(
    session: AsyncSession, author_id: UUID, payload: AuthorUpdate
) -> AuthorModel:
    author = await session.get(AuthorModel, author_id)
    if author is None:
        raise AuthorNotFound(author_id)
    author.name = payload.name
    author.bio = payload.bio
    await session.flush()
    return author


async def delete_author(session: AsyncSession, author_id: UUID) -> None:
    author = await session.get(AuthorModel, author_id)
    if author is None:
        raise AuthorNotFound(author_id)
    await session.delete(author)
    await session.flush()
