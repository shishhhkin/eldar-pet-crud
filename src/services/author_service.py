from uuid import UUID

from sqlalchemy.orm import selectinload

from src.mappers.authors import apply_author_update, to_author_model
from src.models.authors import AuthorModel
from src.repository import AuthorRepo
from src.schemas.authors import AuthorCreate, AuthorRead, AuthorUpdate
from src.services.base import BaseService


class AuthorService(BaseService[AuthorRepo, AuthorModel, AuthorRead]):
    entity_name = 'Author'
    cache_namespace = 'author'
    read_model = AuthorRead
    load_options = (selectinload(AuthorModel.books),)

    async def create(self, payload: AuthorCreate) -> AuthorRead:
        author = to_author_model(payload)
        await self.repo.save(author, 'books')
        return self.read_model.model_validate(author)

    async def update(self, author_id: UUID, payload: AuthorUpdate) -> AuthorRead:
        author = await self._get_or_raise(author_id, *self.load_options)
        apply_author_update(author, payload)
        await self.repo.save(author, 'books')
        self.cache.invalidate_after_commit(self._cache_key(author_id))
        return self.read_model.model_validate(author)

    async def delete(self, author_id: UUID) -> None:
        author = await self._get_or_raise(author_id, *self.load_options)
        author.is_deleted = True
        for book in author.books:
            book.is_deleted = True
        await self.repo.save(author)
        self.cache.invalidate_after_commit(self._cache_key(author_id))
