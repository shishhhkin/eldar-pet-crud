from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.exceptions import ObjectNotFoundError
from src.models.authors import AuthorModel
from src.models.books import BookModel
from src.schemas.authors import AuthorCreate, AuthorUpdate


class AuthorService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _get_with_books(self, author_id: UUID) -> AuthorModel:
        stmt = (
            select(AuthorModel)
            .where(AuthorModel.id == author_id)
            .options(selectinload(AuthorModel.books))
        )
        author = (await self.session.execute(stmt)).scalar_one_or_none()
        if author is None:
            raise ObjectNotFoundError(AuthorModel, author_id)
        return author

    async def create(self, payload: AuthorCreate) -> AuthorModel:
        author = AuthorModel(
            **payload.model_dump(exclude={'books'}),
            books=[BookModel(**book.model_dump()) for book in payload.books],
        )
        self.session.add(author)
        await self.session.flush()
        await self.session.refresh(author, attribute_names=['books'])
        return author

    async def get(self, author_id: UUID) -> AuthorModel:
        return await self._get_with_books(author_id)

    async def update(self, author_id: UUID, payload: AuthorUpdate) -> AuthorModel:
        author = await self._get_with_books(author_id)
        fields = payload.model_fields_set
        if payload.name is not None:
            author.name = payload.name
        if 'bio' in fields:
            author.bio = payload.bio
        if 'books' in fields and payload.books is not None:
            author.books = [BookModel(**book.model_dump()) for book in payload.books]
        await self.session.flush()
        await self.session.refresh(author, attribute_names=['books'])
        return author

    async def delete(self, author_id: UUID) -> None:
        author = await self._get_with_books(author_id)
        author.is_deleted = True
        for book in author.books:
            book.is_deleted = True
        await self.session.flush()
