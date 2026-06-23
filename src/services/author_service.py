from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.mappers.authors import apply_author_update, to_author_model
from src.models.authors import AuthorModel
from src.repository import Repo
from src.schemas.authors import AuthorCreate, AuthorUpdate
from src.services.base import BaseService


class AuthorService(BaseService[AuthorModel]):
    def __init__(self, session: AsyncSession) -> None:
        self.repo = Repo(session, AuthorModel)

    async def create(self, payload: AuthorCreate) -> AuthorModel:
        author = to_author_model(payload)
        self.repo.add(author)
        await self.repo.flush()
        await self.repo.refresh(author, ['books'])
        return author

    async def get(self, author_id: UUID) -> AuthorModel:
        return await self._get_or_raise(author_id, selectinload(AuthorModel.books))

    async def update(self, author_id: UUID, payload: AuthorUpdate) -> AuthorModel:
        author = await self._get_or_raise(author_id, selectinload(AuthorModel.books))
        apply_author_update(author, payload)
        await self.repo.flush()
        await self.repo.refresh(author, ['books'])
        return author

    async def delete(self, author_id: UUID) -> None:
        author = await self._get_or_raise(author_id, selectinload(AuthorModel.books))
        author.is_deleted = True
        for book in author.books:
            book.is_deleted = True
        await self.repo.flush()
