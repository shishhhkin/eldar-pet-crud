from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.exceptions import ConflictError, GenresNotFound, ObjectNotFoundError
from src.models.authors import AuthorModel
from src.models.books import BookModel
from src.models.genres import GenreModel
from src.schemas.books import BookCreate, BookUpdate


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

    async def _ensure_author_active(self, author_id: UUID) -> None:
        stmt = select(AuthorModel.id).where(
            AuthorModel.id == author_id,
            AuthorModel.is_deleted.is_(False),
        )
        if (await self.session.execute(stmt)).scalar_one_or_none() is None:
            raise ConflictError(f'author {author_id} is not available')

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
        await self._ensure_author_active(payload.author_id)
        genres = await self._load_genres(payload.genre_ids)
        book = BookModel(**payload.model_dump(exclude={'genre_ids'}), genres=genres)
        self.session.add(book)
        await self.session.flush()
        await self.session.refresh(book, attribute_names=['author', 'genres'])
        return book

    async def get(self, book_id: UUID) -> BookModel:
        return await self._get_with_relations(book_id)

    async def update(self, book_id: UUID, payload: BookUpdate) -> BookModel:
        book = await self._get_with_relations(book_id)
        await self._ensure_author_active(payload.author_id)
        for field, value in payload.model_dump(exclude={'genre_ids'}).items():
            setattr(book, field, value)
        book.genres = await self._load_genres(payload.genre_ids)
        await self.session.flush()
        await self.session.refresh(book, attribute_names=['author', 'genres'])
        return book

    async def delete(self, book_id: UUID) -> None:
        book = await self._get_with_relations(book_id)
        book.is_deleted = True
        await self.session.flush()
