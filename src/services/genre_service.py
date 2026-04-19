from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.genres import GenreModel
from src.schemas.genres import GenreCreate, GenreUpdate


async def create_genre(session: AsyncSession, payload: GenreCreate) -> GenreModel:
    genre = GenreModel(name=payload.name)
    session.add(genre)
    await session.flush()
    return genre


async def get_genre(session: AsyncSession, genre_id: UUID) -> GenreModel | None:
    return await session.get(GenreModel, genre_id)


async def update_genre(
    session: AsyncSession, genre_id: UUID, payload: GenreUpdate
) -> GenreModel | None:
    genre = await session.get(GenreModel, genre_id)
    if genre is None:
        return None
    genre.name = payload.name
    await session.flush()
    return genre


async def delete_genre(session: AsyncSession, genre_id: UUID) -> bool:
    genre = await session.get(GenreModel, genre_id)
    if genre is None:
        return False
    await session.delete(genre)
    await session.flush()
    return True
