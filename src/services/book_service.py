from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.books import BookModel
from src.schemas.books import BookCreate, BookUpdate


async def _get_with_author(session: AsyncSession, book_id: UUID) -> BookModel | None:
    stmt = (
        select(BookModel)
        .where(BookModel.id == book_id)
        .options(selectinload(BookModel.author))
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def create_book(session: AsyncSession, payload: BookCreate) -> BookModel:
    book = BookModel(title=payload.title, author_id=payload.author_id)
    session.add(book)
    await session.flush()
    await session.refresh(book, attribute_names=['author'])
    return book


async def get_book(session: AsyncSession, book_id: UUID) -> BookModel | None:
    return await _get_with_author(session, book_id)


async def update_book(
    session: AsyncSession, book_id: UUID, payload: BookUpdate
) -> BookModel | None:
    book = await _get_with_author(session, book_id)
    if book is None:
        return None
    book.title = payload.title
    book.author_id = payload.author_id
    await session.flush()
    await session.refresh(book, attribute_names=['author'])
    return book


async def delete_book(session: AsyncSession, book_id: UUID) -> bool:
    book = await session.get(BookModel, book_id)
    if book is None:
        return False
    await session.delete(book)
    await session.flush()
    return True
