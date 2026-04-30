from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.books import BookModel
from src.models.genres import GenreModel
from src.schemas.books import BookCreate, BookUpdate


async def _get_loaded(session: AsyncSession, book_id: UUID) -> BookModel | None:
    stmt = (
        select(BookModel)
        .where(BookModel.id == book_id)
        .options(selectinload(BookModel.author), selectinload(BookModel.genres))
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def _load_genres(session: AsyncSession, genre_ids: list[UUID]) -> list[GenreModel]:
    if not genre_ids:
        return []
    unique_ids = list(set(genre_ids))
    stmt = select(GenreModel).where(GenreModel.id.in_(unique_ids))
    genres = list((await session.execute(stmt)).scalars().all())
    if len(genres) != len(unique_ids):
        found = {g.id for g in genres}
        missing = [str(gid) for gid in unique_ids if gid not in found]
        raise ValueError(f'genres not found: {missing}')
    return genres


async def create_book(session: AsyncSession, payload: BookCreate) -> BookModel:
    genres = await _load_genres(session, payload.genre_ids)
    book = BookModel(title=payload.title, author_id=payload.author_id, genres=genres)
    session.add(book)
    await session.flush()
    await session.refresh(book, attribute_names=['author', 'genres'])
    return book


async def get_book(session: AsyncSession, book_id: UUID) -> BookModel | None:
    return await _get_loaded(session, book_id)


async def update_book(
    session: AsyncSession, book_id: UUID, payload: BookUpdate
) -> BookModel | None:
    book = await _get_loaded(session, book_id)
    if book is None:
        return None
    book.title = payload.title
    book.author_id = payload.author_id
    book.genres = await _load_genres(session, payload.genre_ids)
    await session.flush()
    await session.refresh(book, attribute_names=['author', 'genres'])
    return book


async def delete_book(session: AsyncSession, book_id: UUID) -> bool:
    book = await session.get(BookModel, book_id)
    if book is None:
        return False
    await session.delete(book)
    await session.flush()
    return True
