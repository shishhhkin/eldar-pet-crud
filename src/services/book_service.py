import logging
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db import SessionDep, TxSessionDep
from src.exceptions import ConstraintViolationError, GenresNotFound, ObjectNotFoundError
from src.models.books import BookModel
from src.models.genres import GenreModel
from src.schemas.books import BookCreate, BookUpdate

logger = logging.getLogger(__name__)


class BookService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _get_with_relations(self, book_id: UUID) -> BookModel:
        stmt = (
            select(BookModel)
            .where(BookModel.id == book_id)
            .options(selectinload(BookModel.author), selectinload(BookModel.genres))
        )
        book = (await self.session.execute(stmt)).scalar_one_or_none()
        if book is None:
            raise ObjectNotFoundError(BookModel, book_id)
        return book

    async def _load_genres(self, genre_ids: list[UUID]) -> list[GenreModel]:
        if not genre_ids:
            return []
        unique_ids = list(set(genre_ids))
        stmt = select(GenreModel).where(GenreModel.id.in_(unique_ids))
        genres = list((await self.session.execute(stmt)).scalars().all())
        if len(genres) != len(unique_ids):
            found = {g.id for g in genres}
            missing = [gid for gid in unique_ids if gid not in found]
            raise GenresNotFound(missing)
        return genres

    async def create(self, payload: BookCreate) -> BookModel:
        genres = await self._load_genres(payload.genre_ids)
        book = BookModel(**payload.model_dump(exclude={'genre_ids'}), genres=genres)
        self.session.add(book)
        try:
            await self.session.flush()
        except IntegrityError as e:
            msg = f'integrity error creating book: {e.orig}'
            logger.error(msg, exc_info=True)
            raise ConstraintViolationError(f'failed to create book: {str(e.orig)}') from e
        await self.session.refresh(book, attribute_names=['author', 'genres'])
        return book

    async def get(self, book_id: UUID) -> BookModel:
        return await self._get_with_relations(book_id)

    async def update(self, book_id: UUID, payload: BookUpdate) -> BookModel:
        book = await self._get_with_relations(book_id)
        for field, value in payload.model_dump(exclude={'genre_ids'}).items():
            setattr(book, field, value)
        book.genres = await self._load_genres(payload.genre_ids)
        try:
            await self.session.flush()
        except IntegrityError as e:
            msg = f'integrity error updating book {book_id}: {e.orig}'
            logger.error(msg, exc_info=True)
            raise ConstraintViolationError(
                f'failed to update book {book_id}: {str(e.orig)}'
            ) from e
        await self.session.refresh(book, attribute_names=['author', 'genres'])
        return book

    async def delete(self, book_id: UUID) -> None:
        book = await self._get_with_relations(book_id)
        await self.session.delete(book)
        try:
            await self.session.flush()
        except IntegrityError as e:
            msg = f'integrity error deleting book {book_id}: {e.orig}'
            logger.error(msg, exc_info=True)
            raise ConstraintViolationError(
                f'failed to delete book {book_id}: {str(e.orig)}'
            ) from e


def _book_service(session: SessionDep) -> BookService:
    return BookService(session)


def _book_service_tx(session: TxSessionDep) -> BookService:
    return BookService(session)


BookServiceDep = Annotated[BookService, Depends(_book_service)]
BookServiceTxDep = Annotated[BookService, Depends(_book_service_tx)]
