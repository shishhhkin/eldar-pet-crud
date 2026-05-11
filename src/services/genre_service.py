from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.exceptions import ObjectNotFoundError
from src.models.genres import GenreModel
from src.schemas.genres import GenreCreate, GenreUpdate


async def _get_with_books(session: AsyncSession, genre_id: UUID) -> GenreModel | None:
    stmt = (
        select(GenreModel).where(GenreModel.id == genre_id).options(selectinload(GenreModel.books))
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def create_genre(session: AsyncSession, payload: GenreCreate) -> GenreModel:
    genre = GenreModel(**payload.model_dump())
    session.add(genre)
    await session.flush()
    await session.refresh(genre, attribute_names=['books'])
    return genre


async def get_genre(session: AsyncSession, genre_id: UUID) -> GenreModel:
    genre = await _get_with_books(session, genre_id)
    if genre is None:
        raise ObjectNotFoundError(GenreModel, genre_id)
    return genre


async def update_genre(session: AsyncSession, genre_id: UUID, payload: GenreUpdate) -> GenreModel:
    genre = await _get_with_books(session, genre_id)
    if genre is None:
        raise ObjectNotFoundError(GenreModel, genre_id)
    for field, value in payload.model_dump().items():
        setattr(genre, field, value)
    await session.flush()
    return genre


async def delete_genre(session: AsyncSession, genre_id: UUID) -> None:
    genre = await session.get(GenreModel, genre_id)
    if genre is None:
        raise ObjectNotFoundError(GenreModel, genre_id)
    await session.delete(genre)
    await session.flush()
