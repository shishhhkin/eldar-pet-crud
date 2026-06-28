from uuid import UUID

from sqlalchemy.orm import selectinload

from src.exceptions import AuthorNotFoundError
from src.mappers.authors import apply_author_update, to_author_model, to_author_read
from src.models.authors import AuthorModel
from src.repository import AuthorRepo
from src.schemas.authors import AuthorCreate, AuthorRead, AuthorUpdate
from src.services.base import BaseService


class AuthorService(BaseService[AuthorModel, AuthorRepo]):
    not_found_error = AuthorNotFoundError

    async def create(self, payload: AuthorCreate) -> AuthorRead:
        author = to_author_model(payload)
        await self.repo.save(author, 'books')
        return to_author_read(author)

    async def get(self, author_id: UUID) -> AuthorRead:
        author = await self._get_or_raise(author_id, selectinload(AuthorModel.books))
        return to_author_read(author)

    async def update(self, author_id: UUID, payload: AuthorUpdate) -> AuthorRead:
        author = await self._get_or_raise(author_id, selectinload(AuthorModel.books))
        apply_author_update(author, payload)
        await self.repo.save(author, 'books')
        return to_author_read(author)

    async def delete(self, author_id: UUID) -> None:
        author = await self._get_or_raise(author_id, selectinload(AuthorModel.books))
        author.is_deleted = True
        for book in author.books:
            book.is_deleted = True
        await self.repo.save(author)
