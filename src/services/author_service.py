from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.authors import AuthorModel
from src.models.books import BookModel
from src.repository import Repo
from src.schemas.authors import AuthorCreate, AuthorUpdate


class AuthorService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = Repo(session, AuthorModel)

    async def create(self, payload: AuthorCreate) -> AuthorModel:
        author = AuthorModel(
            **payload.model_dump(exclude={'books'}),
            books=[BookModel(**book.model_dump()) for book in payload.books],
        )
        self.repo.add(author)
        await self.repo.flush()
        await self.repo.refresh(author, ['books'])
        return author

    async def get(self, author_id: UUID) -> AuthorModel:
        return await self.repo.get(author_id, selectinload(AuthorModel.books))

    async def update(self, author_id: UUID, payload: AuthorUpdate) -> AuthorModel:
        author = await self.repo.get(author_id, selectinload(AuthorModel.books))
        fields = payload.model_fields_set
        if payload.name is not None:
            author.name = payload.name
        if 'bio' in fields:
            author.bio = payload.bio
        if 'books' in fields and payload.books is not None:
            author.books = [BookModel(**book.model_dump()) for book in payload.books]
        await self.repo.flush()
        await self.repo.refresh(author, ['books'])
        return author

    async def delete(self, author_id: UUID) -> None:
        author = await self.repo.get(author_id, selectinload(AuthorModel.books))
        author.is_deleted = True
        for book in author.books:
            book.is_deleted = True
        await self.repo.flush()
