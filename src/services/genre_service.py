from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.exceptions import GenreNotFound
from src.models.genres import GenreModel
from src.schemas.genres import GenreCreate, GenreUpdate


async def create_genre(session: AsyncSession, payload: GenreCreate) -> GenreModel:
    genre = GenreModel(name=payload.name)
    session.add(genre)
    await session.flush()
    return genre


async def get_genre(session: AsyncSession, genre_id: UUID) -> GenreModel:
    genre = await session.get(GenreModel, genre_id)
    if genre is None:
        raise GenreNotFound(genre_id)
    return genre


async def update_genre(
    session: AsyncSession, genre_id: UUID, payload: GenreUpdate
) -> GenreModel:
    genre = await session.get(GenreModel, genre_id)
    if genre is None:
        raise GenreNotFound(genre_id)
    genre.name = payload.name
    await session.flush()
    return genre


async def delete_genre(session: AsyncSession, genre_id: UUID) -> None:
    genre = await session.get(GenreModel, genre_id)
    if genre is None:
        raise GenreNotFound(genre_id)
    await session.delete(genre)
    await session.flush()
